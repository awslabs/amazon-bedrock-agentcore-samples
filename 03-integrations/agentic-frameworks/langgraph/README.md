# LangGraph Agent with Bedrock AgentCore Integration

| Information         | Details                                                                      |
|---------------------|------------------------------------------------------------------------------|
| Agent type          | Synchronous                                                                 |
| Agentic Framework   | Langgraph                                                                    |
| LLM model           | Anthropic Claude 3 Haiku                                                     |
| Components          | AgentCore Runtime                                |
| Example complexity  | Easy                                                                 |
| SDK used            | Amazon BedrockAgentCore Python SDK                                           |

This example demonstrates how to integrate a LangGraph agent with AWS Bedrock AgentCore, enabling you to deploy a web search-capable agent as a managed service.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
- AWS account with Bedrock access

## Setup Instructions

### 1. Create a Python Environment with uv

```bash
# Install uv if you don't have it already
pip install uv

# Create and activate a virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Requirements

```bash
uv pip install -r requirements.txt
```

### 3. Understanding the Agent Code

The `langgraph_agent_web_search.py` file contains a LangGraph agent with web search capabilities, integrated with Bedrock AgentCore:

```python
from typing import Annotated
from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# Initialize the LLM with Bedrock
llm = init_chat_model(
    "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    model_provider="bedrock_converse",
)

# Define search tool
from langchain_community.tools import DuckDuckGoSearchRun
search = DuckDuckGoSearchRun()
tools = [search]
llm_with_tools = llm.bind_tools(tools)

# Define state
class State(TypedDict):
    messages: Annotated[list, add_messages]

# Build the graph
graph_builder = StateGraph(State)

def chatbot(state: State):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

graph_builder.add_node("chatbot", chatbot)
tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "chatbot")
graph = graph_builder.compile()

# Integrate with Bedrock AgentCore
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload, context):
    tmp_msg = {"messages": [{"role": "user", "content": payload.get("prompt", "No prompt found in input")}]}
    tmp_output = graph.invoke(tmp_msg)
    return {"result": tmp_output['messages'][-1].content}

app.run()
```

### 4. Configure and Launch with Bedrock AgentCore Toolkit

```bash
# Configure your agent for deployment
agentcore configure

# Deploy your agent
agentcore launch -e langgraph_agent_web_search.py
```

During configuration, you'll be prompted to:
- Select your AWS region
- Choose a deployment name
- Configure other deployment settings

### 5. Testing Your Agent

Once deployed, you can test your agent using:

```bash
agentcore invoke {"prompt":"What are the latest developments in quantum computing?"}
```

The agent will:
1. Process your query
2. Use DuckDuckGo to search for relevant information
3. Provide a comprehensive response based on the search results

### 6. Cleanup

To remove your deployed agent:

```bash
agentcore destroy
```

## How It Works

This agent uses LangGraph to create a directed graph for agent reasoning:

1. The user query is sent to the chatbot node
2. The chatbot decides whether to use tools based on the query
3. If tools are needed, the query is sent to the tools node
4. The tools node executes the search and returns results
5. Results are sent back to the chatbot for final response generation

The Bedrock AgentCore framework handles deployment, scaling, and management of the agent in AWS.

## Additional Resources

- [LangGraph Documentation](https://github.com/langchain-ai/langgraph)
- [LangChain Documentation](https://python.langchain.com/docs/get_started/introduction)
- [Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-core.html)
