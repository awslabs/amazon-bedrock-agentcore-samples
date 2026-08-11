"""Tests for the deterministic core and the tool boundary.

All of these run with no AWS account, no network and no model. That is the point:
every part of this sample a reviewer would take at face value — findings,
arithmetic, source URLs, the AWS-only restriction — is verifiable offline.
"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("POC_VALIDATOR_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from pocvalidator.core import (
    catalog,
    chaining,
    diagrams,
    engine,
    pricing,
    resources,
    rules,
    sow,
)
from pocvalidator.core.models import EdgeType, Node, Severity


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


def test_service_choices_lists_every_service_sorted_by_category_then_name():
    choices = catalog.service_choices()
    assert len(choices) == len(catalog.service_defs())
    categories = [catalog.service_defs()[sid]["category"] for sid, _ in choices]
    assert categories == sorted(categories)


def test_resolve_service_matches_via_short_name_substring():
    """Neither an exact id nor a full-name match: "postgres" is a substring of
    the trimmed RDS PostgreSQL name, resolved before the token-overlap
    fallback ever runs."""
    assert catalog.resolve_service("postgres") == "rds_postgres"


def test_resolve_service_returns_none_when_only_filler_words_remain():
    """After filler words ("aws", "service") are stripped there are no
    meaningful tokens left to score, so this must return None without
    reaching the token-overlap loop at all."""
    assert catalog.resolve_service("AWS Service") is None


# ── Chaining ──────────────────────────────────────────────────────────────────


def test_anti_pattern_is_critical():
    report = build(
        "enterprise",
        "generic",
        ["apigateway", "rds_postgres"],
        [("apigateway", "rds_postgres")],
    )
    assert report.graph.edges[0].edge_type is EdgeType.ANTI_PATTERN
    assert any(f.severity is Severity.CRITICAL for f in report.findings)


def test_unknown_pair_is_unverified_never_native():
    """Silence must never read as approval."""
    report = build("smb", "generic", ["cognito", "kinesis"], [("cognito", "kinesis")])
    assert report.graph.edges[0].edge_type is EdgeType.UNVERIFIED


def test_glue_requirement_names_the_pattern():
    report = build(
        "smb", "generic", ["lambda", "rds_postgres"], [("lambda", "rds_postgres")]
    )
    assert report.graph.edges[0].edge_type is EdgeType.GLUE
    assert "RDS Proxy" in report.graph.edges[0].pattern


def test_orphan_detection():
    report = build("smb", "generic", ["alb", "ec2", "s3"], [("alb", "ec2")])
    assert chaining.orphans(report.graph) == ["Amazon S3"]


def test_mermaid_renders_node_labels_and_edge_style():
    report = build(
        "enterprise",
        "generic",
        ["apigateway", "rds_postgres"],
        [("apigateway", "rds_postgres")],
    )
    rendered = chaining.mermaid(report.graph)
    assert "graph LR" in rendered
    assert "Amazon API Gateway" in rendered
    assert "BROKEN" in rendered  # anti-pattern edge style


def test_dot_notes_when_the_graph_has_no_edges():
    report = build("smb", "generic", ["s3"], [])
    assert "No connections defined" in chaining.dot(report.graph)


# ── Rules and conflicts ───────────────────────────────────────────────────────


def test_fsi_demands_customer_managed_key():
    report = build("enterprise", "fsi", ["rds_postgres"], [])
    assert any(f.rule_id == "FSI-001" for f in report.findings)


def test_smb_not_penalised_for_single_az_but_enterprise_is():
    assert not any(
        "Multi-AZ" in f.title
        for f in build("smb", "generic", ["rds_postgres"], []).findings
    )
    assert any(
        "Multi-AZ" in f.title
        for f in build("enterprise", "generic", ["rds_postgres"], []).findings
    )


def test_cost_sensitive_segment_surfaces_conflict_with_fsi():
    report = build("digital_native", "fsi", ["rds_postgres"], [])
    assert report.conflicts
    assert build("enterprise", "fsi", ["rds_postgres"], []).conflicts == []


def test_applies_matches_by_explicit_service_id_scope():
    """No shipped rule pack uses "services" in applies_to (all use
    "categories"), but the schema supports targeting one exact service."""
    node = Node(
        service_id="s3", name="Amazon S3", category="storage", doc_url="https://x"
    )
    assert rules._applies({"applies_to": {"services": ["s3"]}}, node) is True


def test_applies_matches_a_service_id_listed_under_categories_as_a_convenience():
    node = Node(
        service_id="s3", name="Amazon S3", category="storage", doc_url="https://x"
    )
    assert rules._applies({"applies_to": {"categories": ["s3"]}}, node) is True


def test_satisfied_supports_the_max_operator():
    node = Node(
        service_id="ec2",
        name="Amazon EC2",
        category="compute",
        doc_url="x",
        config={"instance_hours": 100},
    )
    assert (
        rules._satisfied(
            {"attribute": "instance_hours", "operator": "max", "value": 200}, node
        )
        is True
    )
    assert (
        rules._satisfied(
            {"attribute": "instance_hours", "operator": "max", "value": 50}, node
        )
        is False
    )


def test_satisfied_raises_on_an_unknown_operator():
    node = Node(
        service_id="ec2",
        name="Amazon EC2",
        category="compute",
        doc_url="x",
        config={"instance_hours": 100},
    )
    with pytest.raises(ValueError, match="Unknown operator"):
        rules._satisfied(
            {"attribute": "instance_hours", "operator": "bogus", "value": 1}, node
        )


def test_title_names_the_must_be_disabled_case():
    node = Node(service_id="s3", name="Amazon S3", category="storage", doc_url="x")
    title = rules._title({"attribute": "public_access", "value": False}, node)
    assert "must be disabled" in title


def test_title_falls_back_to_generic_phrasing_for_a_non_boolean_expected_value():
    """Only min/true/false show up in the shipped rule packs, but the schema
    allows an arbitrary expected value under the default "equals" operator."""
    node = Node(service_id="s3", name="Amazon S3", category="storage", doc_url="x")
    title = rules._title({"attribute": "log_retention_days", "value": 90}, node)
    assert title.endswith("must be 90 on Amazon S3")


def test_conflict_dedup_skips_a_repeated_attribute_service_pair(monkeypatch):
    """Two requirements in the same industry pack targeting the same attribute
    on the same node must surface one conflict, not two — no shipped pack has
    a duplicate rule like this, so it is injected here."""
    duplicate_industry = {
        "id": "fsi",
        "name": "Financial Services",
        "requirements": [
            {
                "id": "FSI-DUP-1",
                "applies_to": {"categories": ["database"]},
                "attribute": "customer_managed_key",
                "operator": "equals",
                "value": True,
                "severity": "critical",
            },
            {
                "id": "FSI-DUP-2",
                "applies_to": {"categories": ["database"]},
                "attribute": "customer_managed_key",
                "operator": "equals",
                "value": True,
                "severity": "critical",
            },
        ],
    }
    monkeypatch.setattr(catalog, "industries", lambda: {"fsi": duplicate_industry})
    graph = engine.graph_from_selection(
        "digital_native", "fsi", "ap-south-1", "test", ["rds_postgres"], []
    )
    assert len(rules.detect_conflicts(graph)) == 1


# ── Pricing ───────────────────────────────────────────────────────────────────


def test_baseline_arithmetic_is_exact():
    report = build("smb", "generic", ["s3"], [])
    rates = catalog.pricing()["rates"]["s3"]
    usage = catalog.default_usage("s3")
    expected = round(
        usage["storage_gb"] * rates["storage_gb"]
        + usage["requests_10k"] * rates["requests_10k"],
        2,
    )
    assert report.cost.baseline == pytest.approx(expected, abs=0.02)


def test_premium_totals_reconcile():
    report = build(
        "enterprise",
        "fsi",
        ["rds_postgres"],
        [],
        {"rds_postgres": {"multi_az": True, "customer_managed_key": True}},
    )
    premium_lines = [line for line in report.cost.lines if line.is_premium]
    assert premium_lines
    assert report.cost.premium == pytest.approx(
        sum(line.monthly_cost for line in premium_lines), abs=0.01
    )
    assert report.cost.total == pytest.approx(
        report.cost.baseline + report.cost.premium, abs=0.01
    )


def test_baseline_line_is_skipped_when_a_usage_key_has_no_matching_rate():
    """A usage driver with no price in pricing.yaml (e.g. a hand-edited what-if
    scenario) must be skipped, not crash the baseline calculation."""
    graph = engine.build_graph(
        "smb",
        "generic",
        "ap-south-1",
        "test",
        {"s3": {"config": {}, "usage": {"storage_gb": 100, "made_up_driver": 5}}},
        [],
    )
    cost = pricing.estimate(graph)
    assert not any(line.driver == "made_up_driver" for line in cost.lines)


def test_premium_flat_control_skipped_when_the_costing_spec_is_missing():
    """A control the node has turned on but whose cost spec is absent or not
    flat_monthly must be skipped rather than crash the estimate."""
    node = Node(
        service_id="s3",
        name="Amazon S3",
        category="storage",
        doc_url="x",
        config={"waf_enabled": True},
    )
    assert (
        pricing._premium_lines(node, {}, {"waf_enabled": {"basis": "multiplier"}}) == []
    )


def test_backup_retention_beyond_the_free_allocation_is_priced():
    report = build(
        "enterprise",
        "fsi",
        ["rds_postgres"],
        [],
        {"rds_postgres": {"backup_retention_days": 30}},
    )
    retention_lines = [
        l for l in report.cost.lines if l.driver == "backup_retention_days"
    ]
    assert retention_lines
    assert retention_lines[0].is_premium


def test_backup_retention_beyond_the_free_allocation_but_no_storage_usage_is_skipped():
    """Retention beyond the free window only produces a cost line when there is
    metered storage to multiply against; zero storage must skip cleanly rather
    than price a phantom line."""
    graph = engine.build_graph(
        "enterprise",
        "fsi",
        "ap-south-1",
        "test",
        {
            "rds_postgres": {
                "config": {"backup_retention_days": 30},
                "usage": {"storage_gb": 0},
            }
        },
        [],
    )
    cost = pricing.estimate(graph)
    assert not any(line.driver == "backup_retention_days" for line in cost.lines)


# ── Diagram extraction ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "label,expected",
    [
        ("RDS PostgreSQL", "rds_postgres"),
        ("Amazon RDS for PostgreSQL", "rds_postgres"),
        ("Application Load Balancer", "alb"),
        ("ALB", "alb"),
        ("API Gateway", "apigateway"),
        ("ECS Fargate", "ecs_fargate"),
        ("CloudFront", "cloudfront"),
    ],
)
def test_diagram_labels_resolve(label, expected):
    assert catalog.resolve_service(label) == expected


@pytest.mark.parametrize("label", ["MyCustomBox", "Widget", "Legacy Mainframe", ""])
def test_unknown_labels_return_none_rather_than_guessing(label):
    assert catalog.resolve_service(label) is None


def test_extraction_surfaces_unmatched_rather_than_dropping():
    extracted = engine.extraction_from_raw(
        {
            "services": ["CloudFront", "ALB", "MysteryBox"],
            "edges": [{"from": "CloudFront", "to": "ALB"}],
        }
    )
    assert extracted.services == ["cloudfront", "alb"]
    assert extracted.unmatched == ["MysteryBox"]
    assert extracted.edges == [("cloudfront", "alb")]


def test_extraction_drops_edges_to_unresolvable_nodes():
    extracted = engine.extraction_from_raw(
        {
            "services": ["CloudFront"],
            "edges": [{"from": "CloudFront", "to": "MysteryBox"}],
        }
    )
    assert extracted.edges == []


def test_extraction_accepts_tuple_edges_and_skips_malformed_ones():
    """Edges may arrive as {"from": .., "to": ..} dicts (typical model output)
    or as plain (from, to) pairs; anything else is dropped rather than
    raising, matching the tool's promise never to crash on a bad payload."""
    extracted = engine.extraction_from_raw(
        {
            "services": ["CloudFront", "ALB"],
            "edges": [("CloudFront", "ALB"), "not-a-valid-edge", ["only-one"]],
        }
    )
    assert extracted.edges == [("cloudfront", "alb")]


