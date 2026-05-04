# AgentCore Memory Tutorials — Finalized Restructure Plan

## Guiding principle

Organize **by memory type → feature/pattern → framework**. The choice of access surface (CLI, boto3, AgentCore SDK) is a per-notebook decision, not a tree axis — surfaces are interchangeable outside of onboarding.

The one exception is `00-getting-started/`, which teaches the vocabulary and then shows the **same end-to-end flow** three ways (CLI, boto3, AgentCore SDK) with a "when to use which" decision guide.

---

## AgentCore Memory features (reference)

| Area | Features |
|---|---|
| **Memory types** | Short-term (events, sessions, actors), Long-term (extracted records) |
| **Short-term features** | `CreateEvent`/`ListEvents`/`GetEvent`, event metadata, branching, session/actor isolation |
| **Long-term strategies** | Built-in (Semantic / Summary / User Preference / Episodic), Built-in with overrides, Self-managed |
| **Organization** | Namespaces (`{actorId}`/`{sessionId}`/`{strategyId}`), record metadata |
| **Retrieval** | `RetrieveMemoryRecords`, `ListMemoryRecords`, `GetMemoryRecord`, citations |
| **Lifecycle** | Batch create/update/delete, redrive failed ingestions |
| **Streaming** | Memory record streaming → Kinesis (METADATA_ONLY / FULL_CONTENT) |
| **Security** | KMS, IAM conditions on namespace/actorId/sessionId, Cognito federation |
| **Integrations** | Runtime, Identity, Browser, Bedrock Guardrails |
| **Framework SDKs** | boto3, AgentCore SDK (`MemoryClient`), Strands, LangChain/LangGraph, LlamaIndex |

---

## Three integration patterns per framework

| Pattern | What it is | When to use |
|---|---|---|
| **Built-in hooks** | Framework's out-of-the-box AgentCore memory hook | Fastest path; standard save/retrieve lifecycle |
| **Custom hook** | Subclass/implement your own hook | Conditional logic, custom retrieval, multi-strategy orchestration |
| **Memory-as-tool** | Expose memory operations as tools the agent calls | Agent decides when to recall/save |

---

## Finalized tree

```
04-AgentCore-memory/
│
├── 00-getting-started/
│   ├── 01-memory-concepts.md                     # actor/session/event/strategy/namespace/record
│   ├── 02-choosing-your-surface.md               # CLI vs boto3 vs AgentCore SDK decision guide
│   ├── 03-quickstart-cli.md                      # same flow end-to-end, CLI
│   ├── 04-quickstart-boto3.ipynb                 # same flow, raw boto3
│   └── 05-quickstart-agentcore-sdk.ipynb         # same flow, MemoryClient
│
├── 01-short-term-memory/
│   ├── 01-core-features/                         # framework-agnostic primitives
│   │   ├── 01-events-and-sessions.ipynb          # CreateEvent / List / Get / Delete
│   │   ├── 02-event-metadata-filtering.ipynb
│   │   ├── 03-actor-session-isolation.ipynb
│   │   └── 04-event-branching.ipynb              # branchId primitive
│   │
│   ├── 02-single-agent/
│   │   ├── with-strands-agent/
│   │   │   ├── 01-built-in-hook.ipynb
│   │   │   ├── 02-custom-hook.ipynb
│   │   │   ├── 03-memory-tool.ipynb
│   │   │   └── 04-branching-example.ipynb
│   │   ├── with-langgraph-agent/
│   │   │   ├── 01-built-in-checkpointer.ipynb
│   │   │   ├── 02-custom-callback.ipynb
│   │   │   └── 03-memory-tool.ipynb
│   │   └── with-llamaindex-agent/
│   │       ├── 01-built-in-memory-block.ipynb
│   │       ├── 02-custom-memory-block.ipynb
│   │       └── 03-memory-tool.ipynb
│   │
│   └── 03-multi-agent/
│       └── with-strands-agent/
│           ├── 01-built-in-hook.ipynb
│           ├── 02-custom-hook.ipynb
│           └── 03-parallel-branches-example.ipynb
│
├── 02-long-term-memory/
│   ├── 01-core-features/                         # framework-agnostic primitives
│   │   ├── 01-built-in-strategies/
│   │   │   ├── semantic.ipynb
│   │   │   ├── summary.ipynb
│   │   │   ├── user-preference.ipynb
│   │   │   └── episodic.ipynb
│   │   ├── 02-strategies-with-overrides.ipynb
│   │   ├── 03-self-managed-strategy.ipynb
│   │   ├── 04-namespaces-and-organization.ipynb
│   │   ├── 05-retrieve-records-and-citations.ipynb
│   │   ├── 06-structured-metadata.ipynb
│   │   ├── 07-batch-create-update-delete.ipynb
│   │   ├── 08-redrive-failed-ingestions.ipynb
│   │   └── 09-record-streaming.ipynb             # streaming primitive
│   │
│   ├── 02-single-agent/
│   │   ├── with-strands-agent/
│   │   │   ├── 01-built-in-hook/                 # customer-support, math, meeting-notes
│   │   │   ├── 02-custom-hook/                   # customer-support override, self-managed, self-managed-with-citations
│   │   │   └── 03-memory-tool/                   # culinary, debugging (episodic)
│   │   ├── with-langgraph-agent/
│   │   │   ├── 01-built-in-callback/
│   │   │   ├── 02-custom-callback/               # nutrition (user prefs, episodic)
│   │   │   └── 03-memory-tool/
│   │   └── with-llamaindex-agent/
│   │       ├── 01-built-in-memory-block/
│   │       ├── 02-custom-memory-block/
│   │       └── 03-memory-tool/                   # medical, academic, legal, investment
│   │
│   └── 03-multi-agent/
│       └── with-strands-agent/
│           ├── 01-built-in-hook/                 # travel-booking
│           └── 02-custom-hook/                   # healthcare (episodic)
│
├── 03-advanced-patterns/                         # composite use cases built on primitives
│   ├── 01-runtime-integration/
│   ├── 02-identity-integration/
│   ├── 03-guardrails-integration/
│   ├── 04-memory-browser/
│   ├── 05-streaming-use-cases/
│   │   ├── 01-cross-region-replication/
│   │   ├── 02-personalised-recommendations.ipynb
│   │   └── 03-cross-customer-analytics.ipynb
│   └── 06-observability.ipynb                    # CloudWatch metrics/logs
│
└── 04-security-patterns/
    ├── 01-iam-scoped-access/
    ├── 02-cognito-federated-identity/
    └── 03-kms-encryption.ipynb
```

