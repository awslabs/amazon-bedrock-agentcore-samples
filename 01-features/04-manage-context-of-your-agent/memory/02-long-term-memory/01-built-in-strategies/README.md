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
python semantic.py cli          # print equivalent AWS CLI commands
```

`summary.py`, `user-preference.py`, and `episodic.py` all support the same `boto3 | sdk | cli` surfaces. Each script creates a memory resource, drives a short conversation, waits ~60–90s for asynchronous extraction, retrieves the resulting records, and tears down.

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
