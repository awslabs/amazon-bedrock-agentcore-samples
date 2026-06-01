# Namespaces and organisation

Namespaces are hierarchical paths that scope long-term memory records. They drive both **retrieval** (where the agent reads from) and **IAM scoping** (which records a principal is allowed to touch). Get them right on day one — they are hard to migrate later.

## Templates

Namespace templates substitute the runtime variables from the event:

| Variable | Source | Example expanded |
|---|---|---|
| `{actorId}` | `actorId` on `CreateEvent` | `alice` |
| `{sessionId}` | `sessionId` on `CreateEvent` | `sess-2025-09-04-01` |
| `{memoryStrategyId}` | the strategy that produced the record | `strategy-abc123` |

## Granularity choices

| Goal | Pattern |
|---|---|
| One record-set per session per strategy | `/strategy/{memoryStrategyId}/actor/{actorId}/session/{sessionId}/` |
| One record-set per user across sessions | `/strategy/{memoryStrategyId}/actor/{actorId}/` |
| One record-set per strategy across users | `/strategy/{memoryStrategyId}/` |
| Global | `/` |

## Trailing slash matters

`/users/alice` is a *prefix* of both `/users/alice/` and `/users/alice2/`. Always end namespace templates with `/` so prefix-style retrieval (`namespacePath=`) and IAM `namespacePath` conditions don't accidentally match a sibling actor.

## Retrieval modes

| Parameter | Behaviour |
|---|---|
| `namespace=` | Exact namespace match |
| `namespacePath=` | Hierarchical match — every record whose namespace starts with the path |

## Run

```bash
pip install boto3 bedrock-agentcore
python namespaces-and-organization.py boto3   # default — direct service calls
python namespaces-and-organization.py sdk     # AgentCore MemoryClient helpers
```

## Best practices

- **Pick the actor-stable form first.** `/users/{actorId}/...` should be your baseline — it lets you query a user across sessions.
- **Always end with `/`** in templates and queries, to avoid `alice` vs `alice2` collisions.
- **Reuse templates across strategies** when the same scoping makes sense (`/users/{actorId}/facts/`, `/users/{actorId}/preferences/`).
- **Pair with IAM.** Once your namespace shape is fixed, scope runtime roles with `bedrock-agentcore:namespace` / `namespacePath` conditions — see [`../../05-security/01-iam-scoped-access/`](../../05-security/01-iam-scoped-access/).

## AWS CLI walkthrough

The same flow expressed with the AWS CLI:

```bash
# 1. Create memory with two strategies on different namespace shapes.
aws bedrock-agentcore-control create-memory \
  --region "$AWS_REGION" --name "NamespacesCli-$(date +%s)" \
  --event-expiry-duration 30 --client-token "$(uuidgen)" \
  --memory-strategies '[
    {"semanticMemoryStrategy": {
      "name":"Facts",
      "namespaces":["/users/{actorId}/facts/"]
    }},
    {"summaryMemoryStrategy": {
      "name":"Summaries",
      "namespaces":["/users/{actorId}/sessions/{sessionId}/summary/"]
    }}
  ]'
export MEMORY_ID=<id>

# 2. Drive turns for two actors
for actor in alice bob; do
  aws bedrock-agentcore create-event \
    --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
    --actor-id "$actor" --session-id "${actor}-sess" \
    --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --payload "[{\"conversational\":{\"role\":\"USER\",\"content\":{\"text\":\"hi from $actor\"}}}]"
done
sleep 60

# 3. Exact-namespace query: only Alice's facts
aws bedrock-agentcore retrieve-memory-records \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --namespace "/users/alice/facts/" \
  --search-criteria '{"searchQuery":"alice","topK":5}'

# 4. Hierarchical query: everything under /users/*
aws bedrock-agentcore retrieve-memory-records \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --namespace-path "/users/" \
  --search-criteria '{"searchQuery":"all users","topK":20}'

# 5. Teardown
aws bedrock-agentcore-control delete-memory \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" --client-token "$(uuidgen)"
```
