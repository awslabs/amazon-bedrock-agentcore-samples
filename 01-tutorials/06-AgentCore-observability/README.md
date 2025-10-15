# AgentCore Observability 

This repository demonstrates how to implement AgentCore observability for Agents using Amazon CloudWatch and other providers. It provides examples for both Amazon Bedrock AgentCore Runtime hosted agents and agents hosted non on runtime with popular open-source agent frameworks.



For more details on AgentCore Observability, please refer to [this](https://aws.amazon.com/blogs/machine-learning/build-trustworthy-ai-agents-with-amazon-bedrock-agentcore-observability/) blog post.
## Project Structure

```
06-AgentCore-observability/
├── 01-Agentcore-runtime-hosted/
│   ├── CrewAI/
│   │   ├── images/
│   │   ├── requirements.txt
│   │   └── runtime-with-crewai-and-bedrock-models.ipynb
│   ├── Strands Agents/
│   │   ├── images/
│   │   ├── requirements.txt
│   │   └── runtime_with_strands_and_bedrock_models.ipynb
│   └── README.md
├── 02-Agent-not-hosted-on-runtime/
│   ├── CrewAI/
│   │   ├── .env.example
│   │   ├── CrewAI_Observability.ipynb
│   │   └── requirements.txt
│   ├── Langgraph/
│   │   ├── .env.example
│   │   ├── Langgraph_Observability.ipynb
│   │   └── requirements.txt
│   ├── LlamaIndex/
│   │   ├── images/
│   │   ├── .env.example
│   │   ├── LlamaIndex_Observability.ipynb
│   │   ├── README.md
│   │   └── requirements.txt
│   ├── Strands/
│   │   ├── images/
│   │   ├── .env.example
│   │   ├── requirements.txt
│   │   └── Strands_Observability.ipynb
│   └── README.md
├── 03-advanced-concepts/
│   ├── 01-custom-span-creation/
│   │   ├── .env.example
│   │   ├── Custom_Span_Creation.ipynb
│   │   └── requirements.txt
│   └── README.md
├── 04-Agentcore-runtime-partner-observability/
│   ├── Braintrust/
│   │   ├── requirements.txt
│   │   └── runtime_with_strands_and_braintrust.ipynb
│   ├── Langfuse/
│   │   ├── requirements.txt
│   │   └── runtime_with_strands_and_langfuse.ipynb
│   ├── images/
│   └── README.md
└── README.md
```

## Overview

This repository provides examples and tools to help developers implement observability for GenAI applications. AgentCore Observability helps developers trace, debug, and monitor agent performance in production through unified operational dashboards. With support for OpenTelemetry compatible telemetry and detailed visualizations of each step of the agent workflow, Amazon CloudWatch GenAI Observability enables developers to easily gain visibility into agent behavior and maintain standards at scale.

## Contents

Demonstrates examples using the popular Agent dveelopment fraemworks: 

- **Strands Agents**: Build LLM applications with complex workflows using model-driven agentic development
- **CrewAI**: Create autonomous AI agents that work together in roles to accomplish tasks
- **LangGraph**: Extend LangChain with stateful, multi-actor applications for complex reasoning systems
- **LlamaIndex**: LLM-powered agents over data with workflows


### 1. Bedrock AgentCore Runtime Hosted (01-Agentcore-runtime-hosted)

Examples demonstrating observability for Agents hosted on Amazon Bedrock AgentCore Runtime using Amazon OpenTelemetry Python Instrumentation and Amazon CloudWatch.

### 2. Agent Not Hosted on Runtime (02-Agent-not-hosted-on-runtime)

Examples showcasing observability for popular open-source agent frameworks not hosted on Amazon Bedrock AgentCore Runtime:

### 3. Advanced Concepts (03-advanced-concepts)

Advanced observability patterns and techniques:

- **Custom Span Creation**: Learn how to create custom spans for detailed tracing and monitoring of specific operations within your agent workflows

### 4. Partner Observability (04-Agentcore-runtime-partner-observability)

Examples of using agents hosted on Amazon Bedrock AgentCore Runtime with third-party observability tools:

- **Braintrust**: AI evaluation and monitoring platform
- **Langfuse**: LLM observability and analytics

## Getting Started

1. Navigate to the directory of the framework you want to explore
2. Install the requirements.
3. Configure your AWS credentials
4. Copy the `.env.example` file to `.env` and update the variables
5. Open and run the Jupyter notebook

## Prerequisites

- AWS account with appropriate permissions
- Python 3.10+
- Jupyter notebook environment
- AWS CLI configured with your credentials
- Enable Transaction Search

## Clean Up

Please delete the Log groups and associated resources created on Amazon CloudWatch after completing the examples to avoid unnecessary charges.

## License

This project is licensed under the terms specified in the repository.