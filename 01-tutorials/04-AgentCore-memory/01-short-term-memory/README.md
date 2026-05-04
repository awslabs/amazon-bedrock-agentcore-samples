# AgentCore Memory — Short-term memory

Short-term memory stores raw conversation turns (events) scoped to an actor and session, plus branching for exploratory or parallel flows. It provides immediate, low-latency context for a conversation without background processing.

## Folder layout

| Folder | Purpose |
|---|---|
| [`01-core-features/`](./01-core-features/) | Framework-agnostic primitives: events, metadata filtering, actor/session isolation, event branching |
| [`02-single-agent/`](./02-single-agent/) | Framework integrations (Strands, LangGraph, LlamaIndex) with the three patterns: built-in hook, custom hook, memory-as-tool |
| [`03-multi-agent/`](./03-multi-agent/) | Multi-agent STM with shared context, including parallel branching |

## The three integration patterns (per framework)

| Pattern | What it is | When to use |
|---|---|---|
| **Built-in hook** | Use the framework's out-of-the-box AgentCore memory hook | Fastest path; standard save/retrieve lifecycle |
| **Custom hook** | Subclass/implement your own hook | Conditional logic, custom retrieval, orchestration |
| **Memory-as-tool** | Expose memory operations as tools the agent calls | Agent decides when to recall/save |

## Framework × pattern notebooks

### Single-agent

| Framework | Built-in hook | Custom hook | Memory-as-tool |
|---|---|---|---|
| Strands | [`personal-agent.ipynb`](./02-single-agent/with-strands-agent/personal-agent.ipynb) | [`personal-agent-memory-manager.ipynb`](./02-single-agent/with-strands-agent/personal-agent-memory-manager.ipynb) | _gap_ |
| LangGraph | [`math-agent-with-checkpointing.ipynb`](./02-single-agent/with-langgraph-agent/math-agent-with-checkpointing.ipynb) | [`personal-fitness-coach.ipynb`](./02-single-agent/with-langgraph-agent/personal-fitness-coach.ipynb) | [`support-agent-human-in-the-loop.ipynb`](./02-single-agent/with-langgraph-agent/support-agent-human-in-the-loop.ipynb) |
| LlamaIndex | _gap_ | _gap_ | four domain examples in [`with-llamaindex-agent/`](./02-single-agent/with-llamaindex-agent/) |

**Branching** (Strands): [`travel-planning-branching/`](./02-single-agent/with-strands-agent/travel-planning-branching/)

### Multi-agent (Strands)

- Built-in hook: [`travel-planning-agent.ipynb`](./03-multi-agent/with-strands-agent/travel-planning-agent.ipynb)
- Custom hook: [`travel-planning-agent-memory-manager.ipynb`](./03-multi-agent/with-strands-agent/travel-planning-agent-memory-manager.ipynb)
- Parallel branching: [`multi-agent-parallel-branches/`](./03-multi-agent/with-strands-agent/multi-agent-parallel-branches/)

> Framework × pattern classifications above reflect the current intent; the corresponding notebooks keep their original filenames in this pass. See [`../journal.md`](../journal.md) for the restructure plan and known gaps.

## Next steps

- Learn the primitives: [`01-core-features/`](./01-core-features/)
- Cross-session persistence: [`../02-long-term-memory/`](../02-long-term-memory/)
- Security and isolation: [`../04-security-patterns/`](../04-security-patterns/)