# ── Deterministic diagram parsing ─────────────────────────────────────────────


def _diagram(name):
    return (ROOT / "data" / "samples" / "diagrams" / name).read_bytes()


def test_mermaid_parses_exactly():
    result = diagrams.parse("fsi-loan-platform.mmd", _diagram("fsi-loan-platform.mmd"))
    assert result.services == [
        "cloudfront",
        "alb",
        "ecs_fargate",
        "rds_postgres",
        "s3",
        "secretsmanager",
    ]
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


def test_drawio_decompresses_the_default_compressed_diagram_format():
    """draw.io stores diagrams deflate-compressed and base64-encoded by
    default; the uncompressed sample fixture never exercises that path, or
    its malformed-payload and malformed-XML-after-decompression branches, so
    all three are built here."""
    import base64
    import urllib.parse
    import zlib

    def _compress(xml_text):
        quoted = urllib.parse.quote(xml_text)
        compressor = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
        data = compressor.compress(quoted.encode("utf-8")) + compressor.flush()
        return base64.b64encode(data).decode("ascii")

    invalid_payload = _compress("not valid xml <<<")
    valid_inner = (
        '<root><mxCell id="0"/>'
        '<mxCell id="2" value="ALB" vertex="1"/>'
        '<mxCell id="3" value="EC2" vertex="1"/>'
        '<mxCell id="10" edge="1" source="2" target="3"/></root>'
    )
    valid_payload = _compress(valid_inner)
    outer_xml = f"""<mxfile host="app.diagrams.net">
  <diagram name="Bad">abc</diagram>
  <diagram name="Invalid">{invalid_payload}</diagram>
  <diagram name="Good">{valid_payload}</diagram>
</mxfile>"""

    result = diagrams.parse_drawio(outer_xml)
    assert result.services == ["alb", "ec2"]
    assert result.edges == [("alb", "ec2")]


