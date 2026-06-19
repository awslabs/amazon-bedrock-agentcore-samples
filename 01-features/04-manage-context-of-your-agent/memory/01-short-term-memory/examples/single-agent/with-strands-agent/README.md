# Short-term memory — Strands single-agent

A personal assistant built with **Strands Agents**, wired to AgentCore short-term memory through lifecycle hooks. The agent loads recent turns on startup (`get_last_k_turns`) and stores each new message as it's added, so a conversation continues seamlessly when the user returns.

| Information | Details |
|---|---|
| Tutorial type | Short-term conversational |
| Agent type | Personal Agent |
| Framework | Strands Agents |
| LLM model | Anthropic Claude Haiku 4.5 |
| Memory components | Short-term memory, `AgentInitializedEvent` + `MessageAddedEvent` hooks, `get_last_k_turns` |
| Complexity | Beginner |

## What it does

- [`personal-agent.py`](./personal-agent.py) — personal assistant with a web-search tool; an `AgentInitializedEvent` hook hydrates history and a `MessageAddedEvent` hook stores each turn via `MemoryClient`.
- [`personal-agent-memory-manager.py`](./personal-agent-memory-manager.py) — the same agent using the newer **`MemoryManager`** / **`MemorySessionManager`** APIs instead of `MemoryClient` (useful as a migration reference).
- [`travel-planning-branching/`](./travel-planning-branching/) — forks conversation history into branches to explore alternative paths.

## Prerequisites

- Python 3.10+
- AWS credentials with AgentCore Memory permissions
- Access to Amazon Bedrock models

## How to run

```bash
pip install -r requirements.txt
python personal-agent.py
```

See the [single-agent index](../README.md) and the [short-term memory section README](../../../README.md) for context.
