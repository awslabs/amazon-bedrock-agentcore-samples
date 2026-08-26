# Task fixtures

One YAML file per suite. Each file declares what "resolved" means for that suite, because the
denominator of cost-per-resolved-task is only meaningful if "resolved" is written down per suite
rather than assumed. The thresholds those numbers are judged against live in `../gate.yaml`.

## Shape

```yaml
suite: B
title: Eligibility verdicts
resolved_when: verdict exact-match, and the narration agrees with it
tasks:
  - id: B1
    title: A hotel exactly at the cap is inside policy
    prompt: Is a hotel at 250 dollars a night within my policy?
    personas: [priya] # runs once per persona listed
    expect:
      tools:
        required_any: [check_policy_eligibility]
        forbidden: [confirm_booking]
      verdict: # asserted by VerdictExactMatch
        eligible: true
        reason_code: hotel_in_policy
      cards:
        required_types: [policy_verdict]
      by_persona: # where the correct answer differs per tenant
        priya:
          must_mention: ["250"]
          must_not_mention: ["150", "initech"]
```

Every block maps to exactly one code-based evaluator, so a failure names the property that broke
rather than "the task failed":

| Block                             | Evaluator            |
| --------------------------------- | -------------------- |
| `tools.required_any`, `forbidden` | `ToolSequence`       |
| `verdict`                         | `VerdictExactMatch`  |
| `cards.required_types`            | `CardSchemaValid`    |
| `must_not_mention`                | `TenantIsolation`    |
| `writes`                          | `ConfirmBeforeWrite` |
| `handoff`                         | `EscalationPackage`  |

## Two rules that make the numbers mean anything

**Personas, not tenants.** A task lists the travellers it runs as, and the runner resolves the
tenant from the persona — so `priya` and `sam` asking the identical question is one task run twice,
which is what makes tenant contrast a property of the fixture rather than a suite of its own.

| Persona  | Tenant  | Role     | Policy in force                                         |
| -------- | ------- | -------- | ------------------------------------------------------- |
| `priya`  | globex  | traveler | hotel ≤ $250 / 4★, business every 4th internationaltrip |
| `adaeze` | globex  | arranger | as globex, and may act for other globex travellers      |
| `sam`    | initech | traveler | hotel ≤ €150 / 3★, economy only, 7-day advance          |

**`FIXTURE` mode, or the assertions are theatre.** Exact-match verdicts and cost baselines only
mean something against seeded generation, where the same query returns the same options. `LIVE`
mode seeds on a time bucket and drifts between sessions, which is right for a demo and useless for
a gate.

## Expected values are computed, not guessed

The verdicts in suite B were produced by calling `backend/app/service/policy_check.py` directly and
recording what it returned, including the exact boundaries — `$250` exactly at
the cap and departure exactly 7 days out are both **inside** policy. A fixture whose expectation was
written from reading the policy prose would encode the reader's arithmetic instead of the code's.

## Tasks whose support does not exist yet

A task may declare `blocked_on:`. The runner reports those as skipped **with the reason**, and never
as passed — a suite that silently drops the tasks it cannot run would report a clean sheet for
exactly the behaviour nobody has built.
