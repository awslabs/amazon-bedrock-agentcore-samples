# 0002 — Human confirmation gate on diagram extraction

## Status
Accepted.

## Context
Users upload an architecture diagram and a vision model reports what it sees. That
report becomes the design graph every later phase operates on.

## Decision
Phase 1 returns `status: awaiting_confirmation` with the extraction. No validation,
pricing or scoring runs until the caller resubmits with `extraction_confirmed: true`.
Labels the catalogue cannot resolve are returned in `unmatched` and shown to the user.

## Rationale
Vision extraction from architecture diagrams is the least reliable step in the pipeline.
Every downstream output is confident and specific — severities, dollar figures,
documentation links — so an extraction error does not degrade the result, it produces a
polished review of a design the partner never proposed. That is worse than no review.

Dropping unresolvable boxes silently has the same failure shape: the user sees a clean
result and no indication that a third of their diagram was ignored.

## Consequences
Diagram-driven reviews take two round trips. `REQUIRE_EXTRACTION_CONFIRMATION` can
disable the gate for automated testing, but it defaults to `true` and the README does not
advertise turning it off.
