"""Validation orchestrator.

Fixed stage order over one design graph, collecting evidence as it goes. Every
stage is pure and independently testable; the agent layer replaces where the
*inputs* come from, never this logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import catalog, chaining, pricing, resources, rules
from .models import DesignGraph, Node, ValidationReport
from .sow import SOWScore


@dataclass
class ExtractedDiagram:
    """What a vision model reported seeing on an uploaded diagram.

    ``unmatched`` holds box labels that could not be mapped onto the service
    catalogue. They are surfaced to the user for correction — never dropped, and
    never guessed at.
    """

    services: list[str] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.services


def extraction_from_raw(raw: dict[str, Any]) -> ExtractedDiagram:
    """Normalise a model's diagram report onto catalogue ids.

    Anything the catalogue cannot resolve lands in ``unmatched`` so the
    confirmation step can show the user exactly what was not understood.
    """
    services: list[str] = []
    unmatched: list[str] = []
    alias: dict[str, str] = {}

    for label in raw.get("services", []) or []:
        service_id = catalog.resolve_service(str(label))
        if service_id and service_id not in services:
            services.append(service_id)
        if service_id:
            alias[str(label).strip().lower()] = service_id
        else:
            unmatched.append(str(label))

    edges: list[tuple[str, str]] = []
    for edge in raw.get("edges", []) or []:
        if isinstance(edge, dict):
            source_label, target_label = edge.get("from"), edge.get("to")
        elif isinstance(edge, (list, tuple)) and len(edge) == 2:
            source_label, target_label = edge
        else:
            continue
        source = alias.get(str(source_label).strip().lower()) or catalog.resolve_service(
            str(source_label)
        )
        target = alias.get(str(target_label).strip().lower()) or catalog.resolve_service(
            str(target_label)
        )
        if source and target and source != target and (source, target) not in edges:
            edges.append((source, target))

    return ExtractedDiagram(
        services=services,
        edges=edges,
        unmatched=unmatched,
        notes=str(raw.get("notes", "") or ""),
    )


def build_graph(
    segment_id: str,
    industry_id: str,
    region: str,
    description: str,
    selections: dict[str, dict],
    edges: list[tuple[str, str]],
) -> DesignGraph:
    graph = DesignGraph(
        segment_id=segment_id,
        industry_id=industry_id,
        region=region,
        description=description,
    )
    defs = catalog.service_defs()
    for service_id, payload in selections.items():
        definition = defs[service_id]
        graph.add_node(
            Node(
                service_id=service_id,
                name=definition["name"],
                category=definition["category"],
                doc_url=definition["doc_url"],
                config=payload.get("config", {}),
                usage=payload.get("usage", {}),
            )
        )
    for source, target in edges:
        graph.add_edge(source, target)
    return graph


def graph_from_selection(
    segment_id: str,
    industry_id: str,
    region: str,
    description: str,
    service_ids: list[str],
    edges: list[tuple[str, str]],
    overrides: dict[str, dict] | None = None,
) -> DesignGraph:
    """Convenience builder that fills defaults for every selected service."""
    overrides = overrides or {}
    selections: dict[str, dict] = {}
    for service_id in service_ids:
        config = catalog.default_config(service_id)
        config.update(overrides.get(service_id, {}))
        selections[service_id] = {
            "config": config,
            "usage": catalog.default_usage(service_id),
        }
    return build_graph(segment_id, industry_id, region, description, selections, edges)


def validate(graph: DesignGraph, sow_score: SOWScore | None = None) -> ValidationReport:
    chaining.classify(graph)

    rule_findings, conflicts = rules.evaluate(graph)
    chain_findings = chaining.findings(graph)

    report = ValidationReport(
        graph=graph,
        findings=rule_findings + chain_findings,
        conflicts=conflicts,
        cost=pricing.estimate(graph),
    )
    report.sow = sow_score
    report.recommendations = resources.recommend(report, sow_score)
    report.evidence = _evidence(report)
    return report


def _evidence(report: ValidationReport) -> list[dict[str, str]]:
    """Every source consulted. Findings without a source are never produced."""
    seen: dict[str, dict[str, str]] = {}

    for node in report.graph.nodes.values():
        seen[node.doc_url] = {
            "label": f"{node.name} — service documentation",
            "url": node.doc_url,
            "kind": "Service",
        }
    for finding in report.findings:
        if finding.doc_url:
            seen[finding.doc_url] = {
                "label": f"{finding.rule_id} — {finding.title}",
                "url": finding.doc_url,
                "kind": "Rule",
            }
    for edge in report.graph.edges:
        if edge.doc_url:
            seen[edge.doc_url] = {
                "label": f"{edge.source} → {edge.target} — {edge.label}",
                "url": edge.doc_url,
                "kind": "Integration",
            }
    if report.cost:
        seen[report.cost.source] = {
            "label": f"Pricing snapshot, as of {report.cost.as_of} ({report.cost.region})",
            "url": report.cost.source,
            "kind": "Pricing",
        }
    return sorted(seen.values(), key=lambda entry: (entry["kind"], entry["label"]))