def test_drawio_without_any_mxcell_elements_reports_notes():
    result = diagrams.parse_drawio("<mxGraphModel><root></root></mxGraphModel>")
    assert result.is_empty
    assert "mxCell" in result.notes


def test_drawio_skips_a_vertex_with_no_label_and_no_aws_shape_style():
    xml = (
        "<mxGraphModel><root>"
        '<mxCell id="0"/>'
        '<mxCell id="2" value="" style="rounded=1;" vertex="1"/>'
        '<mxCell id="3" value="EC2" '
        'style="shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.ec2;" vertex="1"/>'
        "</root></mxGraphModel>"
    )
    result = diagrams.parse_drawio(xml)
    assert result.services == ["ec2"]
    assert result.unmatched == []


def test_drawio_notes_a_connector_dropped_to_an_unlabelled_shape():
    xml = (
        "<mxGraphModel><root>"
        '<mxCell id="0"/>'
        '<mxCell id="2" value="ALB" vertex="1"/>'
        '<mxCell id="10" edge="1" source="2" target="99"/>'
        "</root></mxGraphModel>"
    )
    result = diagrams.parse_drawio(xml)
    assert "connector" in result.notes


def test_mermaid_skips_subgraph_boundary_lines():
    """ "subgraph ..." and its closing "end" line are structural noise, not
    nodes or edges, and must be skipped rather than mistaken for either."""
    result = diagrams.parse_mermaid(
        "graph LR\nsubgraph Group\nA[ALB]\nB[EC2]\nA --> B\nend\n"
    )
    assert result.services == ["alb", "ec2"]


