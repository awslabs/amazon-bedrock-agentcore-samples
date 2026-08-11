"""POC Validator — AgentCore Runtime entrypoint.

Five phases, plus two optional ones. Only phases 1 and 4 involve a model as
part of the standard review; 2, 3 and 5 are deterministic Python over the
shared design graph. That split is deliberate and carried over from ADR 0014
in the event-driven-claims-agent sample: the model is used where judgement is
needed (reading a diagram, banding prose) and kept away from anything a
reviewer would take at face value (findings, arithmetic, source URLs).

    Phase 1  Intake / diagram extraction   Sonnet, vision   → design graph
             ⤷ confirmation gate — nothing proceeds until the caller confirms
    Phase 2  Validation                     deterministic    → findings
    Phase 3  Pricing                        deterministic    → baseline + premium
    Phase 4  SOW scoring                    Haiku + weights  → score + gaps
    Phase 5  Recommendations                allowlist filter → AWS-only reading
    Phase 6a What-if pricing (optional)    Haiku + sandbox  → docs/decisions/0010
    Phase 6b FAQ knowledge search (optional) vector search  → docs/decisions/0011
"""

import base64
import dataclasses
import json
import sys
import uuid
from pathlib import Path

from bedrock_agentcore.identity.auth import requires_access_token
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from config import (
    AGENT_MODEL_ID,
    FAST_MODEL_ID,
    GATEWAY_CREDENTIAL_PROVIDER,
    GATEWAY_OAUTH_SCOPES,
    GATEWAY_URL,
    REQUIRE_EXTRACTION_CONFIRMATION,
)
from mcp.client.streamable_http import streamablehttp_client
from memory.session import get_memory_session_manager
from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.tools.mcp import MCPClient
from tools.faq_search import search_faq
from tools.structured_output import (
    get_last_extraction,
    get_last_sow_bands,
    reset_state,
    submit_extraction,
    submit_sow_assessment,
)
from tools.what_if_pricing import run_what_if

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import catalog, diagrams, engine, resources, sow
from core.models import Severity

app = BedrockAgentCoreApp()
log = app.logger

EXTRACTION_PROMPT = """You are an AWS architecture diagram reader.

You will be shown an architecture diagram. Your only job is to report what is on
it — the AWS services, and the connections between them.

Rules:
- Report only what you can see. Do not add services that "should" be there.
- If a box is ambiguous, report the label as written and note the ambiguity.
- Follow arrow direction for edges. Where there are no arrows, infer direction
  from data flow and say so in your notes.
- Do not evaluate the architecture. Do not offer opinions, findings or advice.
  A separate deterministic stage does that, and your speculation would corrupt it.
- You MUST finish by calling the submit_extraction tool exactly once.
"""

SOW_PROMPT = """You are grading a Scope of Work document against fixed criteria.

For each criterion you will be given an id and a question. Assign a band:
  0 Absent      — not present at all
  1 Mentioned   — referenced with no substance
  2 Partial     — present but incomplete or ambiguous
  3 Adequate    — clear and usable as written
  4 Strong      — explicit, specific and measurable

Rules:
- Judge only what the document says. Do not credit intent you infer.
- Boilerplate ("performed in a professional manner") is band 1, not band 3.
- Justify each band in one sentence, quoting or closely paraphrasing the document.
- Do NOT compute a total. Weighting happens outside the model and any total you
  produce will be discarded.
- You MUST finish by calling the submit_sow_assessment tool exactly once.
"""

_extractor = None
_sow_grader = None
_mcp_client = None


def load_model(fast: bool = False) -> BedrockModel:
    """Cost routing: Haiku for SOW banding (classification), Sonnet for vision."""
    return BedrockModel(model_id=FAST_MODEL_ID if fast else AGENT_MODEL_ID)


