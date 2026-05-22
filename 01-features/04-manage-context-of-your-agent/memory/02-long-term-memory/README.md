# Long-term memory

Long-term memory turns raw conversation events into structured, reusable records — facts, summaries, preferences, and episodes — organised in namespaces and retrieved by semantic search.

Run the canonical end-to-end flow first:

```bash
pip install boto3 bedrock-agentcore
python standard-usage.py boto3   # default — direct service calls
python standard-usage.py sdk     # AgentCore MemoryClient helpers
python standard-usage.py cli     # print equivalent AWS CLI commands
```

It creates a memory with a semantic strategy, sends a few `CreateEvent` calls, waits for extraction, and retrieves the resulting records. Every sub-feature script supports the same three surfaces.

## Sub-features

| Folder | What it covers |
|---|---|
| [`01-built-in-strategies/`](./01-built-in-strategies/) | The four built-in extractors: semantic, summary, user preference, episodic |
| [`02-strategy-overrides/`](./02-strategy-overrides/) | Customise built-in extraction and consolidation prompts |
| [`03-self-managed-strategy/`](./03-self-managed-strategy/) | Plug your own extraction worker via SNS + S3 with message/token/time triggers |
| [`04-namespaces/`](./04-namespaces/) | Template variables, exact vs. prefix matching, multi-tenancy |
| [`05-retrieval/`](./05-retrieval/) | `RetrieveMemoryRecords`, `ListMemoryRecords`, `GetMemoryRecord` |
| [`06-record-metadata/`](./06-record-metadata/) | `indexedKeys`, structured metadata, `metadataFilters` |
| [`07-batch-apis/`](./07-batch-apis/) | Direct CRUD with `BatchCreate/Update/DeleteMemoryRecords` |
| [`08-redrive/`](./08-redrive/) | List failed extraction jobs and restart them with `StartMemoryExtractionJob` |
| [`09-record-streaming/`](./09-record-streaming/) | Push lifecycle events to Kinesis for event-driven pipelines |

## The four built-in strategies

| Strategy | Extracts | Typical namespace |
|---|---|---|
| **Semantic** | Standalone facts about the world | `/users/{actorId}/facts/` |
| **Summary** | Rolling conversation summaries | `/sessions/{sessionId}/summary/` |
| **User Preference** | Stable per-user settings | `/users/{actorId}/preferences/` |
| **Episodic** | Meaningful interaction sequences | `/episodes/{actorId}/` |

Built-in strategies can be **overridden** to swap their extraction or consolidation prompts (`02-strategy-overrides/`), or replaced entirely with a **self-managed** worker (`03-self-managed-strategy/`).

## Framework integrations

End-to-end agent examples live under `examples/`:

- [`examples/single-agent/`](./examples/single-agent/) — Strands, LangGraph, LlamaIndex with hooks, callbacks, memory-block and memory-as-tool patterns.
- [`examples/multi-agent/`](./examples/multi-agent/) — Multi-agent flows with shared LTM (travel booking, healthcare).

## Best practices

- **Pick a namespace template before you write.** `{actorId}` and `{sessionId}` are the two stable hooks; everything else flows from them.
- **Wait for extraction.** Long-term records appear ~30–60 seconds after `CreateEvent`. Don't retrieve immediately.
- **Pin retrieval to a namespace.** Cross-namespace search is rarely what you want and pulls noise.
- **Use `metadataFilters` for hard constraints** (region, tier, language) — they're enforced at the index, not in the prompt.
- **Subscribe to streaming for downstream pipelines.** Polling for changes is the wrong default at any non-trivial scale.
- **Redrive failed jobs deliberately.** Read `failureReason` first; blind retries cost tokens and rarely help.

## Where to next

- Observability for memory operations: [`../04-observability/`](../04-observability/)
- IAM, encryption, multi-tenant isolation: [`../05-security/`](../05-security/)
- Streaming use cases (cross-region, recommendations, analytics): [`./09-record-streaming/examples/`](./09-record-streaming/examples/)
