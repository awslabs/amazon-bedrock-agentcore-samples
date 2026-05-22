# Amazon Bedrock AgentCore Memory — Feature Digest

Distilled from the AgentCore developer guide. Use this as the "what does the service offer" reference when designing tutorials.

Source: <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html>

---

## 1. What it is

A managed service that stores conversation context for AI agents, so an agent can reason over past turns within a session and remember things across sessions without bespoke storage. Two memory types layer on top of a single memory resource:

- **Short-term memory** — raw events captured per actor + session. Immediate, low-latency context for the current conversation.
- **Long-term memory** — structured records extracted asynchronously from short-term events using _memory strategies_. Persistent insights (facts, preferences, summaries, episodes) that survive across sessions.

A single memory resource can hold short-term events and any number of long-term strategies simultaneously.

---

## 2. Core concepts

| Term                      | Meaning                                                                                                                                                                                             |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **AgentCore Memory**      | Top-level resource (`memoryId`). Holds events + extracted records for an app/agent.                                                                                                                 |
| **Actor** (`actorId`)     | The entity interacting with the agent — usually an end user.                                                                                                                                        |
| **Session** (`sessionId`) | One continuous conversation; groups events.                                                                                                                                                         |
| **Event**                 | Atomic, immutable, timestamped unit of short-term memory. Holds a payload (conversational turns or a blob). Created via `CreateEvent`.                                                              |
| **Event metadata**        | Key-value tags attached to an event for later filtering. Not encrypted with CMK — do not store sensitive content here.                                                                              |
| **Branch** (`branchId`)   | A divergent fork of events from a parent event — for what-if flows or parallel agent branches.                                                                                                      |
| **Memory strategy**       | Configuration (built-in, override, or self-managed) that determines what long-term records are extracted from short-term events.                                                                    |
| **Namespace**             | Hierarchical path scoping long-term records — e.g. `/users/{actorId}/preferences/`. Templated with `{actorId}` / `{sessionId}` / `{strategyId}`. Trailing `/` matters (prevents prefix collisions). |
| **Memory record**         | Structured unit of long-term memory: text + namespace + metadata + strategy.                                                                                                                        |

---

## 3. Short-term memory

### Operations

- `CreateEvent` — append a new event (conversational turns or a blob payload) to a session.
- `ListEvents`, `GetEvent`, `DeleteEvent` — read/manage events.
- `ListSessions` — find prior sessions for an actor.
- Event metadata filters on `ListEvents` for fast lookup without full scans.

### Branching

Each event can fork into branches by setting `branchId` when creating subsequent events. Useful for:

- Exploratory "what-if" turns within a single agent.
- Parallel sub-agents working off a shared parent context.

### Organization

`actorId` + `sessionId` are the only required scoping keys. The same memory resource serves all actors and sessions.

---

## 4. Long-term memory

Long-term memory runs an **asynchronous extraction + consolidation** pipeline over short-term events. Pipeline steps for built-in strategies:

1. **Extraction** — pull insights out of raw events.
2. **Consolidation** — write to a new record or merge with an existing one.
3. **Reflection** (episodic only) — generate cross-episode insights.

If no strategies are configured on a memory, no long-term records are created.

### Built-in strategies

| Strategy            | Extracts                                      | Override-able steps                                      |
| ------------------- | --------------------------------------------- | -------------------------------------------------------- |
| **Semantic**        | Standalone facts about the user/world         | Extraction, Consolidation                                |
| **Summary**         | Rolling summary of the conversation           | Consolidation                                            |
| **User Preference** | Stable per-user settings/preferences          | Extraction, Consolidation                                |
| **Episodic**        | Meaningful interaction sequences ("episodes") | Extraction (turn level and task/goal level) , Reflection |

Multiple strategies can coexist on a single memory.

### Built-in with overrides

Same managed pipeline, but you supply your own:

- Prompt instructions (the **schema is fixed**; only the instructions are editable).
- The Bedrock model used for that step.

Requires `memoryExecutionRoleArn` because Bedrock invocations bill against your account. Bedrock model usage is separately billed.

### Self-managed strategies

You own the entire pipeline. AgentCore handles only storage + retrieval.

Flow:

1. Configure trigger conditions (`messageBasedTrigger`, `tokenBasedTrigger`, `timeBasedTrigger`/idle timeout).
2. AgentCore writes the conversation payload to your S3 bucket and notifies your SNS topic.
3. You run extraction + consolidation (Lambda, ECS, anywhere).
4. You ingest results via `BatchCreateMemoryRecords` / `BatchUpdateMemoryRecords` / `BatchDeleteMemoryRecords`.

Use when you need full control of the schema, the model, or the prompt — or you must integrate external systems.

### Retrieval

