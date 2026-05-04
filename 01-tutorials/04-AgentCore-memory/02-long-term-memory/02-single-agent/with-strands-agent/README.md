# Long-term memory — Strands single-agent

Three integration patterns, same memory resource. Pick based on how explicit you want the agent's memory lifecycle to be.

| Pattern | Folder | Examples |
|---|---|---|
| **Built-in hook** — `AgentCoreMemoryHook` handles save/retrieve on the standard lifecycle | [`01-built-in-hook/`](./01-built-in-hook/) | `customer-support/customer-support-inbuilt-strategy.ipynb`, `simple-math-assistant/`, `meeting-notes-assistant-using-episodic/` |
| **Custom hook** — you subclass `HookProvider` for conditional save/retrieve or multi-strategy orchestration | [`02-custom-hook/`](./02-custom-hook/) | `customer-support/customer-support-override-strategy.ipynb`, `culinary-assistant-self-managed-strategy/`, `culinary-assistant-self-managed-strategy-with-citations/` |
| **Memory-as-tool** — memory operations are exposed as Strands tools the LLM calls | [`03-memory-tool/`](./03-memory-tool/) | `culinary-assistant.ipynb`, `debugging-agent/` |

See [`../../01-core-features/`](../../01-core-features/) for the underlying strategies and APIs.
