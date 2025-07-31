# Lab 6: Hosting Strands Agents with Amazon Bedrock models in Amazon Bedrock AgentCore Runtime

## Overview

In this lab we will learn how to host your existing agent, using Amazon Bedrock AgentCore Runtime. We will provide examples using Amazon Bedrock models, although other non-Bedrock models such as Azure OpenAI and Gemini can also be a valid choice.

### Lab Details

| Information        | Details                                                                          |
| :----------------- | :------------------------------------------------------------------------------- |
| Lab type           | Conversational                                                                   |
| Agent type         | Single                                                                           |
| Agentic Framework  | Strands Agents                                                                   |
| LLM model          | Anthropic Claude Sonnet 4                                                        |
| Lab components     | Hosting agent on AgentCore Runtime. Using Strands Agent and Amazon Bedrock Model |
| Lab vertical       | Customer Support                                                                 |
| Example complexity | Easy                                                                             |
| SDK used           | Amazon BedrockAgentCore Python SDK and boto3                                     |
| **Prerequisites**  | **Previously completed Labs 1 through 5**                                        |

### Lab Architecture

In this Lab we will describe how to deploy an existing agent to AgentCore Runtime.

For demonstration purposes, we will use a Strands Agent using Amazon Bedrock models.

In our example we will use a previously defined Agent with some built-in Google calendar tools, AgentCore Identity access management, AgentCore Observability, using AgentCore Memory, and connected through AgentCore Gateway to additional customer-related lambda tools.

### Lab Key Features

- Hosting Agents on Amazon Bedrock AgentCore Runtime
- Using Amazon Bedrock models
- Using Strands Agents

## Prerequisites

To execute this tutorial you will need:

- Python 3.10+
- AWS credentials
- Amazon Bedrock AgentCore SDK
- Strands Agents
- **Previously completed Labs 1 through 5**

**Note**: the modules implemented using other AgentCore Services, covered in previous Labs, are stored in `customer_support_agent` folder, required for our agent to operate in full.
