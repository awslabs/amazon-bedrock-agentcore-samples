# Memory tutorials — restructure notes

Working notes for aligning the memory tutorials with the desired shape: each feature has a README + standard-usage script, sub-features are nested folders, and real-world tutorials live under an `examples/` subfolder.

---

## Current state (snapshot)

```
memory/
├── README.md
├── journal.md                  <- prior restructure plan; superseded by this file
├── rerun_fixed2.py             <- ad-hoc test runner; not a tutorial artifact
├── run_tests.py                <- ad-hoc test runner; not a tutorial artifact
├── images/
├── 00-getting-started/         OK — concepts.md + decision guide + 3 quickstarts (CLI/boto3/SDK)
├── 01-short-term-memory/
│   ├── README.md
│   ├── 01-core-features/       4 placeholder *.py files (0 lines each) — no teaching content
│   ├── 02-single-agent/        Strands / LangGraph / LlamaIndex example agents
│   └── 03-multi-agent/         Strands example agents (incl. parallel branches)
├── 02-long-term-memory/
│   ├── README.md
│   ├── 01-core-features/       9 placeholder *.py files (0 lines) except 09-record-streaming.py
│   ├── 02-single-agent/        Strands / LangGraph / LlamaIndex examples (built-in / custom / tool)
│   └── 03-multi-agent/         Strands examples
├── 03-advanced-patterns/       Runtime / Identity / Guardrails / Browser / Streaming use cases / Observability (placeholder)
└── 04-security-patterns/       IAM / Cognito / KMS (KMS placeholder)
```

Empty (0-line) Python files acting as placeholders:

- `01-short-term-memory/01-core-features/{01-events-and-sessions, 02-event-metadata-filtering, 03-actor-session-isolation, 04-event-branching}.py`
- `02-long-term-memory/01-core-features/{01-built-in-strategies/{semantic, summary, user-preference, episodic}.py, 02-strategies-with-overrides.py, 03-self-managed-strategy.py, 04-namespaces-and-organization.py, 05-retrieve-records-and-citations.py, 06-structured-metadata.py, 07-batch-create-update-delete.py, 08-redrive-failed-ingestions.py}`
- `03-advanced-patterns/06-observability.py`
- `04-security-patterns/03-kms-encryption.py`

---

## Gap analysis vs. desired shape

The user's stated shape:

> 00 = getting started; 01+ = features and sub-features; use cases go under `examples/`; the main feature folder has a README or python file with standard usage and best practices.

| Concern                                        | Today                                                                                           | Desired                                                                                                                    |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Top-level feature shape                        | `01-core-features/` + `02-single-agent/` + `03-multi-agent/`                                    | `README.md` + standard-usage script + sub-feature folders + `examples/`                                                    |
| Sub-feature pages                              | `01-core-features/<NN>-<name>.py` (mostly empty)                                                | Each sub-feature in its own folder with README + working script                                                            |
| Use cases                                      | Spread across `02-single-agent/`, `03-multi-agent/`, `03-advanced-patterns/`                    | Live under `examples/` adjacent to the feature they exercise                                                               |
| Single vs multi-agent                          | Top-level split (`02-` / `03-` siblings of `01-core-features/`)                                 | Should be a property of the example, not a tree axis                                                                       |
| Framework split (Strands/LangGraph/LlamaIndex) | Folder axis under `02-single-agent/` etc.                                                       | Keep, but nested under `examples/`                                                                                         |
| Advanced patterns                              | Mix of integrations (Runtime/Identity/Guardrails/Browser) + observability + streaming use cases | Integrations stay; observability becomes a feature folder; streaming use cases consolidate under the streaming sub-feature |

---

## Proposed target shape

