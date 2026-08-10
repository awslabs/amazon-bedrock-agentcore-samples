# 0003 — Deterministic validation, pricing and SOW weighting

## Status
Accepted.

## Context
An LLM could plausibly produce findings, a cost estimate and a SOW score directly.

## Decision
Phases 2, 3 and 5 involve no model. Phase 4 uses a model only to band each criterion
0–4; the weighted roll-up is Python. The `submit_sow_assessment` tool docstring tells the
model not to compute a total, and any total it produced would be discarded.

## Rationale
Follows the reasoning in ADR 0014 of the event-driven-claims-agent sample. These are the
outputs a reviewer takes at face value: a severity, a dollar figure, a score out of 100.
A plausible wrong number in any of them is invisible until it is in front of a customer.
Deterministic code can be unit-tested against hand-computed values; a model cannot.

The model is used where judgement is genuinely required — reading a diagram, deciding
whether a paragraph is boilerplate or substance — and nowhere else.

## Consequences
Two runs over the same inputs produce identical findings and identical totals. SOW
scoring degrades to a heuristic floor when no model is available, labelled as such rather
than presented as a full score.
