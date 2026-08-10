"""Deterministic rules engine.

Every finding names the rule that produced it and the pack that rule came from.
There is no unattributed advice anywhere in the output — if the engine cannot say
why it flagged something, it does not flag it.
"""

from __future__ import annotations

from typing import Any

from . import catalog
from .models import Conflict, DesignGraph, Finding, Node, Severity


def _applies(requirement: dict[str, Any], node: Node) -> bool:
    scope = requirement.get("applies_to", {})
    if "services" in scope and node.service_id in scope["services"]:
        return True
    if "categories" in scope and node.category in scope["categories"]:
        return True
    # A rule may name a service in the categories list as a convenience.
    if "categories" in scope and node.service_id in scope["categories"]:
        return True
    return False


def _satisfied(requirement: dict[str, Any], node: Node) -> bool:
    attribute = requirement["attribute"]
    if attribute not in node.config:
        # The attribute does not apply to this service; nothing to enforce.
        return True
    actual = node.get(attribute)
    operator = requirement.get("operator", "equals")
    expected = requirement["value"]
    if operator == "equals":
        return actual == expected
    if operator == "min":
        return float(actual) >= float(expected)
    if operator == "max":
        return float(actual) <= float(expected)
    raise ValueError(f"Unknown operator: {operator}")


def _title(requirement: dict[str, Any], node: Node) -> str:
    attribute = requirement["attribute"]
    label = catalog.attribute_defs()[attribute]["label"]
    operator = requirement.get("operator", "equals")
    expected = requirement["value"]
    if operator == "min":
        return f"{label} below required minimum of {expected} on {node.name}"
    if expected is True:
        return f"{label} not enabled on {node.name}"
    if expected is False:
        return f"{label} must be disabled on {node.name}"
    return f"{label} must be {expected} on {node.name}"


def _evaluate_pack(
    pack: dict[str, Any], graph: DesignGraph, source_kind: str
) -> list[Finding]:
    findings: list[Finding] = []
    for requirement in pack.get("requirements", []):
        for node in graph.nodes.values():
            if not _applies(requirement, node):
                continue
            if _satisfied(requirement, node):
                continue
            findings.append(
                Finding(
                    rule_id=requirement["id"],
                    node_id=node.service_id,
                    node_name=node.name,
                    title=_title(requirement, node),
                    severity=Severity(requirement["severity"].capitalize()),
                    pillar=requirement.get("pillar", "Security"),
                    source=f"{source_kind}:{pack['id']}",
                    source_label=f"{pack['name']} ({source_kind})",
                    rationale=requirement["rationale"],
                    remediation=requirement["remediation"],
                    doc_url=requirement.get("doc_url", ""),
                )
            )
    return findings


def detect_conflicts(graph: DesignGraph) -> list[Conflict]:
    """Surface segment/industry tension instead of silently picking a winner.

    The classic case is a cost-sensitive segment meeting a regulatory floor. The
    engine always enforces the stricter rule, but it says so out loud rather than
    letting the user wonder why a lean design is being told to spend money.
    """
    segment = catalog.segments()[graph.segment_id]
    industry = catalog.industries()[graph.industry_id]
    if segment.get("cost_sensitivity") != "high":
        return []

    costly = {"customer_managed_key", "multi_az", "waf_enabled", "guardrails_enabled"}
    conflicts: list[Conflict] = []
    seen: set[tuple[str, str]] = set()

    for requirement in industry.get("requirements", []):
        attribute = requirement["attribute"]
        if attribute not in costly:
            continue
        for node in graph.nodes.values():
            if not _applies(requirement, node) or _satisfied(requirement, node):
                continue
            key = (attribute, node.service_id)
            if key in seen:
                continue
            seen.add(key)
            label = catalog.attribute_defs()[attribute]["label"]
            conflicts.append(
                Conflict(
                    attribute=label,
                    node_name=node.name,
                    segment_position=(
                        f"{segment['name']} is cost-sensitive and would normally "
                        f"leave {label.lower()} off at this stage."
                    ),
                    industry_position=(
                        f"{industry['name']} rule {requirement['id']} treats it as "
                        f"{requirement['severity']}."
                    ),
                    resolution=(
                        "Enforced the industry rule. Regulatory floors are not "
                        "negotiable against budget, but the cost impact is itemised "
                        "separately in the estimate so the trade-off is visible."
                    ),
                )
            )
    return conflicts


def evaluate(graph: DesignGraph) -> tuple[list[Finding], list[Conflict]]:
    segment = catalog.segments()[graph.segment_id]
    industry = catalog.industries()[graph.industry_id]
    findings = _evaluate_pack(segment, graph, "segment")
    findings += _evaluate_pack(industry, graph, "industry")
    return _deduplicate(findings), detect_conflicts(graph)


def _deduplicate(findings: list[Finding]) -> list[Finding]:
    """Keep the strictest finding when both packs flag the same attribute.

    Two packs demanding the same control on the same node is one problem for the
    user to fix, not two. The higher severity and its source are retained.
    """
    best: dict[tuple[str, str], Finding] = {}
    for finding in findings:
        key = (finding.node_id, finding.title)
        current = best.get(key)
        if current is None or finding.severity.rank < current.severity.rank:
            best[key] = finding
    return list(best.values())