```
memory/
├── README.md                       # top-level map of features
├── documentation.md                # feature digest from devguide (already written)
├── images/
│
├── 00-getting-started/             # unchanged — already on-pattern
│   ├── README.md
│   ├── 01-memory-concepts.md
│   ├── 02-choosing-your-surface.md
│   ├── 03-quickstart-cli.md
│   ├── 04-quickstart-boto3.py
│   └── 05-quickstart-agentcore-sdk.py
│
├── 01-short-term-memory/
│   ├── README.md                   # what it is + standard usage + best practices
│   ├── standard-usage.py           # the canonical "create memory, write events, list events" walkthrough
│   ├── 01-events-and-sessions/
│   │   ├── README.md
│   │   └── events-and-sessions.py
│   ├── 02-event-metadata/
│   │   ├── README.md
│   │   └── event-metadata-filtering.py
│   ├── 03-actor-session-isolation/
│   │   ├── README.md
│   │   └── actor-session-isolation.py
│   ├── 04-branching/
│   │   ├── README.md
│   │   └── event-branching.py
│   └── examples/
│       ├── single-agent/
│       │   ├── with-strands-agent/        (existing files)
│       │   ├── with-langgraph-agent/      (existing files)
│       │   └── with-llamaindex-agent/     (existing files)
│       └── multi-agent/
│           └── with-strands-agent/        (existing files, incl. parallel-branches)
│
├── 02-long-term-memory/
│   ├── README.md                   # what it is + strategy decision guide + best practices
│   ├── standard-usage.py           # canonical "create memory + semantic strategy + retrieve" walkthrough
│   ├── 01-built-in-strategies/
│   │   ├── README.md               # which strategy when, default namespaces, schemas
│   │   ├── semantic.py
│   │   ├── summary.py
│   │   ├── user-preference.py
│   │   └── episodic.py
│   ├── 02-strategy-overrides/
│   │   ├── README.md
│   │   └── strategies-with-overrides.py
│   ├── 03-self-managed-strategy/
│   │   ├── README.md
│   │   └── self-managed-strategy.py
│   ├── 04-namespaces/
│   │   ├── README.md
│   │   └── namespaces-and-organization.py
│   ├── 05-retrieval/
│   │   ├── README.md
│   │   └── retrieve-records-and-citations.py
│   ├── 06-record-metadata/
│   │   ├── README.md
│   │   └── structured-metadata.py
│   ├── 07-batch-apis/
│   │   ├── README.md
│   │   └── batch-create-update-delete.py
│   ├── 08-redrive/
│   │   ├── README.md
│   │   └── redrive-failed-ingestions.py
│   ├── 09-record-streaming/
│   │   ├── README.md               # the streaming primitive + content levels
│   │   ├── record-streaming.py
│   │   └── examples/
│   │       ├── cross-region-replication/         (moved from advanced-patterns/05)
│   │       ├── personalised-recommendations.py   (moved from advanced-patterns/05)
│   │       └── cross-customer-analytics.py       (moved from advanced-patterns/05)
│   └── examples/
│       ├── single-agent/
│       │   ├── with-strands-agent/        (existing built-in / custom / memory-tool subfolders)
│       │   ├── with-langgraph-agent/
│       │   └── with-llamaindex-agent/
│       └── multi-agent/
│           └── with-strands-agent/
│
├── 03-integrations/                # renamed from 03-advanced-patterns (only integrations left)
│   ├── README.md
│   ├── 01-runtime-integration/     (existing)
│   ├── 02-identity-integration/    (existing)
│   ├── 03-guardrails-integration/  (existing)
│   └── 04-memory-browser/          (existing)
│
├── 04-observability/               # promoted out of 03-advanced-patterns
│   ├── README.md
│   └── observability.py
│
└── 05-security/                    # renamed from 04-security-patterns
    ├── README.md
    ├── 01-iam-scoped-access/
    ├── 02-cognito-federated-identity/
    └── 03-kms-encryption/
        ├── README.md
        └── kms-encryption.py
```

Key shifts vs. today:

