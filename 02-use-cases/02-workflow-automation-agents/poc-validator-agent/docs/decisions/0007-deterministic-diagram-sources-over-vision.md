# 0007 — Deterministic diagram sources preferred over vision

## Status
Accepted. Amends the exposure described in ADR 0002.

## Context
ADR 0002 added a human confirmation gate because vision extraction from an architecture
diagram is the least reliable step in the pipeline. The gate contains the risk but does
not reduce it — every diagram-driven review still depends on a model reading an image
correctly, and on a human catching it when it does not.

## Decision
Accept draw.io XML (`.drawio`, `.xml`) and Mermaid (`.mmd`, `.mermaid`, fenced blocks in
`.md`) as first-class inputs, parsed deterministically in `core/diagrams.py`. Source
files skip both the model and the confirmation gate. Image upload remains as a fallback
and still requires confirmation.

## Rationale
Most architecture diagrams have a source file. Parsing it is exact: there is no
possibility of a hallucinated service, and no round trip for the user. The draw.io parser
also recovers the service from the `resIcon=mxgraph.aws4.*` style when a shape has been
left unlabelled, which vision would have to guess at.

Both parsers report unresolvable shapes in `unmatched` exactly as the vision path does,
so everything downstream is identical regardless of how the design arrived.

## Consequences
The UI leads with source upload and describes image upload as the fallback. Vision is now
the third-choice path rather than the primary one, which is the right ordering given its
reliability. Eight tests cover the parsers, including malformed input, unlabelled AWS
shapes, and non-AWS shapes.