- `RetrieveMemoryRecords` — semantic search within a namespace, returns top-K with citations.
- `ListMemoryRecords` — list within a namespace or namespace-path hierarchy.
- `GetMemoryRecord` — fetch one record by id.

### Namespaces

Hierarchical, templated paths. Granularity examples:

| Granularity                | Pattern                                                             |
| -------------------------- | ------------------------------------------------------------------- |
| Most granular              | `/strategy/{memoryStrategyId}/actor/{actorId}/session/{sessionId}/` |
| Per-actor across sessions  | `/strategy/{memoryStrategyId}/actor/{actorId}/`                     |
| Per-strategy across actors | `/strategy/{memoryStrategyId}/`                                     |
| Global                     | `/`                                                                 |

Trailing `/` is mandatory to avoid prefix collisions (e.g. `Alice/` vs `Alice2/`).

### Lifecycle

- `BatchCreateMemoryRecords` / `BatchUpdateMemoryRecords` / `BatchDeleteMemoryRecords` — direct CRUD when you bypass the extraction pipeline.
- `Redrive` — re-run a failed asynchronous ingestion.

---

## 5. Memory record streaming

Push-based delivery of memory record lifecycle events to a Kinesis Data Stream in your account.

- Events: `MemoryRecordCreated`, `MemoryRecordUpdated`, `MemoryRecordDeleted`, plus `StreamingEnabled` validation event.
- Triggered by extraction, batch APIs, and consolidation deletes.
- Content levels: `METADATA_ONLY` (ids, namespaces, timestamps) or `FULL_CONTENT` (adds `memoryRecordText`).
- Configured via `streamDeliveryResources` on `CreateMemory` / `UpdateMemory`. Requires `memoryExecutionRoleArn` with `kinesis:PutRecords`.

Common downstream uses: cross-region replication, real-time personalisation, cross-customer analytics, profile aggregation.

---

## 6. Security and isolation

### Encryption

- At-rest by default with an AWS-owned KMS key.
- Optional customer-managed KMS key via `encryptionKeyArn` on `CreateMemory`.
- Event metadata is **not** CMK-encrypted — keep sensitive data in event content.

### IAM scoping

Three condition keys for `RetrieveMemoryRecords` and related actions:

- `bedrock-agentcore:namespace` — exact namespace match.
- `bedrock-agentcore:namespacePath` — prefix-style match across a namespace hierarchy.
- `bedrock-agentcore:actorId` / `bedrock-agentcore:sessionId` — actor/session scoping.

Use these to enforce per-tenant or per-user isolation at the IAM level.

### Cognito federation

Federate end-user identities into IAM (via Cognito identity pools or `AssumeRoleWithWebIdentity`) so each user gets a session-scoped IAM role. Combine with namespace conditions for per-user memory isolation.

### Memory poisoning / prompt injection

Customer responsibility. Validate / guardrail user input before `CreateEvent`. Test with DAST and prompt-injection probes.

---

## 7. Observability

CloudWatch metrics under the `AWS/Bedrock-AgentCore` namespace.

- Data plane: `Invocations`, `Latency`, `Errors` for `CreateEvent`, `RetrieveMemoryRecords`, etc.
- Ingestion: extraction/consolidation invocations, latency, errors, `NumberOfMemoryRecords`.
- Streaming: `StreamPublishingSuccess`, `StreamPublishingFailure`, `StreamUserError`.
- CloudWatch Logs (when log delivery is enabled) for ingestion debugging and terminal stream-publish failures.

---

## 8. Long-term memory vs RAG

| Concern             | Long-term memory                         | RAG                                      |
| ------------------- | ---------------------------------------- | ---------------------------------------- |
| Question it answers | "Who is the user, what happened before?" | "What do trusted sources say right now?" |
| Source              | Conversation history                     | Curated knowledge base                   |
| Freshness           | User-driven, evolves with interaction    | Authoritative snapshot                   |
| Scope               | Per-user / per-tenant                    | Domain-wide                              |
| Typical pairing     | User personalisation                     | Factual grounding                        |

Use both together: memory for personal context, RAG (e.g. Bedrock Knowledge Bases) for authoritative answers.

---

## 9. Best practices

- Design namespaces hierarchically with trailing `/` from day one — they drive both retrieval and IAM.
- Default to built-in strategies; reach for overrides only for domain-specific extraction; use self-managed when you need schema control or external systems.
- Validate user input before `CreateEvent` to prevent memory poisoning.
- Apply least-privilege IAM with namespace/actor/session conditions.
- Use customer-managed KMS keys for sensitive workloads; don't put sensitive data in event metadata.
- Tune self-managed strategy triggers (`messageCount` / `tokenCount` / idle timeout) to balance freshness vs cost.
- For multi-agent systems, share a single memory resource and use distinct actor IDs (or branches) to isolate contributions.
