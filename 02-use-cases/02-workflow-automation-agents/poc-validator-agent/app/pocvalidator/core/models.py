"""Canonical data model.

Every part of the validator reads and annotates one `DesignGraph`. Findings,
chaining analysis and costing all derive from this single structure, which is what
keeps the four result panels from contradicting each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

    @property
    def rank(self) -> int:
        return {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}[self.value]


class EdgeType(str, Enum):
    NATIVE = "native"
    GLUE = "glue"
    ANTI_PATTERN = "anti_pattern"
    UNVERIFIED = "unverified"


@dataclass
class Node:
    """One AWS service in the submitted design, with its posture configuration."""

    service_id: str
    name: str
    category: str
    doc_url: str
    config: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, float] = field(default_factory=dict)

    def get(self, attribute: str, default: Any = None) -> Any:
        return self.config.get(attribute, default)


@dataclass
class Edge:
    source: str
    target: str
    edge_type: EdgeType = EdgeType.UNVERIFIED
    note: str = ""
    pattern: str = ""
    doc_url: str = ""

    @property
    def label(self) -> str:
        return {
            EdgeType.NATIVE: "Native integration",
            EdgeType.GLUE: "Glue required",
            EdgeType.ANTI_PATTERN: "Anti-pattern",
            EdgeType.UNVERIFIED: "Unverified",
        }[self.edge_type]


@dataclass
class Finding:
    """A single validation result, always traceable to the rule that produced it."""

    rule_id: str
    node_id: str
    node_name: str
    title: str
    severity: Severity
    pillar: str
    source: str  # which rule pack fired: segment id, industry id, or "chaining"
    source_label: str  # human-readable pack name
    rationale: str
    remediation: str
    doc_url: str


@dataclass
class Conflict:
    """A tension between segment and industry rules, surfaced rather than resolved."""

    attribute: str
    node_name: str
    segment_position: str
    industry_position: str
    resolution: str


@dataclass
class CostLine:
    node_id: str
    node_name: str
    driver: str
    driver_label: str
    quantity: float
    unit_rate: float
    monthly_cost: float
    is_premium: bool = False
    note: str = ""


@dataclass
class CostEstimate:
    baseline: float
    premium: float
    lines: list[CostLine] = field(default_factory=list)
    as_of: str = ""
    region: str = ""
    currency: str = "USD"
    source: str = ""

    @property
    def total(self) -> float:
        return round(self.baseline + self.premium, 2)


@dataclass
class DesignGraph:
    segment_id: str
    industry_id: str
    region: str
    description: str = ""
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    def add_node(self, node: Node) -> None:
        self.nodes[node.service_id] = node

    def add_edge(self, source: str, target: str) -> None:
        if source in self.nodes and target in self.nodes:
            self.edges.append(Edge(source=source, target=target))


@dataclass
class ValidationReport:
    graph: DesignGraph
    findings: list[Finding] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    cost: CostEstimate | None = None
    evidence: list[dict[str, str]] = field(default_factory=list)
    sow: Any = None  # SOWScore, when a Scope of Work was submitted
    recommendations: list = field(default_factory=list)  # [(Resource, reason)]

    @property
    def sorted_findings(self) -> list[Finding]:
        return sorted(self.findings, key=lambda f: (f.severity.rank, f.node_name))

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity is severity)

    @property
    def verdict(self) -> tuple[str, str]:
        """Returns (verdict, reasoning). Deliberately blunt about what blocks."""
        crit = self.count(Severity.CRITICAL)
        high = self.count(Severity.HIGH)
        if crit:
            return (
                "Not ready",
                (
                    f"{crit} critical finding{'s' if crit != 1 else ''} must be resolved "
                    "before this design goes in front of a customer."
                ),
            )
        if high >= 3:
            return (
                "Needs work",
                (
                    f"{high} high-severity findings. No single blocker, but the "
                    "aggregate gap is too wide to present as production-ready."
                ),
            )
        if high:
            return (
                "Conditionally ready",
                (
                    f"{high} high-severity finding{'s' if high != 1 else ''} to close, "
                    "each with a clear remediation."
                ),
            )
        return (
            "Ready",
            (
                "No critical or high-severity findings against the selected "
                "segment and industry rules."
            ),
        )
