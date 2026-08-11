"""POC Validator — Streamlit client.

A client, not the product. It holds no validation logic: it either calls the
deployed AgentCore Runtime, or imports the deterministic core directly for a
local review with no AWS account. Both paths render identically, which is what
makes the sample demonstrable before anyone spends money.

Installed separately from the agent — see ui/requirements.txt for why they
cannot share a virtualenv.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import streamlit as st

SAMPLE_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("POC_VALIDATOR_ROOT", str(SAMPLE_ROOT))
sys.path.insert(0, str(SAMPLE_ROOT / "app"))

from pocvalidator.core import catalog, chaining, diagrams, engine, sow  # noqa: E402
from pocvalidator.core.models import EdgeType, Severity  # noqa: E402

st.set_page_config(page_title="POC Validator", page_icon="✓", layout="wide")

SEVERITY_MARK = {
    Severity.CRITICAL: "◆ Critical",
    Severity.HIGH: "▲ High",
    Severity.MEDIUM: "■ Medium",
    Severity.LOW: "● Low",
}
VERDICT_MARK = {
    "Not ready": "◆",
    "Needs work": "▲",
    "Conditionally ready": "■",
    "Ready": "●",
}
EDGE_MARK = {
    EdgeType.NATIVE: "●",
    EdgeType.GLUE: "■",
    EdgeType.ANTI_PATTERN: "◆",
    EdgeType.UNVERIFIED: "▲",
}

st.markdown(
    """
    <style>
      .block-container {padding-top: 2.2rem; max-width: 1200px;}
      .verdict {border-left: 5px solid #444; padding: 0.9rem 1.1rem;
                background: rgba(128,128,128,0.07); border-radius: 4px;}
      .verdict h3 {margin: 0 0 0.25rem 0; font-size: 1.25rem;}
      .verdict p {margin: 0; opacity: 0.85;}
    </style>
    """,
    unsafe_allow_html=True,
)


def init_state() -> None:
    for key, value in {
        "description": "",
        "segment": "enterprise",
        "industry": "generic",
        "region": "ap-south-1",
        "selected": [],
        "edges": [],
        "sow_text": "",
        "report": None,
        "sow_score": None,
        "extraction": None,
        "extraction_confirmed": False,
    }.items():
        st.session_state.setdefault(key, value)


init_state()

segments = catalog.segments()
industries = catalog.industries()
choices = catalog.service_choices()
label_by_id = {sid: label for sid, label in choices}
id_by_label = {label: sid for sid, label in choices}

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Submission context")

    examples = catalog.examples()
    labels = ["— start blank —"] + [example["name"] for example in examples]
    picked = st.selectbox("Load an example", labels)
    if picked != labels[0] and st.button("Load", use_container_width=True):
        example = next(e for e in examples if e["name"] == picked)
        st.session_state.update(
            description=example["description"].strip(),
            segment=example["segment"],
            industry=example["industry"],
            region=example["region"],
            selected=list(example["services"]),
            edges=[tuple(edge) for edge in example["edges"]],
            report=None,
            extraction=None,
            extraction_confirmed=False,
        )
        st.rerun()

    st.divider()
    segment_ids = list(segments)
    st.session_state.segment = st.selectbox(
        "Segment", segment_ids,
        index=segment_ids.index(st.session_state.segment),
        format_func=lambda s: segments[s]["name"],
    )
    industry_ids = list(industries)
    st.session_state.industry = st.selectbox(
        "Industry", industry_ids,
        index=industry_ids.index(st.session_state.industry),
        format_func=lambda s: industries[s]["name"],
    )
    st.session_state.region = st.text_input("Region", st.session_state.region)

    residency = industries[st.session_state.industry].get("data_residency")
    if residency:
        st.info(residency["note"].strip(), icon="ℹ️")

    st.divider()
    runtime_arn = st.text_input(
        "Runtime ARN (optional)",
        os.getenv("AGENTCORE_RUNTIME_ARN", ""),
        help="Leave blank to run the deterministic core locally with no AWS account. "
        "Supply a deployed Runtime ARN to use diagram extraction and model-assisted "
        "SOW grading.",
    )
    st.caption(
        f"{len(catalog.service_defs())} services · {len(catalog.integrations())} "
        f"integrations · {len(segments)} segments · {len(industries)} industries"
    )

# ── Header and intake ─────────────────────────────────────────────────────────

st.title("POC Validator")
st.markdown(
    "Reviews a proposed AWS architecture against segment and industry rules, checks "
    "the services actually connect, prices it, and scores the Scope of Work. "
    "**Every finding names the rule that produced it.**"
)

st.session_state.description = st.text_area(
    "What are you building?",
    value=st.session_state.description,
    height=90,
    placeholder="Describe the workload — what it does, who uses it, rough scale.",
)

# ── Diagram upload ────────────────────────────────────────────────────────────

st.markdown("#### 1 · Architecture")
source_tab, upload_tab, manual_tab = st.tabs(
    ["Upload diagram source", "Upload diagram image", "Pick services manually"]
)

with source_tab:
    st.caption(
        "draw.io and Mermaid files parse exactly — no model, and no confirmation "
        "step, because there is nothing to misread. Prefer this over an image "
        "whenever you have the source."
    )
    source_file = st.file_uploader(
        "Diagram source", type=["drawio", "xml", "mmd", "mermaid", "md"], key="src"
    )
    if source_file is not None:
        parsed = diagrams.parse(source_file.name, source_file.getvalue())
        st.caption(parsed.notes)
        if parsed.unmatched:
            st.warning(
                "Not recognised, and therefore not included: "
                + ", ".join(parsed.unmatched),
                icon="⚠️",
            )
        if parsed.services:
            st.success(
                f"Parsed {len(parsed.services)} services and {len(parsed.edges)} "
                "connections.",
                icon="✅",
            )
            if st.button("Use this design", type="primary", key="use_parsed"):
                st.session_state.selected = parsed.services
                st.session_state.edges = parsed.edges
                st.session_state.report = None
                st.rerun()
        else:
            st.error("No AWS services recognised in that file.")

with upload_tab:
    diagram = st.file_uploader(
        "Architecture diagram", type=["png", "jpg", "jpeg", "webp", "gif"]
    )
    if diagram is not None:
        st.image(diagram, caption=diagram.name, width=520)
        if not runtime_arn:
            st.warning(
                "Diagram extraction needs a deployed Runtime — vision runs on the "
                "agent, not in this client. Add a Runtime ARN in the sidebar, or "
                "switch to the manual tab.",
                icon="⚠️",
            )
        elif st.button("Extract services from diagram", type="primary"):
            with st.spinner("Reading the diagram…"):
                try:
                    import boto3

                    client = boto3.client("bedrock-agentcore")
                    response = client.invoke_agent_runtime(
                        agentRuntimeArn=runtime_arn,
                        payload=json.dumps(
                            {
                                "description": st.session_state.description,
                                "segment": st.session_state.segment,
                                "industry": st.session_state.industry,
                                "region": st.session_state.region,
                                "diagram_base64": base64.b64encode(
                                    diagram.getvalue()
                                ).decode(),
                                "diagram_format": Path(diagram.name).suffix.lstrip("."),
                            }
                        ).encode(),
                    )
                    body = response["response"].read().decode()
                    marker = body.rfind('{"status"')
                    parsed = json.loads(body[marker:]) if marker >= 0 else {}
                    st.session_state.extraction = parsed.get("extraction")
                    st.session_state.extraction_confirmed = False
                except Exception as exc:
                    st.error(f"Runtime invocation failed: {exc}")

    extraction = st.session_state.extraction
    if extraction:
        # The confirmation gate. Findings generated against a misread diagram
        # would describe a design the partner never proposed, so nothing
        # downstream runs until a human has agreed with the extraction.
        st.markdown("##### Confirm what was read")
        st.caption(
            "Nothing is validated until you confirm this. Correct anything wrong — "
            "an extraction error would otherwise become a finding about a design "
            "you never proposed."
        )
        confirmed_services = st.multiselect(
            "Services found",
            options=[label for _, label in choices],
            default=[
                label_by_id[s] for s in extraction.get("services", []) if s in label_by_id
            ],
        )
        if extraction.get("unmatched"):
            st.warning(
                "Not recognised, and therefore not included: "
                + ", ".join(extraction["unmatched"]),
                icon="⚠️",
            )
        if extraction.get("notes"):
            st.caption(f"Reader notes: {extraction['notes']}")
        if st.button("Confirm and use this", type="primary"):
            st.session_state.selected = [id_by_label[l] for l in confirmed_services]
            st.session_state.edges = [
                tuple(edge)
                for edge in extraction.get("edges", [])
                if len(edge) == 2 and all(e in st.session_state.selected for e in edge)
            ]
            st.session_state.extraction_confirmed = True
            st.session_state.report = None
            st.rerun()

with manual_tab:
    picked_labels = st.multiselect(
        "Services in the design",
        options=[label for _, label in choices],
        default=[
            label_by_id[s] for s in st.session_state.selected if s in label_by_id
        ],
    )
    st.session_state.selected = [id_by_label[label] for label in picked_labels]

if not st.session_state.selected:
    st.info("Pick services, upload a diagram, or load an example from the sidebar.")
    st.stop()

# ── Connections ───────────────────────────────────────────────────────────────

st.markdown("#### 2 · Connections")
left, right, action = st.columns([3, 3, 1.4])
source = left.selectbox(
    "From", st.session_state.selected, format_func=lambda s: label_by_id[s]
)
target = right.selectbox(
    "To", st.session_state.selected, format_func=lambda s: label_by_id[s]
)
action.write("")
if action.button("Add", use_container_width=True):
    if source != target and (source, target) not in st.session_state.edges:
        st.session_state.edges.append((source, target))
        st.session_state.report = None
        st.rerun()

st.session_state.edges = [
    edge
    for edge in st.session_state.edges
    if edge[0] in st.session_state.selected and edge[1] in st.session_state.selected
]
for position, (edge_source, edge_target) in enumerate(list(st.session_state.edges)):
    row, remove = st.columns([9, 1])
    row.markdown(f"`{label_by_id[edge_source]}` → `{label_by_id[edge_target]}`")
    if remove.button("Remove", key=f"rm_{position}", use_container_width=True):
        st.session_state.edges.pop(position)
        st.session_state.report = None
        st.rerun()

# ── SOW ───────────────────────────────────────────────────────────────────────

st.markdown("#### 3 · Scope of Work (optional)")
sow_file = st.file_uploader("Upload a SOW", type=["md", "txt"], key="sow_upload")
if sow_file is not None:
    st.session_state.sow_text = sow_file.getvalue().decode("utf-8", errors="replace")
st.session_state.sow_text = st.text_area(
    "Or paste it", value=st.session_state.sow_text, height=120, label_visibility="collapsed"
)

st.divider()
if st.button("Validate submission", type="primary", use_container_width=True):
    score = sow.score_heuristic(st.session_state.sow_text) if st.session_state.sow_text.strip() else None
    graph = engine.graph_from_selection(
        segment_id=st.session_state.segment,
        industry_id=st.session_state.industry,
        region=st.session_state.region,
        description=st.session_state.description,
        service_ids=st.session_state.selected,
        edges=st.session_state.edges,
    )
    st.session_state.sow_score = score
    st.session_state.report = engine.validate(graph, score)

report = st.session_state.report
if report is None:
    st.stop()

# ── Results ───────────────────────────────────────────────────────────────────

verdict, reasoning = report.verdict
st.markdown(
    f'<div class="verdict"><h3>{VERDICT_MARK[verdict]} {verdict}</h3>'
    f"<p>{reasoning}</p></div>",
    unsafe_allow_html=True,
)

metrics = st.columns(6)
metrics[0].metric("Critical", report.count(Severity.CRITICAL))
metrics[1].metric("High", report.count(Severity.HIGH))
metrics[2].metric("Medium", report.count(Severity.MEDIUM))
metrics[3].metric("Low", report.count(Severity.LOW))
metrics[4].metric("Est. monthly", f"${report.cost.total:,.0f}")
metrics[5].metric(
    "SOW score", f"{report.sow.total:.0f}" if report.sow else "—"
)

tabs = st.tabs(["Findings", "Architecture", "Cost", "Scope of Work", "Further reading"])

with tabs[0]:
    for conflict in report.conflicts:
        with st.container(border=True):
            st.markdown(f"**Tension — {conflict.attribute}** on {conflict.node_name}")
            st.markdown(f"- {conflict.segment_position}")
            st.markdown(f"- {conflict.industry_position}")
            st.caption(conflict.resolution)

    orphaned = chaining.orphans(report.graph)
    if orphaned:
        st.warning("Not connected to anything: " + ", ".join(orphaned), icon="⚠️")

    if not report.findings:
        st.success("No findings against the selected rule packs.", icon="✅")
    for finding in report.sorted_findings:
        with st.container(border=True):
            head, tag = st.columns([5, 1.5])
            head.markdown(f"**{finding.title}**")
            tag.markdown(f"`{SEVERITY_MARK[finding.severity]}`")
            st.markdown(finding.rationale)
            st.markdown(f"**Fix.** {finding.remediation}")
            footer = f"Rule `{finding.rule_id}` · {finding.source_label} · {finding.pillar}"
            if finding.doc_url:
                footer += f" · [documentation]({finding.doc_url})"
            st.caption(footer)

with tabs[1]:
    st.graphviz_chart(chaining.dot(report.graph), width="stretch")
    st.caption(
        "Solid = native · dashed = glue required · dotted = unverified · barred = unsupported"
    )
    for edge in report.graph.edges:
        with st.container(border=True):
            names = (
                f"{report.graph.nodes[edge.source].name} → "
                f"{report.graph.nodes[edge.target].name}"
            )
            label = edge.label + (f" — {edge.pattern}" if edge.pattern else "")
            st.markdown(f"{EDGE_MARK[edge.edge_type]} **{names}** · `{label}`")
            st.caption(
                edge.note + (f"  [documentation]({edge.doc_url})" if edge.doc_url else "")
            )

with tabs[2]:
    cost = report.cost
    top = st.columns(3)
    top[0].metric("Baseline", f"${cost.baseline:,.0f}")
    top[1].metric("Compliance premium", f"${cost.premium:,.0f}")
    top[2].metric("Total per month", f"${cost.total:,.0f}")
    st.caption(
        f"Directional only. Indicative on-demand rates, {cost.region}, snapshot "
        f"{cost.as_of}. Model it in the [AWS Pricing Calculator]({cost.source}) "
        "before quoting."
    )
    if cost.premium:
        st.info(
            f"The controls required by {segments[report.graph.segment_id]['name']} and "
            f"{industries[report.graph.industry_id]['name']} account for "
            f"{cost.premium / cost.total * 100:.0f}% of the monthly cost.",
            icon="ℹ️",
        )
    st.dataframe(
        [
            {
                "Service": line.node_name,
                "Driver": line.driver_label,
                "Quantity": f"{line.quantity:,.4g}",
                "Unit rate": f"${line.unit_rate:,.6g}",
                "Monthly": f"${line.monthly_cost:,.2f}",
                "Type": "Premium" if line.is_premium else "Baseline",
            }
            for line in cost.lines
        ],
        width="stretch",
        hide_index=True,
    )

with tabs[3]:
    score = report.sow
    if score is None:
        st.info("No Scope of Work submitted.")
    else:
        head = st.columns(3)
        head[0].metric("Score", f"{score.total:.1f} / 100")
        head[1].metric("Rating", score.rating)
        head[2].metric("Words", f"{score.word_count:,}")
        if not score.model_assisted:
            st.warning(
                "Heuristic floor only — no model grading available. Keyword presence "
                "cannot exceed Adequate, so this is a lower bound on the real score, "
                "not the score.",
                icon="⚠️",
            )
        st.markdown(f"**{score.summary}**")
        st.dataframe(
            [
                {
                    "Criterion": criterion.name,
                    "Weight": f"{criterion.weight}%",
                    "Band": f"{criterion.band} · {criterion.band_label}",
                    "Justification": criterion.justification,
                }
                for criterion in score.scores
            ],
            width="stretch",
            hide_index=True,
        )
        if score.gaps:
            st.markdown("##### Gaps, largest exposure first")
            for gap in score.gaps:
                with st.container(border=True):
                    st.markdown(f"**{gap.name}** · {gap.weight}% weight · {gap.band_label}")
                    st.caption(gap.justification)
                    st.markdown(f"**Fix.** {gap.gap_fix}")

with tabs[4]:
    st.caption(
        "AWS and Amazon sources only. The restriction is enforced by a domain "
        "allowlist in code, not by asking a model to behave."
    )
    for resource, reason in report.recommendations:
        with st.container(border=True):
            st.markdown(f"**[{resource.title}]({resource.url})** · `{resource.kind_label}`")
            st.markdown(resource.summary)
            st.caption(f"Suggested because: {reason}")

    st.divider()
    st.download_button(
        "Download review as JSON",
        data=json.dumps(
            {
                "verdict": {"result": verdict, "reasoning": reasoning},
                "findings": [
                    {
                        "rule_id": f.rule_id,
                        "severity": f.severity.value,
                        "title": f.title,
                        "remediation": f.remediation,
                        "doc_url": f.doc_url,
                    }
                    for f in report.sorted_findings
                ],
                "cost": {
                    "baseline": report.cost.baseline,
                    "compliance_premium": report.cost.premium,
                    "total": report.cost.total,
                },
                "sow": {"score": report.sow.total, "rating": report.sow.rating}
                if report.sow
                else None,
                "recommendations": [
                    {"title": r.title, "url": r.url, "why": why}
                    for r, why in report.recommendations
                ],
                "evidence": report.evidence,
            },
            indent=2,
        ),
        file_name="poc-validation.json",
        mime="application/json",
        width="stretch",
    )