@requires_access_token(
    provider_name=GATEWAY_CREDENTIAL_PROVIDER,
    auth_flow="M2M",
    scopes=GATEWAY_OAUTH_SCOPES.replace(",", " ").split(),
)
def _build_mcp_client(*, access_token: str) -> MCPClient:
    """MCPClient for the Gateway, with Identity-managed OAuth.

    The decorator handles token acquisition from the AgentCore Identity token
    vault, caching and refresh — no secrets in env vars or code.
    """

    def _transport():
        headers = {"Authorization": f"Bearer {access_token}"}
        return streamablehttp_client(GATEWAY_URL, headers=headers)

    return MCPClient(_transport)


def get_mcp_client():
    """Gateway client, or None. None is a supported state, not an error."""
    global _mcp_client
    if _mcp_client is None:
        if not GATEWAY_URL:
            log.warning("GATEWAY_URL not configured — documentation lookup unavailable")
            return None
        try:
            _mcp_client = _build_mcp_client()
        except Exception as exc:
            log.warning("Failed to build MCP client (Identity auth): %s", exc)
            return None
    return _mcp_client


def get_extractor(session_manager=None):
    global _extractor
    tools = [submit_extraction]
    mcp = get_mcp_client()
    if mcp:
        tools.insert(0, mcp)
    if session_manager is not None:
        return Agent(
            model=load_model(),
            system_prompt=EXTRACTION_PROMPT,
            tools=tools,
            session_manager=session_manager,
        )
    if _extractor is None:
        _extractor = Agent(model=load_model(), system_prompt=EXTRACTION_PROMPT, tools=tools)
    return _extractor


def get_sow_grader():
    """SOW grader gets no Gateway access — it reads a document, nothing else."""
    global _sow_grader
    if _sow_grader is None:
        _sow_grader = Agent(
            model=load_model(fast=True),
            system_prompt=SOW_PROMPT,
            tools=[submit_sow_assessment],
        )
    return _sow_grader


def _decode_diagram(payload: dict):
    """Return a Strands image content block from a base64 diagram, or None."""
    raw = payload.get("diagram_base64")
    if not raw:
        return None
    fmt = (payload.get("diagram_format") or "png").lower().lstrip(".")
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in {"png", "jpeg", "gif", "webp"}:
        log.warning("Unsupported diagram format %r — skipping extraction", fmt)
        return None
    try:
        return {"image": {"format": fmt, "source": {"bytes": base64.b64decode(raw)}}}
    except Exception as exc:
        log.warning("Could not decode diagram: %s", exc)
        return None


