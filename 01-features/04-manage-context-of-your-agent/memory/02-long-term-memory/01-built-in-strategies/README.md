# Built-in memory strategies

Built-in strategies are managed extraction pipelines that turn raw events into structured long-term memory records. AgentCore handles the prompt, the model, and the schema — you only pick which strategies to enable on your memory resource and where the records land (via namespace templates).

## The four strategies

| Strategy | Extracts | Pipeline steps | Default namespace pattern |
|---|---|---|---|
| **Semantic** ([semantic.py](./semantic.py)) | Standalone facts about the user/world | Extraction → Consolidation | `/users/{actorId}/facts/` |
| **Summary** ([summary.py](./summary.py)) | Rolling conversation summary | Consolidation | `/sessions/{sessionId}/summary/` |
| **User preference** ([user-preference.py](./user-preference.py)) | Stable per-user preferences | Extraction → Consolidation | `/users/{actorId}/preferences/` |
| **Episodic** ([episodic.py](./episodic.py)) | Meaningful interaction sequences + cross-episode reflection | Extraction → Consolidation → Reflection | `/episodes/{actorId}/` |

A single memory resource can host any combination of these; records land in distinct namespaces so retrieval stays clean.

## Run

```bash
pip install boto3 bedrock-agentcore
python semantic.py boto3        # default — direct service calls
python semantic.py sdk          # AgentCore MemoryClient helpers
```

`summary.py`, `user-preference.py`, and `episodic.py` all support the same `boto3 | sdk` surfaces. Each script creates a memory resource, drives a short conversation, waits ~60–90s for asynchronous extraction, retrieves the resulting records, and tears down.

## Best practices

- **Default to built-in.** They cover the common cases without you maintaining a prompt or model.
- **Pick the namespace template up front.** Use `{actorId}` for per-user data, `{sessionId}` for per-session data, and a trailing `/` to avoid prefix collisions.
- **Combine strategies deliberately.** Semantic + user-preference is a great baseline; add summary for long sessions and episodic for stateful, multi-session workflows.
- **Asynchronous, not free.** Each extraction step calls a Bedrock model in your account; high-volume sessions cost more than retrieval-only workloads.
- **Verify with retrieval.** Drive a representative conversation and inspect what comes back — that's the fastest way to tune namespace and strategy choice.

## Where to go next

- Tweak the prompt or model on a built-in strategy: [`../02-strategy-overrides/`](../02-strategy-overrides/)
- Own the entire extraction pipeline: [`../03-self-managed-strategy/`](../03-self-managed-strategy/)
- Organise records across actors/sessions/strategies: [`../04-namespaces/`](../04-namespaces/)

## AWS CLI walkthrough

The same flow expressed with the AWS CLI, one section per strategy.

### Semantic

```bash
# 1. Create memory with a semantic strategy
aws bedrock-agentcore-control create-memory \
  --region "$AWS_REGION" --name "SemanticCli-$(date +%s)" \
  --event-expiry-duration 30 --client-token "$(uuidgen)" \
  --memory-strategies '[{
    "semanticMemoryStrategy": {
      "name": "UserFacts",
      "description": "Standalone facts about the user",
      "namespaces": ["/users/{actorId}/facts/"]
    }
  }]'
export MEMORY_ID=<id>

# 2. Drive a short conversation
aws bedrock-agentcore create-event \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --actor-id user-alex --session-id sess-cli \
  --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --payload '[{"conversational":{"role":"USER","content":{"text":"I prefer Python and live in Berlin."}}}]'

# 3. Wait for extraction (~60s) and retrieve
sleep 60
aws bedrock-agentcore retrieve-memory-records \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --namespace "/users/user-alex/facts/" \
  --search-criteria '{"searchQuery":"language preference?","topK":3}'

# 4. Teardown
aws bedrock-agentcore-control delete-memory \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" --client-token "$(uuidgen)"
```

### Summary

```bash
# 1. Create memory with a summary strategy. Summaries are typically per-session.
aws bedrock-agentcore-control create-memory \
  --region "$AWS_REGION" --name "SummaryCli-$(date +%s)" \
  --event-expiry-duration 30 --client-token "$(uuidgen)" \
  --memory-strategies '[{
    "summaryMemoryStrategy": {
      "name": "SessionSummary",
      "description": "Rolling conversation summary",
      "namespaces": ["/sessions/{sessionId}/summary/"]
    }
  }]'
export MEMORY_ID=<id>

# 2. Drive a multi-turn conversation (loop several create-event calls).
aws bedrock-agentcore create-event \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --actor-id user-alex --session-id sess-cli \
  --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --payload '[{"conversational":{"role":"USER","content":{"text":"Plan a 10-day trip to Japan."}}}]'
# ... repeat for additional turns ...

# 3. Wait ~75s for consolidation, then retrieve the rolling summary.
sleep 75
aws bedrock-agentcore retrieve-memory-records \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --namespace "/sessions/sess-cli/summary/" \
  --search-criteria '{"searchQuery":"trip plan","topK":5}'

# 4. Teardown
aws bedrock-agentcore-control delete-memory \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" --client-token "$(uuidgen)"
```

### User preference

```bash
# 1. Create memory with a user-preference strategy
aws bedrock-agentcore-control create-memory \
  --region "$AWS_REGION" --name "UserPrefCli-$(date +%s)" \
  --event-expiry-duration 30 --client-token "$(uuidgen)" \
  --memory-strategies '[{
    "userPreferenceMemoryStrategy": {
      "name": "UserPreferences",
      "description": "Stable preferences across sessions",
      "namespaces": ["/users/{actorId}/preferences/"]
    }
  }]'
export MEMORY_ID=<id>

# 2. Mention a few preferences
aws bedrock-agentcore create-event \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --actor-id user-alex --session-id sess-cli \
  --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --payload '[{"conversational":{"role":"USER","content":{"text":"I prefer window seats and email notifications."}}}]'

# 3. Wait ~60s, then retrieve
sleep 60
aws bedrock-agentcore retrieve-memory-records \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --namespace "/users/user-alex/preferences/" \
  --search-criteria '{"searchQuery":"preferences","topK":10}'

# 4. Teardown
aws bedrock-agentcore-control delete-memory \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" --client-token "$(uuidgen)"
```

### Episodic

```bash
# 1. Create memory with an episodic strategy
aws bedrock-agentcore-control create-memory \
  --region "$AWS_REGION" --name "EpisodicCli-$(date +%s)" \
  --event-expiry-duration 30 --client-token "$(uuidgen)" \
  --memory-strategies '[{
    "episodicMemoryStrategy": {
      "name": "Episodes",
      "description": "Meaningful interaction sequences",
      "namespaces": ["/episodes/{actorId}/"]
    }
  }]'
export MEMORY_ID=<id>

# 2. Drive a multi-turn session that forms one episode (loop several events).
aws bedrock-agentcore create-event \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --actor-id user-alex --session-id debug-sess \
  --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --payload '[{"conversational":{"role":"USER","content":{"text":"Memory leak after deploy."}}}]'
# ... repeat to form a coherent episode ...

# 3. Wait ~90s for extraction + reflection, then retrieve.
sleep 90
aws bedrock-agentcore retrieve-memory-records \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --namespace "/episodes/user-alex/" \
  --search-criteria '{"searchQuery":"memory leak debugging","topK":3}'

# 4. Teardown
aws bedrock-agentcore-control delete-memory \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" --client-token "$(uuidgen)"
```
