# Long-term memory — LlamaIndex single-agent

Three integration patterns matching the LlamaIndex model.

| Pattern | Folder | Notes |
|---|---|---|
| **Built-in memory block** — LlamaIndex's AgentCore memory block on the default chat-engine lifecycle | [`01-built-in-memory-block/`](./01-built-in-memory-block/) | Placeholder — content to be authored |
| **Custom memory block** — subclass the memory block for bespoke extraction/retrieval | [`02-custom-memory-block/`](./02-custom-memory-block/) | Placeholder — content to be authored |
| **memory-as-tool** — memory ops exposed as LlamaIndex tools the LLM invokes | [`03-memory-tool/`](./03-memory-tool/) | Four domain examples: academic research, investment advisor, legal doc analyzer, medical knowledge |

See [`../../01-core-features/`](../../01-core-features/) for the underlying strategies and APIs.

## Running the Python Scripts

Navigate into each sub-folder and run the scripts:

```bash
pip install -r requirements.txt  # if present
```

```bash
# 03-memory-tool/
python 03-memory-tool/academic-research-assistant-long-term-memory-tutorial.py
python 03-memory-tool/investment-portfolio-advisor-long-term-memory-tutorial.py
python 03-memory-tool/medical-knowledge-assistant-long-term-memory-tutorial.py
```

