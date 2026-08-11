"""Deterministic diagram parsing.

Vision extraction from a PNG is the least reliable step in the pipeline. When the
user has a *source* diagram — draw.io XML or Mermaid — it can be parsed exactly,
with no model, no confirmation gate and no chance of a hallucinated service.

So the input hierarchy is: source file first, image only as a fallback. This
inverts ADR 0002's exposure — the confirmation gate still exists for images,
but most users never need to rely on it.

Both parsers are strict about what they claim. A shape they cannot map onto the
service catalogue is returned in ``unmatched``, exactly as the vision path does,
so downstream handling is identical regardless of input format.
"""

from __future__ import annotations

import base64
import re
import urllib.parse
import zlib

from defusedxml import ElementTree

from .engine import ExtractedDiagram, extraction_from_raw

# draw.io AWS shapes carry the service in the style string rather than the label
# when the user has left a shape unnamed, e.g.
#   shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.s3;
_RES_ICON = re.compile(r"res(?:Icon)?=mxgraph\.aws4\.([a-z0-9_]+)", re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]+>")

# Mermaid node declarations: id["Label"], id(Label), id{Label}, id[[Label]]
_MERMAID_NODE = re.compile(
    r"(?P<id>[A-Za-z0-9_.-]+)\s*(?:\[\[|\[\(|\[|\(\(|\(|\{\{|\{)\s*"
    r"[\"'`]?(?P<label>[^\]\)\}\"'`]+)[\"'`]?\s*(?:\]\]|\)\]|\]|\)\)|\)|\}\}|\})"
)
# Mermaid edges: A --> B, A -.-> B, A -- text --> B, A ==> B
_MERMAID_EDGE = re.compile(
    r"(?P<src>[A-Za-z0-9_.-]+)\s*"
    r"(?:-{2,3}|-\.-|={2,3})(?:\|[^|]*\||\s*[^->=\s]*\s*)?(?:-{1,2}>|>|-{1,2}x|-{1,2}o)\s*"
    r"(?P<dst>[A-Za-z0-9_.-]+)"
)


def _clean(label: str) -> str:
    """Strip the HTML draw.io embeds in labels, and collapse whitespace."""
    text = _HTML_TAG.sub(" ", label or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return " ".join(text.split())


def _decompress_drawio(payload: str) -> str | None:
    """draw.io stores diagrams deflate-compressed and base64-encoded by default."""
    try:
        raw = base64.b64decode(payload)
        inflated = zlib.decompress(raw, -zlib.MAX_WBITS)
        return urllib.parse.unquote(inflated.decode("utf-8"))
    except Exception:
        return None


def parse_drawio(xml_text: str) -> ExtractedDiagram:
    """Parse a .drawio / .xml export into an extraction result.

    Handles both uncompressed diagrams and the default compressed form.
    """
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        return ExtractedDiagram(notes=f"Could not parse the file as XML: {exc}")

    # Unwrap <mxfile><diagram>…</diagram></mxfile>, decompressing if needed.
    if root.tag == "mxfile":
        for diagram in root.findall("diagram"):
            if diagram.find(".//mxCell") is not None:
                root = diagram
                break
            inner = _decompress_drawio((diagram.text or "").strip())
            if inner:
                try:
                    root = ElementTree.fromstring(inner)
                    break
                except ElementTree.ParseError:
                    continue

    cells = root.findall(".//mxCell")
    if not cells:
        return ExtractedDiagram(
            notes="No mxCell elements found — is this a draw.io diagram?"
        )

    labels: dict[str, str] = {}
    raw_services: list[str] = []
    edges: list[dict[str, str]] = []

    for cell in cells:
        cell_id = cell.get("id", "")
        style = cell.get("style", "") or ""
        value = _clean(cell.get("value", ""))

        if cell.get("edge") == "1":
            source, target = cell.get("source"), cell.get("target")
            if source and target:
                edges.append({"from": source, "to": target})
            continue

        if cell.get("vertex") != "1":
            continue

        # Prefer the visible label; fall back to the AWS shape name.
        name = value
        if not name:
            match = _RES_ICON.search(style)
            if match:
                name = match.group(1).replace("_", " ")
        if not name:
            continue

        labels[cell_id] = name
        raw_services.append(name)

    # Re-express edges in terms of labels so extraction_from_raw can resolve them.
    named_edges = [
        {"from": labels[edge["from"]], "to": labels[edge["to"]]}
        for edge in edges
        if edge["from"] in labels and edge["to"] in labels
    ]
    dropped = len(edges) - len(named_edges)

    result = extraction_from_raw({"services": raw_services, "edges": named_edges})
    notes = [f"Parsed {len(raw_services)} shapes and {len(named_edges)} connectors."]
    if dropped:
        notes.append(
            f"{dropped} connector(s) attached to a container or unlabelled shape "
            "and were not included."
        )
    result.notes = " ".join(notes)
    return result


def parse_mermaid(text: str) -> ExtractedDiagram:
    """Parse a Mermaid flowchart into an extraction result."""
    labels: dict[str, str] = {}
    raw_services: list[str] = []
    edge_ids: list[tuple[str, str]] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("%%", "graph ", "flowchart ", "subgraph")):
            continue
        if stripped in {"end"}:
            continue

        for match in _MERMAID_NODE.finditer(stripped):
            node_id = match.group("id")
            label = _clean(match.group("label"))
            if label and node_id not in labels:
                labels[node_id] = label
                raw_services.append(label)

        for match in _MERMAID_EDGE.finditer(stripped):
            source, target = match.group("src"), match.group("dst")
            if source != target:
                edge_ids.append((source, target))

    # A bare id with no declared label is its own label — common in short diagrams.
    for source, target in edge_ids:
        for node_id in (source, target):
            if node_id not in labels:
                labels[node_id] = node_id
                raw_services.append(node_id)

    named_edges = [
        {"from": labels[source], "to": labels[target]}
        for source, target in edge_ids
        if source in labels and target in labels
    ]

    if not raw_services:
        return ExtractedDiagram(
            notes="No Mermaid nodes recognised. Expected a `graph`/`flowchart` block."
        )

    result = extraction_from_raw({"services": raw_services, "edges": named_edges})
    result.notes = (
        f"Parsed {len(raw_services)} nodes and {len(named_edges)} edges from Mermaid."
    )
    return result


def parse(filename: str, content: bytes | str) -> ExtractedDiagram:
    """Dispatch on file extension. Returns an empty result for image formats,
    which must go through the vision path and the confirmation gate."""
    text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
    lowered = filename.lower()

    if lowered.endswith((".drawio", ".xml")):
        return parse_drawio(text)
    if lowered.endswith((".mmd", ".mermaid")):
        return parse_mermaid(text)
    if lowered.endswith((".md", ".txt")):
        # Pull a fenced mermaid block out of markdown if there is one.
        fenced = re.search(r"```mermaid\s*(.+?)```", text, re.DOTALL | re.IGNORECASE)
        if fenced:
            return parse_mermaid(fenced.group(1))
        return parse_mermaid(text)

    return ExtractedDiagram(
        notes=f"{filename} is an image format — it goes through vision extraction "
        "and requires confirmation."
    )


def is_deterministic(filename: str) -> bool:
    """True when the file can be parsed exactly, skipping the confirmation gate."""
    return filename.lower().endswith((".drawio", ".xml", ".mmd", ".mermaid"))
