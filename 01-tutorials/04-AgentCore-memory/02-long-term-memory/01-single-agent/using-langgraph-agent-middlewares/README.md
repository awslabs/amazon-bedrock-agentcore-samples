# LangGraph v1.0 Agent with Memory Middlewares

This tutorial demonstrates how to integrate Amazon Bedrock AgentCore Memory with a LangGraph v1.0 agent using the **new middleware pattern**.

## What's New in LangGraph v1.0

| Old (Deprecated) | New (v1.0) |
|------------------|------------|
| `from langgraph.prebuilt import create_react_agent` | `from langchain.agents import create_agent` |
| `pre_model_hook=..., post_model_hook=...` | `middleware=[...]` |
| Functions as parameters | Decorators: `@before_model`, `@after_model` |

## Key Features

- **`@before_model` middleware**: Retrieves relevant user preferences from AgentCore Memory before LLM invocation
- **`@after_model` middleware**: Saves conversation to AgentCore Memory for long-term extraction
- **Built-in Memory Strategies**: Uses `USER_PREFERENCE` and `SEMANTIC` strategies (no IAM role required)
- **MemoryManager**: Simplified memory creation from the starter toolkit

## Memory Strategies

This example uses two built-in strategies:

1. **USER_PREFERENCE**: Automatically extracts user preferences from conversations
2. **SEMANTIC**: Stores factual information mentioned in conversations

```python
memory = memory_manager.get_or_create_memory(
    name="NutritionAssistant",
    strategies=[
        {StrategyType.USER_PREFERENCE.value: {...}},
        {StrategyType.SEMANTIC.value: {...}}
    ]
)
```

## Middleware Pattern

```python
from langchain.agents.middleware import before_model, after_model, AgentState
from langgraph.runtime import Runtime

@before_model
def retrieve_from_memory(state: AgentState, runtime: Runtime):
    # Retrieve memories and inject into context
    ...

@after_model
def save_to_memory(state: AgentState, runtime: Runtime):
    # Save conversation to AgentCore Memory
    ...

# Create agent with middlewares
graph = create_agent(
    llm,
    tools=[],
    middleware=[retrieve_from_memory, save_to_memory],
    checkpointer=InMemorySaver(),
)
```

## Prerequisites

- Python 3.10+
- AWS account with appropriate permissions
- Access to Amazon Bedrock models

## Installation

```bash
pip install -r requirements.txt
```

## Files

| File | Description |
|------|-------------|
| `nutrition-assistant-with-middlewares.ipynb` | Main tutorial notebook |
| `requirements.txt` | Python dependencies |

## Related Examples

- [`using-langgraph-agent-hooks`](../using-langgraph-agent-hooks/) - Deprecated approach using `pre_model_hook`/`post_model_hook`

