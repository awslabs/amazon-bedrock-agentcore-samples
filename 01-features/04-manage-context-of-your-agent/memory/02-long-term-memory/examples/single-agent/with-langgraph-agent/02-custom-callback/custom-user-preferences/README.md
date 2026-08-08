# Long-term memory — LangGraph agent with AgentCore Memory middlewares

A nutrition assistant built with **LangGraph** that uses **agent middlewares** to automatically extract,
store, and recall user preferences across conversation sessions.

| Information | Details |
|---|---|
| Tutorial type | Long-term conversational |
| Agent type | Nutrition Assistant |
| Framework | LangGraph (with middlewares) |
| LLM model | Anthropic Claude Haiku 4.5 |
| Strategies | UserPreference + Semantic (built-in, **no IAM execution role required**) |
| Memory components | `@before_agent`/`@after_agent` middlewares, semantic retrieval, `MemoryManager` |
| Complexity | Intermediate |

## Architecture

![Architecture](architecture.png)

## Key features

- **`@before_agent` middleware**: retrieves relevant user preferences from AgentCore Memory once per agent call
- **`@after_agent` middleware**: saves the conversation to AgentCore Memory for long-term extraction
- **Built-in memory strategies**: uses `USER_PREFERENCE` and `SEMANTIC` (no IAM role required)
- **MemoryManager**: simplified memory creation from the starter toolkit

## What it does

[`nutrition-assistant-with-user-preference-saving.py`](./nutrition-assistant-with-user-preference-saving.py):

1. Creates memory with built-in `USER_PREFERENCE` and `SEMANTIC` strategies via `MemoryManager`.
2. A **`@before_agent` middleware** retrieves relevant preferences and facts, then injects them into the system prompt.
3. An **`@after_agent` middleware** stores each new turn for asynchronous extraction.
4. Across sessions, the agent recalls dietary restrictions, favorite foods, and health goals to personalize advice.

## Memory strategies

This example uses two built-in strategies:

1. **USER_PREFERENCE** — automatically extracts user preferences from conversations
2. **SEMANTIC** — stores factual information mentioned in conversations

```python
memory = memory_manager.get_or_create_memory(
    name="Nutrition_Assistant",
    strategies=[
        {StrategyType.USER_PREFERENCE.value: {...}},
        {StrategyType.SEMANTIC.value: {...}},
    ],
)
```

Namespaces:

- `nutrition/{actorId}/preferences` — user food preferences
- `nutrition/{actorId}/facts` — factual information

> **Tip**: for custom extraction/consolidation prompts, use `StrategyType.CUSTOM` with `MemoryClient`
> (which does require a `memory_execution_role_arn`).

## Middleware pattern

This example uses LangGraph's agent middlewares with `create_agent`, replacing the deprecated
`create_react_agent` + `pre_model_hook`/`post_model_hook` arguments:

```python
from langchain.agents import create_agent
from langchain.agents.middleware import before_agent, after_agent, AgentState
from langgraph.runtime import Runtime

@before_agent
def retrieve_from_memory(state: AgentState, runtime: Runtime):
    # Retrieve memories and inject into context
    ...

@after_agent
def save_to_memory(state: AgentState, runtime: Runtime):
    # Save conversation to AgentCore Memory
    ...

graph = create_agent(
    llm,
    tools=[],
    middleware=[retrieve_from_memory, save_to_memory],
    checkpointer=InMemorySaver(),
)
```

Agent-level middlewares run **once per agent invocation**, whereas model-level hooks run on every LLM
call (which can happen several times in one agent turn when tools are involved). For memory retrieval
and saving, once per agent call is both sufficient and more efficient.

## Prerequisites

- Python 3.10+
- AWS account with AgentCore Memory permissions
- Access to Amazon Bedrock models

## How to run

```bash
pip install -r requirements.txt
python nutrition-assistant-with-user-preference-saving.py
```

See the sibling [`episodic-memory/`](../episodic-memory/) for the episodic variant, or the [LangGraph single-agent README](../../README.md) for all three patterns.
