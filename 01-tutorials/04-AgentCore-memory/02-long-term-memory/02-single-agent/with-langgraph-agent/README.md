# Long-term memory — LangGraph single-agent

Three integration patterns matching the LangGraph model.

| Pattern | Folder | Notes |
|---|---|---|
| **Built-in callback** — LangGraph's AgentCore memory callback on the default state-graph lifecycle | [`01-built-in-callback/`](./01-built-in-callback/) | Placeholder — content to be authored |
| **Custom callback** — write your own node / checkpointer that calls the Memory API | [`02-custom-callback/`](./02-custom-callback/) | `custom-user-preferences/` (nutrition assistant, user prefs), `episodic-memory/` (nutrition assistant, episodic) |
| **Memory-as-tool** — memory ops exposed as LangGraph tools the LLM invokes | [`03-memory-tool/`](./03-memory-tool/) | Placeholder — content to be authored |

See [`../../01-core-features/`](../../01-core-features/) for the underlying strategies and APIs.
