# Short-term memory — LangGraph single-agent

Three LangGraph examples that use Amazon Bedrock AgentCore Memory for **short-term**
memory — running context within a conversation, persisted and resumed across turns. The
common thread is the **`AgentCoreMemorySaver` checkpointer** from
[`langgraph-checkpoint-aws`](https://pypi.org/project/langgraph-checkpoint-aws/): pass it
to the agent and LangGraph automatically saves and restores graph state per
`(thread_id, actor_id)`, where `thread_id` maps to the AgentCore **session_id** and
`actor_id` to the AgentCore **actor_id**.

| Example | File | Pattern | Complexity |
|---|---|---|---|
| **Math agent with checkpointing** | [`math-agent-with-checkpointing.py`](./math-agent-with-checkpointing.py) | `AgentCoreMemorySaver` as the checkpointer for automatic state persistence; multi-turn calculations that build on prior context; session isolation across `thread_id`s. | Beginner |
| **Personal fitness coach** | [`personal-fitness-coach.py`](./personal-fitness-coach.py) | Memory exposed as a **tool** (`list_events`) the agent calls to retrieve recent conversation history; a hand-built `StateGraph` with a chatbot node + `ToolNode`. | Beginner |
| **Support agent (human-in-the-loop)** | [`support-agent-human-in-the-loop.py`](./support-agent-human-in-the-loop.py) | LangGraph's `interrupt` / `Command` to pause for human input and resume; state preserved across the interruption by the checkpointer. | Beginner |

All three use Claude Haiku 4.5 on Amazon Bedrock and require no IAM execution role
(short-term memory uses no long-term extraction strategy).

## Architecture

<div style="text-align:left">
    <img src="images/architecture.png" width="65%" />
</div>

```
  graph.stream/invoke ──▶ LangGraph agent ──▶ model (Bedrock, Claude Haiku 4.5)
          │                     │
          │ config:             │ checkpoint state per (thread_id, actor_id)
          │  thread_id=session  ▼
          │  actor_id=user   ┌─────────────────────────────────────────────┐
          └─────────────────▶│  AgentCore Memory (AgentCoreMemorySaver)     │
                             │   thread_id → session_id, actor_id → actor_id │
                             └─────────────────────────────────────────────┘
```

## Configuration: thread_id and actor_id

For the `AgentCoreMemorySaver` checkpointer, every invocation must set both identifiers in
the runtime config — this is how state is scoped and resumed:

```python
config = {
    "configurable": {
        "thread_id": "session-1",     # maps to AgentCore session_id (the conversation thread)
        "actor_id": "react-agent-1",  # maps to AgentCore actor_id (the user/agent)
    }
}
```

Using a new `thread_id` starts a fresh, isolated conversation; reusing one resumes exactly
where it left off.

> ### LangGraph API note
> These examples use `create_react_agent` from `langgraph.prebuilt` (and, in the fitness
> coach, a hand-built `StateGraph`). In **LangGraph v1.0**, `create_react_agent` is
> **deprecated** in favor of `from langchain.agents import create_agent` with the
> middleware system — it still runs but emits a deprecation warning. The
> `AgentCoreMemorySaver` checkpointer, `thread_id`/`actor_id` config, and `StateGraph` APIs
> shown here are unchanged across versions. For the current `create_agent` + middleware
> style applied to long-term memory, see the
> [LTM LangGraph examples](../../../../02-long-term-memory/examples/single-agent/with-langgraph-agent/).

## Prerequisites

- Python 3.10+
- AWS credentials with **both** AgentCore Memory permissions and Amazon Bedrock
  model-invocation permissions (resolved from the standard AWS chain).
- **Amazon Bedrock model access for Claude Haiku 4.5** in your region (request it in the
  Bedrock console under *Model access*; `us-west-2` is a safe default).

## How to run

```bash
pip install -r requirements.txt

# Optional: override the region (defaults to us-west-2)
export AWS_REGION=us-west-2

python math-agent-with-checkpointing.py
python personal-fitness-coach.py
python support-agent-human-in-the-loop.py
```

> **Note:** `support-agent-human-in-the-loop.py` uses an `InMemorySaver` checkpointer in
> the script body (it handles the full interrupt/resume protocol cleanly for the demo); the
> file documents swapping in `AgentCoreMemorySaver(memory_id, region_name=region)` for
> production. The other two use `AgentCoreMemorySaver` directly.

## Cleanup

Each script creates an AgentCore Memory resource (billable). The scripts end with a
commented-out `client.delete_memory_and_wait(...)` call — uncomment it to delete the
resource after a run, or delete it from the AgentCore console.

## Where to go next

- Long-term memory with LangGraph (built-in callback, custom callback, memory-as-tool):
  [`../../../../02-long-term-memory/examples/single-agent/with-langgraph-agent/`](../../../../02-long-term-memory/examples/single-agent/with-langgraph-agent/)
- The short-term memory concepts (events, sessions, actor isolation, branching):
  [`../../../README.md`](../../../README.md)
