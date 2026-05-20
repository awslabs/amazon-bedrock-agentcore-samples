# AgentCore memory — Long-term memory

Long-term memory turns raw conversation events into structured, reusable records — facts, summaries, preferences, and episodes — organized in namespaces and retrieved by semantic search.

## Folder layout

| Folder | Purpose |
|---|---|
| [`01-core-features/`](./01-core-features/) | Framework-agnostic primitives: strategies (semantic, summary, user preference, episodic), overrides, self-managed, namespaces, retrieval, metadata, batch APIs, redrive, record streaming |
| [`02-single-agent/`](./02-single-agent/) | Framework integrations (Strands, LangGraph, LlamaIndex) across the three patterns |
| [`03-multi-agent/`](./03-multi-agent/) | Multi-agent LTM with shared context |

## The four built-in strategies

| Strategy | Extracts | Typical namespace |
|---|---|---|
| **Semantic** | Standalone facts about the world | `/users/{actorId}/facts/` |
| **Summary** | Rolling conversation summaries | `/sessions/{sessionId}/summary/` |
| **User Preference** | Stable per-user settings | `/users/{actorId}/preferences/` |
| **Episodic** | Meaningful interaction sequences | `/episodes/{actorId}/` |

Plus **Built-in with overrides** (prompt-level tweaks on the above) and **Self-managed** (your own Lambdas for extraction + consolidation).

## Framework × pattern coverage

### Single-agent

| Framework | Built-in hook / callback / memory-block | Custom | memory-as-tool |
|---|---|---|---|
| Strands | `customer-support/customer-support-inbuilt-strategy`, `simple-math-assistant`, `meeting-notes-assistant-using-episodic` | `customer-support/customer-support-override-strategy`, `culinary-assistant-self-managed-strategy`, `culinary-assistant-self-managed-strategy-with-citations` | `culinary-assistant`, `debugging-agent` |
| LangGraph | _gap_ | `custom-user-preferences`, `episodic-memory` (nutrition) | _gap_ |
| LlamaIndex | _gap_ | _gap_ | academic research, investment advisor, legal analyzer, medical knowledge |

### Multi-agent (Strands)

- Built-in hook: `travel-booking-agent`
- Custom hook: `healthcare-assistant-using-episodic`


## Next steps

- Ground the concepts: [`01-core-features/`](./01-core-features/)
- Agent integrations: [`02-single-agent/`](./02-single-agent/), [`03-multi-agent/`](./03-multi-agent/)
- Streaming use cases built on the streaming primitive: [`../03-advanced-patterns/05-streaming-use-cases/`](../03-advanced-patterns/05-streaming-use-cases/)
- Security & isolation: [`../04-security-patterns/`](../04-security-patterns/)

## Running the Python Scripts

Navigate into each sub-folder and run the scripts:

```bash
pip install -r requirements.txt  # if present
```

```bash
# 01-core-features/
python 01-core-features/09-record-streaming.py
```

