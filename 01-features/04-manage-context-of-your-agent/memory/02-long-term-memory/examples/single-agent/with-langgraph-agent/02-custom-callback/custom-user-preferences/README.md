# Long-term memory — LangGraph custom user-preference callback

A nutrition assistant built with **LangGraph** that uses a **custom-override UserPreference strategy** plus agent middlewares to automatically extract, store, and recall user preferences across sessions. Custom prompts steer how preferences are extracted and consolidated.

| Information | Details |
|---|---|
| Tutorial type | Long-term conversational |
| Agent type | Nutrition Assistant |
| Framework | LangGraph (with middlewares) |
| LLM model | Anthropic Claude Haiku 4.5 |
| Strategies | UserPreference — **custom override** (requires IAM execution role) |
| Memory components | Custom extraction/consolidation prompts, `@before_agent`/`@after_agent` middlewares, semantic retrieval |
| Complexity | Intermediate |

## What it does

[`nutrition-assistant-with-user-preference-saving.py`](./nutrition-assistant-with-user-preference-saving.py):

1. Creates memory with a UserPreference custom-override strategy, using the prompts in [`custom_memory_prompts.py`](./custom_memory_prompts.py).
2. A **`@before_agent` middleware** retrieves relevant preferences and injects them into context.
3. An **`@after_agent` middleware** stores new turns for asynchronous extraction.
4. Across sessions, the agent recalls dietary restrictions, favorite foods, and health goals to personalize advice.

## Middleware pattern

This example uses LangGraph's agent middlewares with `create_agent` instead of the deprecated
`create_react_agent` + `pre_model_hook`/`post_model_hook` arguments:

```python
from langchain.agents import create_agent
from langchain.agents.middleware import before_agent, after_agent, AgentState
from langgraph.runtime import Runtime, get_config

@before_agent
def retrieve_from_memory(state: AgentState, runtime: Runtime):
    config = get_config()
    actor_id = config["configurable"]["actor_id"]
    store = runtime.store
    ...

@after_agent
def save_to_memory(state: AgentState, runtime: Runtime):
    ...

graph = create_agent(
    llm,
    store=store,
    tools=[],
    middleware=[retrieve_from_memory, save_to_memory],
)
```

Agent-level middlewares run **once per agent invocation**, whereas model-level hooks run on every LLM
call (which can happen several times in one agent turn when tools are involved). For memory retrieval
and saving, once per agent call is both sufficient and more efficient.

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
