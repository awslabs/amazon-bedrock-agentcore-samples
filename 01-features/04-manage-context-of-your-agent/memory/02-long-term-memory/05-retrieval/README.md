# Retrieving long-term memory records

Three retrieval primitives, picked by the question you're asking:

| API | Use when |
|---|---|
| `RetrieveMemoryRecords` | Relevance-ranked semantic search within a namespace (the common case) |
| `ListMemoryRecords` | You want to browse / enumerate every record in a namespace |
| `GetMemoryRecord` | You already have a `memoryRecordId` and want the full record |

`RetrieveMemoryRecords` accepts either:

- `namespace=` — exact namespace match.
- `namespacePath=` — prefix-style match across a namespace hierarchy.

…plus a `searchCriteria` object with `searchQuery`, `topK` (default 20, max 100), `metadataFilters`, and optional `memoryStrategyId` to constrain to a single strategy.

## Run

```bash
pip install boto3 bedrock-agentcore
python retrieve-records-and-citations.py boto3   # default — direct service calls
python retrieve-records-and-citations.py sdk     # AgentCore MemoryClient helpers (uses gmcp_client for list/get)
python retrieve-records-and-citations.py cli     # print equivalent AWS CLI commands
```

## What's in a result

Each hit returns:

- `memoryRecordId`
- `content.text` — the extracted record
- `score` — relevance, only on `RetrieveMemoryRecords`
- `namespaces` — the namespaces this record was written to
- `memoryStrategyId` — which strategy produced it
- `metadata`, `createdAt`

## Best practices

- **Always pin a namespace.** Unscoped retrieval across all records is rarely what you want and pulls noise.
- **Pick `topK` to fit the LLM context budget.** Pull 3–5 for direct injection; pull more only if you re-rank or filter downstream.
- **Use `metadataFilters` for hard constraints** (`region=EU`, `tier=premium`) — they're enforced at the index, unlike the LLM-side filtering you'd otherwise do.
- **Prefer `namespacePath=` for hierarchical reads** (e.g. all preferences for an actor across strategies) and `namespace=` for exact targeting.
- **Pair with citations.** Surface the namespace + record id when an answer relies on memory — useful for debugging hallucinated extractions.
