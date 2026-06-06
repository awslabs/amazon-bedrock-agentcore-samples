# Long-term memory — LangGraph custom user-preference callback

A nutrition assistant built with **LangGraph** that uses a **custom-override UserPreference strategy** plus pre/post model hooks to automatically extract, store, and recall user preferences across sessions. Custom prompts steer how preferences are extracted and consolidated.

| Information | Details |
|---|---|
| Tutorial type | Long-term conversational |
| Agent type | Nutrition Assistant |
| Framework | LangGraph |
| LLM model | Anthropic Claude Haiku 4.5 |
| Strategies | UserPreference — **custom override** (requires IAM execution role) |
| Memory components | Custom extraction/consolidation prompts, pre/post model hooks, semantic retrieval |
| Complexity | Intermediate |

## What it does

[`nutrition-assistant-with-user-preference-saving.py`](./nutrition-assistant-with-user-preference-saving.py):

1. Creates memory with a UserPreference custom-override strategy, using the prompts in [`custom_memory_prompts.py`](./custom_memory_prompts.py).
2. A **pre-model hook** retrieves relevant preferences and injects them into context.
3. A **post-model hook** stores new turns for asynchronous extraction.
4. Across sessions, the agent recalls dietary restrictions, favorite foods, and health goals to personalize advice.

## Prerequisites

- Python 3.10+
- AWS account with AgentCore Memory permissions and an IAM execution role
- Access to Amazon Bedrock models

## How to run

```bash
pip install -r requirements.txt
python nutrition-assistant-with-user-preference-saving.py
```

See the sibling [`episodic-memory/`](../episodic-memory/) for the episodic variant, or the [LangGraph single-agent README](../../README.md) for all three patterns.