def _normalise_payload(payload):
    """Unwrap the {"prompt": "<json>"} shape that `agentcore dev` produces."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {"prompt": payload}
    if "prompt" in payload and "description" not in payload:
        inner = payload["prompt"]
        if isinstance(inner, str):
            try:
                parsed = json.loads(inner)
                if isinstance(parsed, dict):
                    payload = parsed
            except (json.JSONDecodeError, TypeError):
                payload.setdefault("description", inner)
    return payload


@app.entrypoint
async def invoke(payload, context):
    """Run a POC validation. Streams phase progress, ends with a JSON result."""
    payload = _normalise_payload(payload)
    reset_state()

    description = payload.get("description", "")
    segment = payload.get("segment", "enterprise")
    industry = payload.get("industry", "generic")
    region = payload.get("region", "ap-south-1")
    services = payload.get("services") or []
    edges = [tuple(edge) for edge in (payload.get("edges") or [])]
    sow_text = payload.get("sow_text", "")
    confirmed = bool(payload.get("extraction_confirmed", False))

    actor_id = payload.get("partner_id") or payload.get("user_id") or "anonymous"
    session_id = f"poc-{actor_id}-{uuid.uuid4().hex[:12]}"

    session_manager = None
    try:
        session_manager = get_memory_session_manager(session_id, actor_id)
    except Exception as exc:
        log.warning("Memory unavailable (running without recall): %s", exc)

    # ── Phase 1: diagram extraction ──────────────────────────────────────────
    # Source diagrams parse exactly, so they skip both the model and the
    # confirmation gate. Only images need vision, and only vision needs a human
    # to check the result. See docs/decisions/0007.
    diagram_name = payload.get("diagram_filename", "")
    diagram_text = payload.get("diagram_text", "")
    if diagram_text and diagrams.is_deterministic(diagram_name or ".mmd"):
        yield "## Phase 1 · Parsing the diagram source\n\n"
        parsed = diagrams.parse(diagram_name or "diagram.mmd", diagram_text)
        if not services:
            services = parsed.services
        if not edges:
            edges = parsed.edges
        yield f"{parsed.notes}\n\n"
        if parsed.unmatched:
            yield (
                "**Not recognised, and therefore not included:** "
                + ", ".join(parsed.unmatched)
                + "\n\n"
            )

    image_block = _decode_diagram(payload)
    if image_block is not None:
        yield "## Phase 1 · Reading the diagram\n\n"
        try:
            extractor = get_extractor(session_manager=session_manager)
            message = [
                image_block,
                {
                    "text": "Identify every AWS service in this architecture diagram "
                    "and the connections between them, then call submit_extraction."
                },
            ]
            async for event in extractor.stream_async(message):
                if "data" in event and isinstance(event["data"], str):
                    yield event["data"]
        except Exception as exc:
            log.warning("Diagram extraction failed: %s", exc)
            yield f"\n\nDiagram extraction unavailable: {exc}\n"

        extraction = engine.extraction_from_raw(get_last_extraction())

        if not services:
            services = extraction.services
        if not edges:
            edges = extraction.edges

        if extraction.unmatched:
            yield (
                "\n\n**Not recognised:** "
                + ", ".join(extraction.unmatched)
                + " — confirm or correct these before the review runs.\n"
            )

        if REQUIRE_EXTRACTION_CONFIRMATION and not confirmed:
            # Correctness gate. Findings generated against a misread diagram
            # would describe a design the partner never proposed.
            yield (
                "\n\n---\n**Confirmation required.** Review the extraction below, "
                "then resubmit with `extraction_confirmed: true`.\n\n"
            )
            yield json.dumps(
                {
                    "status": "awaiting_confirmation",
                    "extraction": {
                        "services": extraction.services,
                        "edges": [list(edge) for edge in extraction.edges],
                        "unmatched": extraction.unmatched,
                        "notes": extraction.notes,
                    },
                },
                indent=2,
            )
            return

    if not services:
        yield json.dumps(
            {"status": "error", "message": "No services supplied and none extracted."}
        )
        return

    # ── Phase 4a: SOW banding (before validation so it can feed the report) ──
    sow_score = None
    if sow_text.strip():
        yield "\n\n---\n## Phase 4 · Scoring the Scope of Work\n\n"
        sow_score = sow.score_heuristic(sow_text)
        try:
            grader = get_sow_grader()
            grader_input = (
                "Criteria:\n"
                + json.dumps(sow.criteria_for_prompt(), indent=2)
                + "\n\nDocument:\n"
                + sow_text[:60000]
            )
            async for event in grader.stream_async(grader_input):
                if "data" in event and isinstance(event["data"], str):
                    yield event["data"]
            bands = get_last_sow_bands()
            if bands:
                sow_score = sow.apply_model_bands(sow_score, bands)
        except Exception as exc:
            log.warning("SOW model pass unavailable, using heuristic floor: %s", exc)
            yield f"\n\nModel grading unavailable — heuristic floor only ({exc}).\n"

    # ── Phases 2, 3, 5: deterministic ────────────────────────────────────────
    yield "\n\n---\n## Phases 2, 3 & 5 · Validation, pricing and recommendations\n\n"

    graph = engine.graph_from_selection(
        segment_id=segment,
        industry_id=industry,
        region=region,
        description=description,
        service_ids=services,
        edges=edges,
        overrides=payload.get("config_overrides") or {},
    )
    report = engine.validate(graph, sow_score)

    verdict, reasoning = report.verdict
    yield f"**{verdict}** — {reasoning}\n\n"

    result = {
        "status": "complete",
        "session_id": session_id,
        "verdict": {"result": verdict, "reasoning": reasoning},
        "counts": {
            severity.value: report.count(severity) for severity in Severity
        },
        "findings": [
            {
                "rule_id": finding.rule_id,
                "severity": finding.severity.value,
                "title": finding.title,
                "pillar": finding.pillar,
                "source": finding.source_label,
                "rationale": finding.rationale,
                "remediation": finding.remediation,
                "doc_url": finding.doc_url,
            }
            for finding in report.sorted_findings
        ],
        "conflicts": [
            {
                "attribute": conflict.attribute,
                "node": conflict.node_name,
                "segment_position": conflict.segment_position,
                "industry_position": conflict.industry_position,
                "resolution": conflict.resolution,
            }
            for conflict in report.conflicts
        ],
        "integrations": [
            {
                "from": edge.source,
                "to": edge.target,
                "type": edge.edge_type.value,
                "pattern": edge.pattern,
                "note": edge.note,
            }
            for edge in report.graph.edges
        ],
        "cost": {
            "baseline": report.cost.baseline,
            "compliance_premium": report.cost.premium,
            "total": report.cost.total,
            "currency": report.cost.currency,
            "region": report.cost.region,
            "as_of": report.cost.as_of,
            "lines": [dataclasses.asdict(line) for line in report.cost.lines],
        },
        "recommendations": [
            {
                "title": resource.title,
                "kind": resource.kind_label,
                "url": resource.url,
                "summary": resource.summary,
                "why": reason,
            }
            for resource, reason in report.recommendations
        ],
        "evidence": report.evidence,
        "gateway_available": get_mcp_client() is not None,
    }

    if sow_score is not None:
        result["sow"] = {
            "score": sow_score.total,
            "rating": sow_score.rating,
            "model_assisted": sow_score.model_assisted,
            "summary": sow_score.summary,
            "criteria": [
                {
                    "id": criterion.criterion_id,
                    "name": criterion.name,
                    "weight": criterion.weight,
                    "band": criterion.band,
                    "band_label": criterion.band_label,
                    "justification": criterion.justification,
                    "fix": criterion.gap_fix if criterion.is_gap else "",
                }
                for criterion in sow_score.scores
            ],
        }

    # ── Phase 6a: what-if pricing (optional, Code Interpreter) ──────────────
    # Only runs if the caller asks a question. See docs/decisions/0010 for
    # why this needs a model call this account's Marketplace restriction may
    # block, and why that's stated in the response rather than hidden.
    what_if_question = payload.get("what_if_question", "").strip()
    if what_if_question:
        yield "\n\n---\n## Phase 6a · What-if pricing\n\n"
        whatif = run_what_if(what_if_question, result["cost"]["lines"])
        if whatif["status"] == "unavailable":
            yield f"What-if pricing unavailable: {whatif['reason']}\n"
        else:
            yield "Ran a model-authored, sandbox-executed recomputation — see `what_if.code` in the result for exactly what ran.\n"
        result["what_if"] = whatif

    # ── Phase 6b: FAQ knowledge search (optional, Knowledge Base) ───────────
    # Only runs if the caller asks. See docs/decisions/0011 for why this is a
    # Knowledge Base rather than a Memory namespace.
    faq_query = payload.get("faq_query", "").strip()
    if faq_query:
        yield "\n\n---\n## Phase 6b · FAQ knowledge search\n\n"
        faq = search_faq(faq_query)
        if faq["status"] == "unavailable":
            yield f"FAQ search unavailable: {faq['reason']}\n"
        else:
            yield f"Found {len(faq['results'])} matching FAQ entries.\n"
        result["faq"] = faq

    yield json.dumps(result, indent=2)


if __name__ == "__main__":
    app.run()
