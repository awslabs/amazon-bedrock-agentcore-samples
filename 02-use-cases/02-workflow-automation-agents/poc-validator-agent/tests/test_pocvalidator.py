"""Tests for the deterministic core and the tool boundary.

All of these run with no AWS account, no network and no model. That is the point:
every part of this sample a reviewer would take at face value — findings,
arithmetic, source URLs, the AWS-only restriction — is verifiable offline.
"""

import os
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("POC_VALIDATOR_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from pocvalidator.core import catalog, chaining, diagrams, engine, resources, sow
from pocvalidator.core.models import EdgeType, Severity


def build(segment, industry, services, edges, overrides=None, sow_text=None):
    graph = engine.graph_from_selection(
        segment, industry, "ap-south-1", "test", services, edges, overrides or {}
    )
    score = sow.score_heuristic(sow_text) if sow_text else None
    return engine.validate(graph, score)


# ── Catalogue integrity ───────────────────────────────────────────────────────

def test_catalogues_load():
    assert len(catalog.service_defs()) >= 15
    assert len(catalog.integrations()) >= 30
    assert set(catalog.segments()) == {"enterprise", "smb", "digital_native"}
    assert set(catalog.industries()) == {"fsi", "retail", "generic"}


def test_every_rule_targets_a_known_attribute():
    known = set(catalog.attribute_defs())
    severities = {s.value for s in Severity}
    for pack in list(catalog.segments().values()) + list(catalog.industries().values()):
        for requirement in pack["requirements"]:
            assert requirement["attribute"] in known, requirement["id"]
            assert requirement["severity"].capitalize() in severities, requirement["id"]
            assert requirement["rationale"] and requirement["remediation"]


def test_every_integration_references_known_services():
    known = set(catalog.service_defs())
    for (source, target), entry in catalog.integrations().items():
        assert source in known and target in known
        assert entry["type"] in {"native", "glue", "anti_pattern"}


def test_every_priced_service_exists():
    assert set(catalog.pricing()["rates"]) <= set(catalog.service_defs())


# ── Chaining ──────────────────────────────────────────────────────────────────

def test_anti_pattern_is_critical():
    report = build("enterprise", "generic", ["apigateway", "rds_postgres"],
                   [("apigateway", "rds_postgres")])
    assert report.graph.edges[0].edge_type is EdgeType.ANTI_PATTERN
    assert any(f.severity is Severity.CRITICAL for f in report.findings)


def test_unknown_pair_is_unverified_never_native():
    """Silence must never read as approval."""
    report = build("smb", "generic", ["cognito", "kinesis"], [("cognito", "kinesis")])
    assert report.graph.edges[0].edge_type is EdgeType.UNVERIFIED


def test_glue_requirement_names_the_pattern():
    report = build("smb", "generic", ["lambda", "rds_postgres"],
                   [("lambda", "rds_postgres")])
    assert report.graph.edges[0].edge_type is EdgeType.GLUE
    assert "RDS Proxy" in report.graph.edges[0].pattern


def test_orphan_detection():
    report = build("smb", "generic", ["alb", "ec2", "s3"], [("alb", "ec2")])
    assert chaining.orphans(report.graph) == ["Amazon S3"]


# ── Rules and conflicts ───────────────────────────────────────────────────────

def test_fsi_demands_customer_managed_key():
    report = build("enterprise", "fsi", ["rds_postgres"], [])
    assert any(f.rule_id == "FSI-001" for f in report.findings)


def test_smb_not_penalised_for_single_az_but_enterprise_is():
    assert not any("Multi-AZ" in f.title
                   for f in build("smb", "generic", ["rds_postgres"], []).findings)
    assert any("Multi-AZ" in f.title
               for f in build("enterprise", "generic", ["rds_postgres"], []).findings)


def test_cost_sensitive_segment_surfaces_conflict_with_fsi():
    report = build("digital_native", "fsi", ["rds_postgres"], [])
    assert report.conflicts
    assert build("enterprise", "fsi", ["rds_postgres"], []).conflicts == []


# ── Pricing ───────────────────────────────────────────────────────────────────

def test_baseline_arithmetic_is_exact():
    report = build("smb", "generic", ["s3"], [])
    rates = catalog.pricing()["rates"]["s3"]
    usage = catalog.default_usage("s3")
    expected = round(usage["storage_gb"] * rates["storage_gb"]
                     + usage["requests_10k"] * rates["requests_10k"], 2)
    assert report.cost.baseline == pytest.approx(expected, abs=0.02)


def test_premium_totals_reconcile():
    report = build("enterprise", "fsi", ["rds_postgres"], [],
                   {"rds_postgres": {"multi_az": True, "customer_managed_key": True}})
    premium_lines = [line for line in report.cost.lines if line.is_premium]
    assert premium_lines
    assert report.cost.premium == pytest.approx(
        sum(line.monthly_cost for line in premium_lines), abs=0.01)
    assert report.cost.total == pytest.approx(
        report.cost.baseline + report.cost.premium, abs=0.01)


# ── Diagram extraction ────────────────────────────────────────────────────────

@pytest.mark.parametrize("label,expected", [
    ("RDS PostgreSQL", "rds_postgres"),
    ("Amazon RDS for PostgreSQL", "rds_postgres"),
    ("Application Load Balancer", "alb"),
    ("ALB", "alb"),
    ("API Gateway", "apigateway"),
    ("ECS Fargate", "ecs_fargate"),
    ("CloudFront", "cloudfront"),
])
def test_diagram_labels_resolve(label, expected):
    assert catalog.resolve_service(label) == expected


@pytest.mark.parametrize("label", ["MyCustomBox", "Widget", "Legacy Mainframe", ""])
def test_unknown_labels_return_none_rather_than_guessing(label):
    assert catalog.resolve_service(label) is None


def test_extraction_surfaces_unmatched_rather_than_dropping():
    extracted = engine.extraction_from_raw({
        "services": ["CloudFront", "ALB", "MysteryBox"],
        "edges": [{"from": "CloudFront", "to": "ALB"}],
    })
    assert extracted.services == ["cloudfront", "alb"]
    assert extracted.unmatched == ["MysteryBox"]
    assert extracted.edges == [("cloudfront", "alb")]


def test_extraction_drops_edges_to_unresolvable_nodes():
    extracted = engine.extraction_from_raw({
        "services": ["CloudFront"],
        "edges": [{"from": "CloudFront", "to": "MysteryBox"}],
    })
    assert extracted.edges == []


# ── Deterministic diagram parsing ─────────────────────────────────────────────

def _diagram(name):
    return (ROOT / "data" / "samples" / "diagrams" / name).read_bytes()


def test_mermaid_parses_exactly():
    result = diagrams.parse("fsi-loan-platform.mmd", _diagram("fsi-loan-platform.mmd"))
    assert result.services == ["cloudfront", "alb", "ecs_fargate", "rds_postgres",
                               "s3", "secretsmanager"]
    assert ("cloudfront", "alb") in result.edges
    assert ("ecs_fargate", "rds_postgres") in result.edges
    assert result.unmatched == []


def test_drawio_parses_and_reads_shape_style_when_label_is_empty():
    """An unnamed AWS shape still carries the service in resIcon=."""
    result = diagrams.parse("simple-webapp.drawio", _diagram("simple-webapp.drawio"))
    assert "s3" in result.services, "should recover S3 from the shape style"
    assert ("alb", "ec2") in result.edges


def test_drawio_surfaces_non_aws_shapes_rather_than_dropping():
    result = diagrams.parse("simple-webapp.drawio", _diagram("simple-webapp.drawio"))
    assert "Legacy Mainframe" in result.unmatched


def test_source_formats_are_deterministic_images_are_not():
    for name in ["a.drawio", "a.xml", "a.mmd", "a.mermaid"]:
        assert diagrams.is_deterministic(name)
    for name in ["a.png", "a.jpg", "a.pdf", "a.webp"]:
        assert not diagrams.is_deterministic(name)


def test_image_upload_is_routed_to_vision_not_parsed():
    result = diagrams.parse("architecture.png", b"\x89PNG\r\n")
    assert result.is_empty
    assert "confirmation" in result.notes


def test_malformed_diagram_sources_do_not_raise():
    assert diagrams.parse("x.drawio", b"<not xml").is_empty
    assert diagrams.parse("x.mmd", b"nothing here at all").is_empty


def test_parsed_diagram_feeds_a_real_review():
    """End to end: Mermaid source in, findings and cost out."""
    parsed = diagrams.parse("fsi-loan-platform.mmd", _diagram("fsi-loan-platform.mmd"))
    report = build("enterprise", "fsi", parsed.services, parsed.edges)
    assert report.findings
    assert report.cost.total > 0


def test_mermaid_round_trips_through_our_own_renderer():
    """The DOT we render and the Mermaid we parse describe the same graph."""
    parsed = diagrams.parse("fsi-loan-platform.mmd", _diagram("fsi-loan-platform.mmd"))
    report = build("smb", "generic", parsed.services, parsed.edges)
    dot = chaining.dot(report.graph)
    for service_id in parsed.services:
        assert service_id in dot


# ── SOW scoring ───────────────────────────────────────────────────────────────

def _sample(name):
    return (ROOT / "data" / "samples" / f"sample-sow-{name}.md").read_text(encoding="utf-8")


def test_sow_weights_sum_to_100():
    assert sum(c["weight"] for c in catalog.sow_criteria()["criteria"]) == 100


def test_sow_heuristic_discriminates_weak_from_strong():
    weak = sow.score_heuristic(_sample("weak"))
    strong = sow.score_heuristic(_sample("strong"))
    assert strong.total > weak.total + 25
    assert weak.rating == "Inadequate"
    assert strong.rating in {"Acceptable", "Strong"}


def test_sow_heuristic_reports_itself_as_unassisted():
    assert sow.score_heuristic(_sample("strong")).model_assisted is False


def test_empty_sow_scores_zero():
    assert sow.score_heuristic("").total == 0.0


def test_model_bands_override_and_total_is_recomputed():
    score = sow.score_heuristic(_sample("weak"))
    before = score.total
    sow.apply_model_bands(score, {c["id"]: {"band": 4, "justification": "x"}
                                  for c in catalog.sow_criteria()["criteria"]})
    assert score.model_assisted is True
    assert score.total == 100.0 and score.total > before


def test_invalid_model_bands_are_ignored_not_trusted():
    score = sow.score_heuristic(_sample("weak"))
    baseline = score.total
    sow.apply_model_bands(score, {"NOT-A-CRITERION": {"band": 4},
                                  "SOW-01": {"band": 99},
                                  "SOW-02": {"band": "high"}})
    assert score.total == baseline


def test_criteria_for_prompt_withholds_weights():
    for item in sow.criteria_for_prompt():
        assert set(item) == {"id", "name", "question"}


def test_toc_line_is_detected_and_real_section_is_not():
    # Word's tab-stop TOC fields render as plain text as "<title>\t<page number>".
    text_lower = "out of scope\t6\nexecutive summary\nfiller.\n\nout of scope\nreal detail.\n"
    toc_idx = text_lower.find("out of scope")
    real_idx = text_lower.find("out of scope", toc_idx + 1)
    assert sow._is_toc_occurrence(text_lower, toc_idx) is True
    assert sow._is_toc_occurrence(text_lower, real_idx) is False


def test_heuristic_scores_the_real_section_not_the_toc_entry():
    # Regression test: a keyword's first occurrence is very often a Table of
    # Contents line repeating the section title, not the section itself. The
    # window used to score substance must come from the real section even
    # though it appears later in the document than the ToC line does.
    text = (
        "Out of Scope\t6\n"
        "Executive Summary\n"
        "This filler sentence near the top of the document is unrelated to the "
        "real exclusions and must not be what gets measured for substance.\n"
        "\n"
        "Out of Scope\n"
        "Custom mobile app development, on-premises hardware procurement, "
        "third-party vendor integrations, production support beyond hypercare, "
        "and anything not explicitly listed as an in-scope deliverable earlier "
        "in this statement of work document, are all excluded from this "
        "engagement and remain the customer's responsibility throughout.\n"
    )
    score = sow.score_heuristic(text)
    out_of_scope = next(s for s in score.scores if s.criterion_id == "SOW-03")
    assert out_of_scope.band >= 2, out_of_scope.justification


# ── AWS-only recommendations ──────────────────────────────────────────────────

def test_no_catalogue_entry_is_rejected_by_the_allowlist():
    """A non-AWS URL in the catalogue must fail here, not reach a partner."""
    assert resources.rejected() == ()


def test_every_recommendation_url_is_aws_owned():
    for resource in resources.all_resources():
        assert resources.is_allowed(resource.url), resource.url


@pytest.mark.parametrize("url", [
    "https://medium.com/@someone/aws-tips",
    "https://stackoverflow.com/questions/1",
    "http://aws.amazon.com/blogs/",                 # http, not https
    "https://youtube.com/@RandomCloudGuy",          # YouTube, wrong channel
    "https://aws.amazon.com.evil.example/blogs/",   # lookalike host
])
def test_disallowed_urls_are_rejected(url):
    assert resources.is_allowed(url) is False


@pytest.mark.parametrize("url", [
    "https://aws.amazon.com/blogs/architecture/",
    "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html",
    "https://www.youtube.com/@AWSEventsChannel",
    "https://calculator.aws/",
])
def test_allowed_urls_pass(url):
    assert resources.is_allowed(url) is True


def test_recommendations_are_relevant_and_explained():
    report = build("enterprise", "fsi", ["rds_postgres", "s3", "lambda"],
                   [("lambda", "rds_postgres")])
    assert report.recommendations
    for resource, reason in report.recommendations:
        assert reason, resource.id
        assert resources.is_allowed(resource.url)


def test_industry_changes_the_recommendations():
    fsi = {r.id for r, _ in build("enterprise", "fsi", ["rds_postgres"], []).recommendations}
    retail = {r.id for r, _ in build("enterprise", "retail", ["rds_postgres"], []).recommendations}
    assert fsi != retail


def test_sow_submission_adds_partner_practice_reading():
    without = {r.id for r, _ in build("smb", "generic", ["s3"], []).recommendations}
    with_sow = {r.id for r, _ in build("smb", "generic", ["s3"], [],
                                       sow_text=_sample("strong")).recommendations}
    assert with_sow - without


# ── Tool boundary ─────────────────────────────────────────────────────────────

def test_structured_output_tools_record_and_reset():
    sys.path.insert(0, str(ROOT / "app" / "pocvalidator"))
    from tools import structured_output as so

    so.reset_state()
    so.record_extraction('["CloudFront"]', '[{"from":"CloudFront","to":"ALB"}]', "note")
    assert so.get_last_extraction()["services"] == ["CloudFront"]

    so.record_sow_assessment('[{"id":"SOW-01","band":3,"justification":"ok"},'
                             '{"id":"SOW-02","band":9}]')
    bands = so.get_last_sow_bands()
    assert bands["SOW-01"]["band"] == 3
    assert "SOW-02" not in bands, "out-of-range band must be rejected, not clamped"

    so.reset_state()
    assert so.get_last_extraction() == {} and so.get_last_sow_bands() == {}


def test_malformed_tool_payloads_do_not_raise():
    sys.path.insert(0, str(ROOT / "app" / "pocvalidator"))
    from tools import structured_output as so

    so.reset_state()
    so.record_extraction("not json", "also not json")
    assert so.get_last_extraction()["services"] == []
    assert "Could not parse" in so.record_sow_assessment("{}")


# ── Config discipline ─────────────────────────────────────────────────────────

def test_env_vars_are_only_read_in_config():
    """ADR 0011 in the reference sample: all env reads in one module."""
    offenders = []
    for path in (ROOT / "app" / "pocvalidator").rglob("*.py"):
        if path.name in {"config.py", "catalog.py"}:
            continue
        if "os.getenv" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"env reads outside config.py: {offenders}"


# ── Examples ──────────────────────────────────────────────────────────────────

def test_all_examples_validate():
    verdicts = {"Ready", "Conditionally ready", "Needs work", "Not ready"}
    for example in catalog.examples():
        report = build(example["segment"], example["industry"], example["services"],
                       [tuple(e) for e in example["edges"]], example.get("config") or {})
        assert report.cost.total > 0, example["id"]
        assert report.verdict[0] in verdicts, example["id"]


def test_broken_example_actually_fails():
    broken = next(e for e in catalog.examples() if e["id"] == "broken_design")
    report = build(broken["segment"], broken["industry"], broken["services"],
                   [tuple(e) for e in broken["edges"]])
    assert report.verdict[0] == "Not ready"
    assert report.count(Severity.CRITICAL) >= 3


# ── AgentCore configuration ───────────────────────────────────────────────────
#
# These read agentcore.json.template, not agentcore.json: the latter is
# gitignored (it's populated with real account/ARN values by whoever is
# actively deploying) and simply does not exist on a fresh clone, which is
# exactly the environment CI runs these tests in. The template is what
# actually ships in the repo, and its structure is identical to the real
# file — only the account id / ARN / pool id fields are placeholders — so
# every schema assertion below holds equally well against it.

def test_agentcore_json_is_valid_and_uses_the_current_cli_schema():
    import json
    config = json.loads((ROOT / "agentcore" / "agentcore.json.template").read_text())
    for key in ("runtimes", "memories", "agentCoreGateways", "policyEngines",
                "evaluators", "onlineEvalConfigs", "credentials"):
        assert key in config, key
    assert config["runtimes"][0]["entrypoint"] == "main.py"
    assert not (ROOT / ".bedrock_agentcore.yaml").exists(), \
        "Starter Toolkit config is deprecated and penalised in the use-case rubric"


def test_agentcore_json_matches_the_cli_schema():
    """Field shapes verified against @aws/agentcore's own zod schema.

    Every one of these was wrong on the first attempt and only surfaced by
    running `agentcore validate`, so they are pinned here.
    """
    import json
    config = json.loads((ROOT / "agentcore" / "agentcore.json.template").read_text())

    # managedBy accepts exactly one value.
    assert config["managedBy"] == "CDK"

    target = config["agentCoreGateways"][0]["targets"][0]
    # Real Lambda-backed target (wraps the official AWS Documentation MCP
    # server), not the placeholder mcpServer/endpoint the sample shipped with.
    assert target["targetType"] == "lambdaFunctionArn"
    assert "lambdaFunctionArn" in target
    assert target["lambdaFunctionArn"]["lambdaArn"].startswith("arn:aws:lambda:")
    assert target["lambdaFunctionArn"]["toolSchemaFile"].endswith(".json")
    # lambdaFunctionArn targets are invoked over IAM; no outboundAuth block.
    assert "outboundAuth" not in target


def test_aws_targets_template_is_a_bare_array():
    """The schema is a top-level array, not an object with a `targets` key."""
    import json
    template = json.loads(
        (ROOT / "agentcore" / "aws-targets.json.template").read_text()
    )
    assert isinstance(template, list)
    assert {"name", "account", "region"} <= set(template[0])


def test_no_hardcoded_account_ids_or_arns():
    """Scans exactly what would be committed, not a developer's live local state.

    `agentcore.json` and `aws-targets.json` are gitignored on purpose: a real
    deployment populates them with a real account id/ARNs, and that is
    correct and expected on disk for whoever is actively deploying. The
    `.template` counterparts are what actually ships in the repo and must
    stay placeholder-only, so those are what this test checks instead.
    """
    import re
    pattern = re.compile(r"\b\d{12}\b|arn:aws:[a-z0-9-]+:[a-z0-9-]*:\d{12}:")
    skip_dirs = {".git", "__pycache__", ".pytest_cache", "node_modules", "cdk.out", "dist", ".cli"}
    skip_files = {"agentcore.json", "aws-targets.json", ".cognito-state.json"}
    for path in list(ROOT.rglob("*.py")) + list(ROOT.rglob("*.json")) + list(ROOT.rglob("*.yaml")):
        if any(part in skip_dirs for part in path.parts) or path.name in skip_files:
            continue
        assert not pattern.search(path.read_text(encoding="utf-8", errors="ignore")), path


def test_ui_and_agent_dependencies_are_separate():
    """bedrock-agentcore and streamlit cannot share a virtualenv."""
    def pins(path):
        return [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    agent = pins(ROOT / "app" / "pocvalidator" / "requirements.txt")
    ui = pins(ROOT / "ui" / "requirements.txt")
    assert not any(line.startswith("streamlit") for line in agent)
    assert not any(line.startswith("bedrock-agentcore") for line in ui)