def test_mermaid_bare_ids_without_brackets_use_the_id_as_the_label():
    result = diagrams.parse_mermaid("graph LR\nALB --> EC2\n")
    assert result.services == ["alb", "ec2"]
    assert result.edges == [("alb", "ec2")]


def test_markdown_source_extracts_a_fenced_mermaid_block():
    result = diagrams.parse(
        "design.md",
        "# Notes\n\n```mermaid\ngraph LR\nA[ALB]\nB[EC2]\nA --> B\n```\n\nMore text.",
    )
    assert result.services == ["alb", "ec2"]


def test_text_source_without_a_fence_is_parsed_as_mermaid_directly():
    result = diagrams.parse("notes.txt", "graph LR\nA[ALB]\nB[EC2]\nA --> B\n")
    assert result.services == ["alb", "ec2"]


# ── SOW scoring ───────────────────────────────────────────────────────────────


def _sample(name):
    return (ROOT / "data" / "samples" / f"sample-sow-{name}.md").read_text(
        encoding="utf-8"
    )


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
    sow.apply_model_bands(
        score,
        {
            c["id"]: {"band": 4, "justification": "x"}
            for c in catalog.sow_criteria()["criteria"]
        },
    )
    assert score.model_assisted is True
    assert score.total == 100.0 and score.total > before


