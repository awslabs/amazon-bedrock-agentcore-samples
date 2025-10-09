# Third-Party Observability for Amazon Bedrock AgentCore Agents

This repository contains examples of using agents hosted on Amazon Bedrock AgentCore Runtime with third-party observability tools like Braintrust, Langfuse, and others. These examples demonstrate OpenTelemetry integration for monitoring agent performance, tracing LLM interactions, and debugging workflows.


## Getting Started

The publish folder contains:
- A Jupyter notebook demonstrating AgentCore runtime with various observability solutions
- A requirements.txt file listing necessary dependencies

## Usage

1. Install the requirements: `pip install -r requirements.txt`
2. Configure your AWS credentials
3. Set up your observability platform account and obtain API keys
4. Update environment variables in the notebook with your credentials
5. Open and run the Jupyter notebook

## Frameworks
While the examples demonstrate using Strands Agent SDK, Amazon bedrock AgentCore enables developers to use any agentic framework and any model of their choice.

### Strands Agents
[Strands](https://strandsagents.com/latest/) provides a framework for building LLM applications with complex workflows, with built-in telemetry support.

## Clean Up
Remember to delete the AgentCore Runtime and ECR repository using the cleanup section in the notebook to avoid ongoing charges.