# 0006 — Curated resource catalogue over live web search

## Status
Accepted. Revisit if a web-search Gateway target lands upstream.

## Context
Recommendations could come from live search or a curated catalogue.

## Decision
Ship a versioned catalogue in `data/resources.yaml` with an as-of date. Rank against the
findings the review actually produced, and state the reason for each suggestion.

## Rationale
No sample in the repository currently uses a web-search Gateway target, so live search
would be unproven ground in a contribution meant to demonstrate established patterns.
A catalogue is also deterministic and offline-testable, which keeps the no-AWS quickstart
honest, and it cannot drift onto a domain the allowlist would have to catch after the
fact.

The cost is staleness, bounded by the as-of date being visible in the UI.

## Consequences
Recommendations need periodic refresh. If a web-search target becomes available, it
should reuse the same allowlist from `core/resources.py` rather than a prompt instruction.