def test_invalid_model_bands_are_ignored_not_trusted():
    score = sow.score_heuristic(_sample("weak"))
    baseline = score.total
    sow.apply_model_bands(
        score,
        {
            "NOT-A-CRITERION": {"band": 4},
            "SOW-01": {"band": 99},
            "SOW-02": {"band": "high"},
        },
    )
    assert score.total == baseline


def test_criteria_for_prompt_withholds_weights():
    for item in sow.criteria_for_prompt():
        assert set(item) == {"id", "name", "question"}


def test_toc_line_is_detected_and_real_section_is_not():
    # Word's tab-stop TOC fields render as plain text as "<title>\t<page number>".
    text_lower = (
        "out of scope\t6\nexecutive summary\nfiller.\n\nout of scope\nreal detail.\n"
    )
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


def test_toc_detection_handles_the_final_line_with_no_trailing_newline():
    """The occurrence sits on the last line of the document, so find("\\n", idx)
    returns -1 and the line-end boundary must fall back to the string length."""
    text_lower = "some filler text\nout of scope\t6"
    idx = text_lower.find("out of scope")
    assert sow._is_toc_occurrence(text_lower, idx) is True


def test_heuristic_band_rewards_a_single_signal_in_a_substantial_section():
    """Exactly one signal ("raci") but a long surrounding section still lifts
    the band above bare mention — a branch distinct from the multi-signal
    cases the other SOW tests exercise."""
    text = "RACI " + "x " * 300
    score = sow.score_heuristic(text)
    roles = next(s for s in score.scores if s.criterion_id == "SOW-08")
    assert roles.band == 2
    assert "substantial section" in roles.justification


def test_total_is_zero_with_no_criteria_at_all():
    """A SOWScore built with no criteria (not just neutral bands) must
    short-circuit to 0.0 rather than divide by zero."""
    assert sow.SOWScore(scores=[]).total == 0.0


def test_rating_reaches_strong_at_full_marks():
    score = sow.score_heuristic("")
    sow.apply_model_bands(
        score,
        {
            c["id"]: {"band": 4, "justification": "x"}
            for c in catalog.sow_criteria()["criteria"]
        },
    )
    assert score.rating == "Strong"


def test_rating_lands_on_weak_at_half_marks():
    score = sow.score_heuristic("")
    sow.apply_model_bands(
        score,
        {
            c["id"]: {"band": 2, "justification": "x"}
            for c in catalog.sow_criteria()["criteria"]
        },
    )
    assert score.total == 50.0
    assert score.rating == "Weak"


def test_summary_names_the_largest_gap():
    score = sow.score_heuristic(_sample("weak"))
    assert "below Adequate" in score.summary


def test_summary_reports_no_material_gaps_once_every_criterion_passes():
    score = sow.score_heuristic("")
    sow.apply_model_bands(
        score,
        {
            c["id"]: {"band": 4, "justification": "x"}
            for c in catalog.sow_criteria()["criteria"]
        },
    )
    assert (
        score.summary == "No material gaps. Every criterion scored Adequate or better."
    )


# ── AWS-only recommendations ──────────────────────────────────────────────────


def test_no_catalogue_entry_is_rejected_by_the_allowlist():
    """A non-AWS URL in the catalogue must fail here, not reach a partner."""
    assert resources.rejected() == ()


def test_every_recommendation_url_is_aws_owned():
    for resource in resources.all_resources():
        assert resources.is_allowed(resource.url), resource.url


