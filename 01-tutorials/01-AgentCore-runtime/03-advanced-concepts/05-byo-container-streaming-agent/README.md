# Streaming Responses with Strands Agents and Amazon Bedrock models in Amazon Bedrock AgentCore Runtime

## Overview

In this tutorial we will learn how to implement streaming responses using Amazon Bedrock AgentCore Runtime with your existing agents. 

We will focus on a Strands Agents with Amazon Bedrock model example that demonstrates real-time streaming capabilities. 

### Tutorial Details

|Information| Details|
|:--------------------|:---------------------------------------------------------------------------------|
| Tutorial type       | Conversational with Streaming|
| Agent type          | Single         |
| Agentic Framework   | Strands Agents |
| LLM model           | Anthropic Claude Sonnet 4 |
| Tutorial components | Custom Strands Agent Container with Streaming responses and Amazon Bedrock Model |
| Tutorial vertical   | Cross-vertical                                                                   |
| Example complexity  | Intermediate                                                                     |
| SDK used            | Amazon BedrockAgentCore Python SDK and boto3|

### Tutorial Architecture

In this tutorial we will describe how to deploy a streaming agent to AgentCore runtime. 

For demonstration purposes, we will use a custom Strands Agent container using Amazon Bedrock models with streaming capabilities.

In our example we will use a simple agent with two tools in separate python modules: `get_weather` and `get_time`, but with streaming response capabilities.


### Tutorial Key Features

* Custom Agent API Container
* Streaming responses from agents on Amazon Bedrock AgentCore Runtime
* Real-time partial result deliver
* Using Amazon Bedrock models with streaming
* Using Strands Agents and FastAPI with async streaming support