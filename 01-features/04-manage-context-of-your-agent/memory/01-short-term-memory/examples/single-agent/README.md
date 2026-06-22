# Short-term memory — single-agent examples

One agent per example, each wiring AgentCore short-term memory into a different framework. The same pattern recurs: retrieve recent turns on startup, store each turn as it happens.

| Framework | Folder | What it demonstrates |
|---|---|---|
| Anthropic Claude SDK (no framework) | [`with-claude-sdk/`](./with-claude-sdk/) | Explicit `messages[]` management — the clearest view of what short-term memory does |
| Strands Agents | [`with-strands-agent/`](./with-strands-agent/) | Personal agent via lifecycle hooks; `travel-planning-branching/` forks the conversation |
| LangGraph | [`with-langgraph-agent/`](./with-langgraph-agent/) | Built-in checkpointing, custom hooks, and human-in-the-loop |
| LlamaIndex | [`with-llamaindex-agent/`](./with-llamaindex-agent/) | `AgentCoreMemory` context in a `FunctionAgent` across four domains |

## Where to go next

- Multi-agent short-term examples: [`../multi-agent/`](../multi-agent/)
- Short-term memory primitives: [`../../README.md`](../../README.md)