---

## Primitive vs. use case split

| Primitive (core-features) | Use case (advanced-patterns or framework folders) |
|---|---|
| `01-short-term-memory/01-core-features/04-event-branching.ipynb` | `01-short-term-memory/02-single-agent/with-strands-agent/04-branching-example.ipynb` (travel planner)<br>`01-short-term-memory/03-multi-agent/with-strands-agent/03-parallel-branches-example.ipynb` |
| `02-long-term-memory/01-core-features/09-record-streaming.ipynb` | `03-advanced-patterns/05-streaming-use-cases/*` (cross-region, recommendations, analytics) |

Rule: if the notebook teaches **how the feature works**, it's a primitive. If it **composes the feature with other services or agent logic**, it's a use case.

---

## Mapping existing notebooks → new paths

### Short-term memory (single-agent)

| Current | New path |
|---|---|
| `01-short-term-memory/01-single-agent/with-strands-agent/personal-agent.ipynb` | `01-short-term-memory/02-single-agent/with-strands-agent/personal-agent.ipynb` |
| `01-short-term-memory/01-single-agent/with-strands-agent/personal-agent-memory-manager.ipynb` | same folder, filename preserved |
| `01-short-term-memory/01-single-agent/with-langgraph-agent/*` | `01-short-term-memory/02-single-agent/with-langgraph-agent/` |
| `01-short-term-memory/01-single-agent/with-llamaindex-agent/*` | `01-short-term-memory/02-single-agent/with-llamaindex-agent/` |
| `04-memory-branching/travel-planning-agent-with-memory-branching.ipynb` | `01-short-term-memory/02-single-agent/with-strands-agent/` |

### Short-term memory (multi-agent)

| Current | New path |
|---|---|
| `01-short-term-memory/02-multi-agent/with-strands-agent/*` | `01-short-term-memory/03-multi-agent/with-strands-agent/` |
| `04-memory-branching/multi-agent-parallel-execution-with-memory-branching.ipynb` | `01-short-term-memory/03-multi-agent/with-strands-agent/` |

### Long-term memory (single-agent, Strands)