@pytest.mark.parametrize(
    "url",
    [
        "https://medium.com/@someone/aws-tips",
        "https://stackoverflow.com/questions/1",
        "http://aws.amazon.com/blogs/",  # http, not https
        "https://youtube.com/@RandomCloudGuy",  # YouTube, wrong channel
        "https://aws.amazon.com.evil.example/blogs/",  # lookalike host
    ],
)
def test_disallowed_urls_are_rejected(url):
    assert resources.is_allowed(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "https://aws.amazon.com/blogs/architecture/",
        "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html",
        "https://www.youtube.com/@AWSEventsChannel",
        "https://calculator.aws/",
    ],
)
def test_allowed_urls_pass(url):
    assert resources.is_allowed(url) is True


def test_recommendations_are_relevant_and_explained():
    report = build(
        "enterprise",
        "fsi",
        ["rds_postgres", "s3", "lambda"],
        [("lambda", "rds_postgres")],
    )
    assert report.recommendations
    for resource, reason in report.recommendations:
        assert reason, resource.id
        assert resources.is_allowed(resource.url)


def test_industry_changes_the_recommendations():
    fsi = {
        r.id
        for r, _ in build("enterprise", "fsi", ["rds_postgres"], []).recommendations
    }
    retail = {
        r.id
        for r, _ in build("enterprise", "retail", ["rds_postgres"], []).recommendations
    }
    assert fsi != retail


def test_sow_submission_adds_partner_practice_reading():
    without = {r.id for r, _ in build("smb", "generic", ["s3"], []).recommendations}
    with_sow = {
        r.id
        for r, _ in build(
            "smb", "generic", ["s3"], [], sow_text=_sample("strong")
        ).recommendations
    }
    assert with_sow - without


def test_resource_kind_label_maps_to_a_human_readable_string():
    resource = resources.all_resources()[0]
    assert resource.kind_label == resources.KIND_LABEL[resource.kind]


def test_is_allowed_returns_false_rather_than_raising_on_a_malformed_url():
    """urlparse raises ValueError on some malformed netlocs (e.g. an
    unterminated IPv6 host); a resource URL that fails to parse must be
    rejected, not crash the recommender."""
    assert resources.is_allowed("https://[::1") is False


def test_partition_drops_and_records_a_disallowed_catalogue_url(monkeypatch):
    """Exercises the rejection branch directly: the shipped catalogue is
    clean (see test_no_catalogue_entry_is_rejected_by_the_allowlist above), so
    a bad entry has to be injected to prove the drop path itself works."""
    monkeypatch.setattr(
        catalog,
        "resources_raw",
        lambda: {
            "resources": [
                {
                    "id": "bad-1",
                    "title": "Not AWS",
                    "kind": "blog",
                    "url": "https://medium.com/not-aws",
                    "summary": "x",
                    "tags": [],
                },
            ]
        },
    )
    resources._partition.cache_clear()
    try:
        assert resources.rejected() == (
            {"id": "bad-1", "url": "https://medium.com/not-aws"},
        )
        assert resources.all_resources() == ()
    finally:
        resources._partition.cache_clear()


# ── Report model ─────────────────────────────────────────────────────────


def test_sorted_findings_orders_by_severity_then_node_name():
    report = build("enterprise", "fsi", ["rds_postgres"], [])
    ranks = [f.severity.rank for f in report.sorted_findings]
    assert ranks == sorted(ranks)


def test_verdict_is_conditionally_ready_with_high_but_no_critical_findings():
    report = build("enterprise", "generic", ["rds_postgres"], [])
    assert report.count(Severity.CRITICAL) == 0
    assert report.count(Severity.HIGH) >= 1
    assert report.verdict[0] == "Conditionally ready"


# ── Tool boundary ─────────────────────────────────────────────────────────────


def test_structured_output_tools_record_and_reset():
    sys.path.insert(0, str(ROOT / "app" / "pocvalidator"))
    from tools import structured_output as so

    so.reset_state()
    so.record_extraction('["CloudFront"]', '[{"from":"CloudFront","to":"ALB"}]', "note")
    assert so.get_last_extraction()["services"] == ["CloudFront"]

    so.record_sow_assessment(
        '[{"id":"SOW-01","band":3,"justification":"ok"},{"id":"SOW-02","band":9}]'
    )
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


