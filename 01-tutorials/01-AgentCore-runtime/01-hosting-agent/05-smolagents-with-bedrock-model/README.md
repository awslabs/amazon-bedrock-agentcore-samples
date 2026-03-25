# Hosting SmoLAgents with Amazon Bedrock models in Amazon Bedrock AgentCore Runtime

## Overview

In this tutorial we will learn how to host your existing agent using Amazon Bedrock AgentCore Runtime with Hugging Face SmoLAgents framework.

SmoLAgents is Hugging Face's lightweight agent framework that provides a simple and efficient way to create AI agents with tool calling capabilities. It's designed to be minimal yet powerful, making it perfect for production deployments.

This example demonstrates SmoLAgents' native Amazon Bedrock integration using the `AmazonBedrockServerModel` class, which provides direct connectivity to Bedrock models without additional dependencies.

### Tutorial Details

| Information         | Details                                                                      |
|:--------------------|:-----------------------------------------------------------------------------|
| Tutorial type       | Conversational                                                               |
| Agent type          | Single                                                                       |
| Agentic Framework   | SmoLAgents (Hugging Face)                                                    |
| LLM model           | Anthropic Claude Sonnet 4                                                    |
| Tutorial components | Hosting agent on AgentCore Runtime. Using SmoLAgents and Amazon Bedrock Model |
| Tutorial vertical   | Cross-vertical                                                               |
| Example complexity  | Easy                                                                         |
| SDK used            | Amazon BedrockAgentCore Python SDK and boto3                                |

### Tutorial Architecture

In this tutorial we will describe how to deploy an existing SmoLAgents agent to AgentCore runtime. 

For demonstration purposes, we will use a SmoLAgents agent using Amazon Bedrock models with custom tools for weather, time, and calculations.

### Tutorial Key Features

* Hosting Agents on Amazon Bedrock AgentCore Runtime
* Using Amazon Bedrock models with native SmoLAgents integration
* Custom tool integration with SmoLAgents
* Lightweight agent framework implementation

## Prerequisites

Before starting, ensure you have:
- Python 3.10+
- AWS credentials configured
- Access to Amazon Bedrock models
- Docker running