1. Each feature folder gets a README with **standard usage + best practices** and a `standard-usage.py` showing the canonical flow.
2. Each sub-feature is its own folder (README + script) instead of a bare `NN-name.py` file at the same level — this aligns with "features and sub-features" and gives room for accompanying notes/diagrams.
3. `02-single-agent/` and `03-multi-agent/` collapse under `examples/{single-agent,multi-agent}/` so they're clearly _use cases that exercise the feature_, not parallel feature axes.
4. Streaming use cases move next to the streaming primitive (under `09-record-streaming/examples/`) instead of living in `03-advanced-patterns/`.
5. `03-advanced-patterns/` becomes `03-integrations/` (only Runtime/Identity/Guardrails/Browser remain). Observability promoted to its own top-level feature `04-observability/`. Security moves to `05-security/` for consistent naming.
6. Root cleanup: drop `TEST_REPORT_CARD.md`, `journal.md`, `rerun_fixed2.py`, `run_tests.py` (or move test-runner artifacts out of the tutorials tree).

---

## Open questions for the user

1. **Scope of this pass.** Do you want me to (a) execute the full rename/move plan above and update all README links, or (b) do it in slices (e.g. STM first, then LTM, then integrations)?
2. **Empty placeholder scripts.** Today there are ~17 zero-line `.py` files. Should I (a) author working content for each as part of this pass, (b) leave them empty and clearly mark as "TODO" in each new sub-feature README, or (c) delete them until content exists?
3. **Test runner / report card.** OK to delete `TEST_REPORT_CARD.md`, `rerun_fixed2.py`, `run_tests.py` from the tutorials tree, or should they move elsewhere in the repo?
4. **Streaming use cases location.** Move under `02-long-term-memory/09-record-streaming/examples/` (my proposal), keep in `03-advanced-patterns/`, or both with a cross-link?
5. **Feature numbering.** Going from 4 to 5 top-level feature buckets (split observability out, rename security). OK, or keep 4 and leave observability inside integrations/security?

---

## To-do (executed once user signs off)

Phase 0 — root cleanup

- [ ] Delete or relocate: `TEST_REPORT_CARD.md`, `journal.md`, `rerun_fixed2.py`, `run_tests.py`
- [ ] Refresh top-level `README.md` to match the new tree

Phase 1 — short-term memory

- [ ] Add `01-short-term-memory/README.md` (standard usage + best practices)
- [ ] Add `01-short-term-memory/standard-usage.py`
- [ ] Convert each placeholder under `01-core-features/` into `<NN-name>/README.md` + `<name>.py` (folder per sub-feature)
- [ ] Move `02-single-agent/` and `03-multi-agent/` under `examples/`

Phase 2 — long-term memory

- [ ] Add `02-long-term-memory/README.md` + `standard-usage.py`
- [ ] Convert each placeholder under `01-core-features/` into a sub-feature folder
- [ ] Promote `01-built-in-strategies/` to a top-level sub-feature; folder per strategy if needed
- [ ] Move single/multi-agent example trees under `examples/`
- [ ] Pull streaming use cases from `03-advanced-patterns/05-streaming-use-cases/` under `09-record-streaming/examples/`

Phase 3 — integrations / observability / security

- [ ] Rename `03-advanced-patterns/` → `03-integrations/` (drop streaming-use-cases, drop observability)
- [ ] Promote observability to `04-observability/` with README + script
- [ ] Rename `04-security-patterns/` → `05-security/`; convert KMS placeholder into a folder + README + script
- [ ] Add per-folder READMEs that follow the same shape: what / when to use / best practices / link to examples

Phase 4 — verification

- [ ] Walk every README link, confirm no dangling references after moves
- [ ] Update top-level README and `00-getting-started/README.md` "where to go next" pointers

---

## Things done

- [x] Read AgentCore Memory developer guide and key sub-pages (memory types, strategies, organization, terminology, streaming, best practices, observability, RAG comparison)
- [x] Surveyed existing tutorial tree (READMEs + file sizes)
- [x] Wrote `documentation.md` summarizing service features
- [x] Drafted this notes/plan document
