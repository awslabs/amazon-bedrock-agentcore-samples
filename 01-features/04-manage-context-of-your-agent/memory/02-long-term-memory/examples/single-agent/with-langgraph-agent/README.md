# Long-term memory — LangGraph single-agent

Three integration patterns matching the LangGraph model.

| Pattern | Folder | Notes |
|---|---|---|
| **Built-in callback** — LangGraph's AgentCore memory callback on the default state-graph lifecycle | [`01-built-in-callback/`](./01-built-in-callback/) | Placeholder — content to be authored |
| **Custom callback** — write your own node / checkpointer that calls the memory API | [`02-custom-callback/`](./02-custom-callback/) | `custom-user-preferences/` (nutrition assistant, user prefs), `episodic-memory/` (nutrition assistant, episodic) |
| **memory-as-tool** — memory ops exposed as LangGraph tools the LLM invokes | [`03-memory-tool/`](./03-memory-tool/) | Placeholder — content to be authored |

See the [long-term memory README](../../../README.md) for the underlying strategies and APIs.

## Running the Python Scripts

Install dependencies and run scripts from the relevant sub-folders:

```bash
# Install dependencies (in each sub-folder)
pip install -r requirements.txt

python 02-custom-callback/episodic-memory/custom_memory_prompts.py
python 02-custom-callback/episodic-memory/nutrition-assistant-with-episodic-memory.py
python 02-custom-callback/custom-user-preferences/custom_memory_prompts.py
python 02-custom-callback/custom-user-preferences/nutrition-assistant-with-user-preference-saving.py
```
