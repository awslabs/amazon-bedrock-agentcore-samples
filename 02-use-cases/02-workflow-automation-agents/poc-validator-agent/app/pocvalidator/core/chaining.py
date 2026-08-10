"""Service chaining analysis.

The governing rule: never assert that two services integrate unless the catalogue
says so. An edge the catalogue does not know about is reported as *unverified*,
not as working. Confidently inventing an integration that does not exist is the
worst failure this tool could have, so the unknown case is explicit.
"""

from __future__ import annotations

from . import catalog
from .models import DesignGraph, EdgeType, Finding, Severity


def classify(graph: DesignGraph) -> None:
    """Annotate every edge in place from the integration catalogue."""
    known = catalog.integrations()
    for edge in graph.edges:
        entry = known.get((edge.source, edge.target))
        if entry is None:
            edge.edge_type = EdgeType.UNVERIFIED
            edge.note = (
                "This pair is not in the integration catalogue. It has not been "
                "confirmed to work and has not been ruled out — verify it against "
                "AWS documentation before relying on it."
            )
            edge.doc_url = ""
            continue
        edge.edge_type = EdgeType(entry["type"])
        edge.note = entry.get("note", "")
        edge.pattern = entry.get("pattern", "")
        edge.doc_url = entry.get("doc_url", "")


def findings(graph: DesignGraph) -> list[Finding]:
    """Turn problematic edges into findings alongside the rule-pack results."""
    results: list[Finding] = []
    for edge in graph.edges:
        source = graph.nodes[edge.source]
        target = graph.nodes[edge.target]
        pair = f"{source.name} → {target.name}"

        if edge.edge_type is EdgeType.ANTI_PATTERN:
            results.append(
                Finding(
                    rule_id=f"CHAIN-{edge.source}-{edge.target}".upper(),
                    node_id=edge.source,
                    node_name=pair,
                    title=f"Unsupported integration: {pair}",
                    severity=Severity.CRITICAL,
                    pillar="Reliability",
                    source="chaining",
                    source_label="Integration catalogue",
                    rationale=edge.note,
                    remediation="Remove this edge and route through an application "
                    "or integration tier.",
                    doc_url=edge.doc_url,
                )
            )
        elif edge.edge_type is EdgeType.GLUE:
            results.append(
                Finding(
                    rule_id=f"CHAIN-{edge.source}-{edge.target}".upper(),
                    node_id=edge.source,
                    node_name=pair,
                    title=f"{pair} requires glue: {edge.pattern}",
                    severity=Severity.HIGH,
                    pillar="Reliability",
                    source="chaining",
                    source_label="Integration catalogue",
                    rationale=edge.note,
                    remediation=f"Introduce {edge.pattern} between the two services "
                    "and account for its cost and operational overhead.",
                    doc_url=edge.doc_url,
                )
            )
        elif edge.edge_type is EdgeType.UNVERIFIED:
            results.append(
                Finding(
                    rule_id=f"CHAIN-{edge.source}-{edge.target}".upper(),
                    node_id=edge.source,
                    node_name=pair,
                    title=f"Unverified integration: {pair}",
                    severity=Severity.MEDIUM,
                    pillar="Operational Excellence",
                    source="chaining",
                    source_label="Integration catalogue",
                    rationale=edge.note,
                    remediation="Confirm against AWS documentation, then add the "
                    "pair to data/integrations.yaml so future reviews are grounded.",
                    doc_url="",
                )
            )
    return results


def orphans(graph: DesignGraph) -> list[str]:
    """Services with no edge in either direction — usually a modelling omission."""
    connected: set[str] = set()
    for edge in graph.edges:
        connected.add(edge.source)
        connected.add(edge.target)
    return [n.name for sid, n in graph.nodes.items() if sid not in connected]


def mermaid(graph: DesignGraph) -> str:
    """Render the design graph as Mermaid for inline display."""
    style = {
        EdgeType.NATIVE: "-->",
        EdgeType.GLUE: "-. glue .->",
        EdgeType.ANTI_PATTERN: "-- BROKEN --x",
        EdgeType.UNVERIFIED: "-. unverified .->",
    }
    lines = ["graph LR"]
    for sid, node in graph.nodes.items():
        lines.append(f'  {sid}["{node.name}"]')
    for edge in graph.edges:
        lines.append(f"  {edge.source} {style[edge.edge_type]} {edge.target}")
    return "\n".join(lines)


DOT_STYLE = {
    EdgeType.NATIVE: 'color="#1f6f4a" penwidth=2',
    EdgeType.GLUE: 'color="#8a6d1f" style=dashed penwidth=2 label="glue"',
    EdgeType.ANTI_PATTERN: 'color="#a32020" penwidth=3 label="unsupported" arrowhead=tee',
    EdgeType.UNVERIFIED: 'color="#6b6b6b" style=dotted label="unverified"',
}

CATEGORY_FILL = {
    "networking": "#e8f0fb",
    "compute": "#e9f5ec",
    "database": "#fdf0e6",
    "storage": "#f3ecfa",
    "integration": "#fdf7e0",
    "security": "#fbe9ee",
    "observability": "#eef1f4",
    "analytics": "#e6f5f6",
    "ai": "#f0ecfb",
}


def dot(graph: DesignGraph) -> str:
    """Render the design graph as Graphviz DOT for st.graphviz_chart."""
    lines = [
        "digraph design {",
        '  rankdir=LR;',
        '  bgcolor="transparent";',
        '  node [shape=box style="rounded,filled" fontname="Helvetica" fontsize=11 '
        'penwidth=0.8 color="#c8ccd2" margin="0.18,0.10"];',
        '  edge [fontname="Helvetica" fontsize=9];',
    ]
    for sid, node in graph.nodes.items():
        fill = CATEGORY_FILL.get(node.category, "#f2f2f2")
        lines.append(f'  {sid} [label="{node.name}" fillcolor="{fill}"];')
    for edge in graph.edges:
        lines.append(f"  {edge.source} -> {edge.target} [{DOT_STYLE[edge.edge_type]}];")
    if not graph.edges:
        lines.append('  _note [label="No connections defined" fillcolor="#f2f2f2" '
                     'fontcolor="#6b6b6b" style="rounded,filled,dashed"];')
    lines.append("}")
    return "\n".join(lines)
