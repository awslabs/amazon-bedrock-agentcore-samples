# Namespaces and organisation

Namespaces are hierarchical paths that scope long-term memory records. They drive both **retrieval** (where the agent reads from) and **IAM scoping** (which records a principal is allowed to touch). Get them right on day one — they are hard to migrate later.

## Templates

Namespace templates substitute runtime variables from the event: `{actorId}`, `{sessionId}`, and `{memoryStrategyId}`. This sample uses one template:

```
/facts/{actorId}/
```

## Multi-tenancy: put the tenant in the actorId

`actorId` is just a string — it may contain `/`. The sample writes events for both shapes under the same template:

| actorId | Resolved namespace |
|---|---|
| `user1` | `/facts/user1/` |
| `user2` | `/facts/user2/` |
| `tenantA/user1` | `/facts/tenantA/user1/` |
| `tenantA/user2` | `/facts/tenantA/user2/` |

Because the tenant becomes a path segment, `namespacePath` filters at every level:

| Query | Returns |
|---|---|
| `namespace="/facts/user1/"` | one user (exact match) |
| `namespacePath="/facts/tenantA/"` | every user under tenantA, nobody else |
| `namespacePath="/facts/"` | everything — plain users and all tenants |

For hard isolation, scope each tenant's runtime role with a `namespacePath` IAM condition — see [`../../05-security/01-iam-scoped-access/`](../../05-security/01-iam-scoped-access/).

## Always start *and* end every namespace with `/`

Every template and every retrieval argument must be `/segment/.../` — leading and trailing slash. A retrieval without a trailing slash is rejected, and the trailing slash is what keeps `/facts/user1/` from also matching `user10`. Mixing `facts/user1/` and `/facts/user1/` creates two namespaces that never match each other.

## Run

```bash
pip install boto3 "bedrock-agentcore>=1.14"
python namespaces-and-organization.py boto3   # default — direct service calls
python namespaces-and-organization.py sdk     # AgentCore MemorySessionManager
```

Both paths create the memory, write events for the four actors above, and run the three queries (exact user, one tenant, everything). Add `--cleanup` to delete the memory at the end.

## AWS CLI walkthrough

```bash
# 1. Create memory
aws bedrock-agentcore-control create-memory \
  --region "$AWS_REGION" --name "NamespacesCli-$(date +%s)" \
  --event-expiry-duration 30 --client-token "$(uuidgen)" \
  --memory-strategies '[{"semanticMemoryStrategy":{"name":"Facts","namespaceTemplates":["/facts/{actorId}/"]}}]'
export MEMORY_ID=<id>

# 2. Events — plain and tenant-qualified actorIds
for actor in user1 user2 tenantA/user1 tenantA/user2; do
  aws bedrock-agentcore create-event \
    --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
    --actor-id "$actor" --session-id "sess-${actor//\//-}" \
    --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --payload "[{\"conversational\":{\"role\":\"USER\",\"content\":{\"text\":\"hi from $actor\"}}}]"
done
sleep 60

# 3. Exact: one user
aws bedrock-agentcore retrieve-memory-records \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --namespace "/facts/user1/" \
  --search-criteria '{"searchQuery":"user1","topK":5}'

# 4. Hierarchical: one tenant only
aws bedrock-agentcore retrieve-memory-records \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --namespace-path "/facts/tenantA/" \
  --search-criteria '{"searchQuery":"tenantA users","topK":20}'

# 5. Hierarchical: everything
aws bedrock-agentcore retrieve-memory-records \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --namespace-path "/facts/" \
  --search-criteria '{"searchQuery":"all users","topK":20}'

# 6. Teardown
aws bedrock-agentcore-control delete-memory \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" --client-token "$(uuidgen)"
```

## Best practices

- **Lead with the data type, then actor** — `/facts/{actorId}/` keeps one queryable tree whether actorIds are flat or tenant-qualified.
- **For multi-tenancy, encode the tenant in the actorId** (`tenantA/user1`) — no schema change needed, and `namespacePath` gives you per-tenant queries for free.
- **Always start and end with `/`** in templates, `namespace=`, `namespacePath=`, and IAM conditions alike.
- **Pair with IAM.** Once the shape is fixed, scope runtime roles with `bedrock-agentcore:namespace` / `namespacePath` conditions.