def test_whatif_code_tool_records_and_resets():
    """Same typed-tool-call pattern as structured_output.py — the code the
    model submits is captured verbatim, and reset_whatif_state() clears it
    between what-if calls the same way reset_state() does for extraction."""
    sys.path.insert(0, str(ROOT / "app" / "pocvalidator"))
    from tools import what_if_pricing as wip

    wip.reset_whatif_state()
    assert wip.get_last_whatif_code() == ""

    wip.record_whatif_code("def compute(lines):\n    return {'x': 1}\n")
    assert "def compute(lines):" in wip.get_last_whatif_code()

    wip.reset_whatif_state()
    assert wip.get_last_whatif_code() == ""


def test_faq_search_degrades_without_knowledge_base_id():
    """No AWS account, no network — search_faq must return status=unavailable
    rather than raise when FAQ_KNOWLEDGE_BASE_ID isn't configured, same
    graceful-degradation contract as run_what_if() and the SOW model pass."""
    sys.path.insert(0, str(ROOT / "app" / "pocvalidator"))
    import config
    from tools import faq_search

    original = config.FAQ_KNOWLEDGE_BASE_ID
    faq_search.FAQ_KNOWLEDGE_BASE_ID = ""
    try:
        result = faq_search.search_faq("why does RDS need Multi-AZ?")
        assert result["status"] == "unavailable"
        assert "reason" in result
    finally:
        faq_search.FAQ_KNOWLEDGE_BASE_ID = original


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
        report = build(
            example["segment"],
            example["industry"],
            example["services"],
            [tuple(e) for e in example["edges"]],
            example.get("config") or {},
        )
        assert report.cost.total > 0, example["id"]
        assert report.verdict[0] in verdicts, example["id"]


def test_broken_example_actually_fails():
    broken = next(e for e in catalog.examples() if e["id"] == "broken_design")
    report = build(
        broken["segment"],
        broken["industry"],
        broken["services"],
        [tuple(e) for e in broken["edges"]],
    )
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
    for key in (
        "runtimes",
        "memories",
        "knowledgeBases",
        "agentCoreGateways",
        "policyEngines",
        "evaluators",
        "onlineEvalConfigs",
        "credentials",
    ):
        assert key in config, key
    assert config["runtimes"][0]["entrypoint"] == "main.py"
    assert not (ROOT / ".bedrock_agentcore.yaml").exists(), (
        "Starter Toolkit config is deprecated and penalised in the use-case rubric"
    )


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

    # knowledgeBases[]: written by `agentcore add knowledge-base --json`, not
    # guessed — type is "AgentCoreKnowledgeBase" (not "KnowledgeBase"), and
    # dataSources is an array of {type, uri}, not a single object.
    kb = config["knowledgeBases"][0]
    assert kb["type"] == "AgentCoreKnowledgeBase"
    assert len(kb["description"]) <= 200, (
        "AWS::Bedrock::KnowledgeBase Description has a 200-char limit"
    )
    source = kb["dataSources"][0]
    assert source["type"] == "S3"
    assert source["uri"].startswith("s3://")


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
    skip_dirs = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        "cdk.out",
        "dist",
        ".cli",
        ".understand-anything",
    }
    # Any virtualenv (`.venv`, `.venv-ui`, ...) is developer-local state, not repo content.
    skip_prefixes = (".venv",)
    skip_files = {"agentcore.json", "aws-targets.json", ".cognito-state.json"}
    for path in (
        list(ROOT.rglob("*.py"))
        + list(ROOT.rglob("*.json"))
        + list(ROOT.rglob("*.yaml"))
    ):
        if (
            any(part in skip_dirs for part in path.parts)
            or any(part.startswith(skip_prefixes) for part in path.parts)
            or path.name in skip_files
        ):
            continue
        assert not pattern.search(path.read_text(encoding="utf-8", errors="ignore")), (
            path
        )


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