| Current | New path |
|---|---|
| `using-strands-agent-hooks/customer-support/customer-support-inbuilt-strategy.ipynb` | `with-strands-agent/01-built-in-hook/customer-support/` |
| `using-strands-agent-hooks/customer-support/customer-support-override-strategy.ipynb` | `with-strands-agent/02-custom-hook/customer-support/` |
| `using-strands-agent-hooks/simple-math-assistant/` | `with-strands-agent/01-built-in-hook/simple-math-assistant/` |
| `using-strands-agent-hooks/meeting-notes-assistant-using-episodic/` | `with-strands-agent/01-built-in-hook/meeting-notes-assistant-using-episodic/` |
| `using-strands-agent-hooks/culinary-assistant-self-managed-strategy/` | `with-strands-agent/02-custom-hook/culinary-assistant-self-managed-strategy/` |
| `using-strands-agent-hooks/culinary-assistant-self-managed-strategy-with-citations/` | `with-strands-agent/02-custom-hook/culinary-assistant-self-managed-strategy-with-citations/` |
| `using-strands-agent-memory-tool/culinary-assistant.ipynb` | `with-strands-agent/03-memory-tool/culinary-assistant.ipynb` |
| `using-strands-agent-memory-tool/debugging-agent/` | `with-strands-agent/03-memory-tool/debugging-agent/` |

### Long-term memory (single-agent, LangGraph & LlamaIndex)

| Current | New path |
|---|---|
| `using-langgraph-agent-hooks/episodic-memory/` | `with-langgraph-agent/02-custom-callback/episodic-memory/` |
| `using-langgraph-agent-hooks/custom-user-preferences/` | `with-langgraph-agent/02-custom-callback/custom-user-preferences/` |
| `using-llamaindex-agent-memory-tool/*` | `with-llamaindex-agent/03-memory-tool/` |

### Long-term memory (multi-agent)

| Current | New path |
|---|---|
| `02-long-term-memory/02-multi-agent/with-strands-agent/travel-booking-agent/` | `02-long-term-memory/03-multi-agent/with-strands-agent/01-built-in-hook/travel-booking-agent/` |
| `02-long-term-memory/02-multi-agent/with-strands-agent/healthcare-assistant-using-episodic/` | `02-long-term-memory/03-multi-agent/with-strands-agent/02-custom-hook/healthcare-assistant-using-episodic/` |

### Advanced patterns

| Current | New path |
|---|---|
| `03-advanced-patterns/02-memory-runtime-integration/` | `03-advanced-patterns/01-runtime-integration/` |
| `03-advanced-patterns/03-memory-identity-runtime-integration/` | `03-advanced-patterns/02-identity-integration/` |
| `03-advanced-patterns/01-guardrails-integration/` | `03-advanced-patterns/03-guardrails-integration/` |
| `03-advanced-patterns/04-memory-browser/` | unchanged |
| `03-advanced-patterns/05-memory-streaming/memory_record_streaming.ipynb` | `02-long-term-memory/01-core-features/09-record-streaming.ipynb` |
| `03-advanced-patterns/06-streaming-for-cross-region-replication/` | `03-advanced-patterns/05-streaming-use-cases/01-cross-region-replication/` |
| `03-advanced-patterns/07-memory-for-personalisation-and-analytics/01-*` | `03-advanced-patterns/05-streaming-use-cases/02-personalised-recommendations.ipynb` |
| `03-advanced-patterns/07-memory-for-personalisation-and-analytics/02-*` | `03-advanced-patterns/05-streaming-use-cases/03-cross-customer-analytics.ipynb` |

### Security

| Current | New path |
|---|---|
| `05-memory-security-patterns/01-memory-iam-policies/` | `04-security-patterns/01-iam-scoped-access/` |
| `05-memory-security-patterns/02-memory-iam-cognito-identities/` | `04-security-patterns/02-cognito-federated-identity/` |

---

## Gaps (documented as follow-up work in per-folder READMEs)

**New content required:**

- `00-getting-started/*` — concepts, surface-decision guide, three quickstarts
- `01-short-term-memory/01-core-features/*` — all four STM primitive notebooks
- `02-long-term-memory/01-core-features/*` except 09-record-streaming — all LTM primitives
- `02-long-term-memory/02-single-agent/with-langgraph-agent/{01-built-in-callback,03-memory-tool}/` — framework × pattern gaps
- `02-long-term-memory/02-single-agent/with-llamaindex-agent/{01-built-in-memory-block,02-custom-memory-block}/` — framework × pattern gaps
- `03-advanced-patterns/06-observability.ipynb`
- `04-security-patterns/03-kms-encryption.ipynb`

**Framework × pattern classification still to verify** (notebooks kept with original filenames in this pass):
- STM Strands/LangGraph/LlamaIndex single-agent notebooks — intended pattern split noted in per-folder READMEs
- STM Strands multi-agent notebooks — same
