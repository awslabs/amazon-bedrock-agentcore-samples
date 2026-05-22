# Short-term memory

Short-term memory stores raw conversation turns (events) scoped to an `actorId` and a `sessionId`. It gives the agent immediate, low-latency access to the current conversation — no extraction, no embeddings, no background pipeline.

## Standard usage

[`standard-usage.py`](./standard-usage.py) is the canonical flow: create a memory resource, wait for `ACTIVE`, append a few events with `CreateEvent`, list them back with `ListEvents`, fetch one with `GetEvent`, delete the memory.

```bash
pip install boto3 bedrock-agentcore
python standard-usage.py boto3   # default — direct service calls
python standard-usage.py sdk     # AgentCore MemoryClient helpers
```

Every sub-feature script supports the same three surfaces.

## Sub-features

| # | Folder | What it teaches |
|---|---|---|
| 01 | [`01-events-and-sessions/`](./01-events-and-sessions/) | The CreateEvent / ListEvents / GetEvent / ListSessions loop |
| 02 | [`02-event-metadata/`](./02-event-metadata/) | Tagging events with metadata and filtering with `EQUALS_TO`, `EXISTS`, `NOT_EXISTS` |
| 03 | [`03-actor-session-isolation/`](./03-actor-session-isolation/) | One memory resource, many actors, no cross-actor leakage |
| 04 | [`04-branching/`](./04-branching/) | Forking a session for what-if flows or parallel sub-agents |

## Examples

Framework integrations live under [`examples/`](./examples/). They wire short-term memory into Strands, LangGraph, and LlamaIndex agents using three common patterns:

| Pattern | What it is | When to use |
|---|---|---|
| **Built-in hook** | Framework's out-of-the-box AgentCore memory adapter | Fastest path; standard save/retrieve lifecycle |
| **Custom hook** | Your own hook implementation | Conditional logic, custom retrieval, orchestration |
| **memory-as-tool** | Memory operations exposed as tools the LLM calls | Agent decides when to recall/save |

| Subtree | Contents |
|---|---|
| [`examples/single-agent/with-strands-agent/`](./examples/single-agent/with-strands-agent/) | Built-in hook + custom hook; travel-planning branching example |
| [`examples/single-agent/with-langgraph-agent/`](./examples/single-agent/with-langgraph-agent/) | Built-in (`math-agent-with-checkpointing`), custom (`personal-fitness-coach`), tool (`support-agent-human-in-the-loop`) |
| [`examples/single-agent/with-llamaindex-agent/`](./examples/single-agent/with-llamaindex-agent/) | Four domain examples: academic research, investment, legal, medical |
| [`examples/multi-agent/with-strands-agent/`](./examples/multi-agent/with-strands-agent/) | Multi-agent travel planner; `multi-agent-parallel-branches/` shows branch-per-subagent |

## Best practices

- **One conversation = one `sessionId`.** Don't reuse a session across days; start a new one and re-hydrate context with `ListEvents` if needed.
- **Pick a stable `actorId`** that maps to the real user (Cognito `sub`, internal user id) — long-term memory namespaces typically template on it.
- **Use `includePayloads=False`** on `ListEvents` when you only need ids/timestamps; switch to `True` only when you need the content.
- **Cap storage cost with `eventExpiryDuration`** (3–365 days) at memory creation.
- **Don't put sensitive data in event metadata** — metadata is not encrypted with your customer-managed KMS key.
- **Plan branches before you need them.** Decide branch names up front so `ListEvents` filters stay clean.

## Where to go next

- Cross-session persistence: [`../02-long-term-memory/`](../02-long-term-memory/)
- Security and isolation: [`../05-security/`](../05-security/)
- Wire memory into runtime/identity/Guardrails: [`../03-integrations/`](../03-integrations/)

## AWS CLI walkthrough

The same flow expressed with the AWS CLI:

```bash
# 1. Create a memory resource
aws bedrock-agentcore-control create-memory \
  --region "$AWS_REGION" \
  --name "StmStandardCli-$(date +%s)" \
  --event-expiry-duration 30 \
  --client-token "$(uuidgen)"
# Capture memory.id from the response → export MEMORY_ID=...

# 2. Poll until ACTIVE
aws bedrock-agentcore-control get-memory \
  --region "$AWS_REGION" \
  --memory-id "$MEMORY_ID" \
  --query 'memory.status'

# 3. Append three events
for i in 1 2 3; do
  aws bedrock-agentcore create-event \
    --region "$AWS_REGION" \
    --memory-id "$MEMORY_ID" \
    --actor-id user-42 \
    --session-id sess-cli \
    --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --payload "[{\"conversational\":{\"role\":\"USER\",\"content\":{\"text\":\"turn $i\"}}}]"
done

# 4. List events for the session
aws bedrock-agentcore list-events \
  --region "$AWS_REGION" \
  --memory-id "$MEMORY_ID" \
  --actor-id user-42 \
  --session-id sess-cli \
  --include-payloads

# 5. Fetch a single event by id
aws bedrock-agentcore get-event \
  --region "$AWS_REGION" \
  --memory-id "$MEMORY_ID" \
  --actor-id user-42 \
  --session-id sess-cli \
  --event-id <event-id-from-step-4>

# 6. Teardown
aws bedrock-agentcore-control delete-memory \
  --region "$AWS_REGION" \
  --memory-id "$MEMORY_ID" \
  --client-token "$(uuidgen)"
```
