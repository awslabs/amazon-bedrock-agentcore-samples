# AgentCore Observability on Amazon CloudWatch for Bedrock AgentCore Runtime Agents 

This repository contains examples to showcase AgentCore Observability for Strands Agent  hosted on Amazon Bedrock AgentCore Runtime using Amazon OpenTelemetry Python Instrumentation and Amazon CloudWatch. Observability helps developers trace, debug, and monitor agent performance in production through unified operational dashboards. With support for OpenTelemetry compatible telemetry and detailed visualizations of each step of the agent workflow, Amazon CloudWatch GenAI Observability enables developers to easily gain visibility into agent behavior and maintain quality standards at scale.


## Getting Started

The Project folder has the following:
- A Jupyter notebook demonstrating the Agentcore runtime and observability on Cloudwatch.
- A requirements.txt file listing necessary dependencies
- An .env.example file showing required environment variables


## Usage

1. Navigate to the directory of the framework you want to explore
2. Install the requirements: `!pip install -r requirements.txt `
3. Configure your AWS credentials 
3. Copy the .env.example file to .env and update the variables
4. Open and run the Jupyter notebook


### Strands Agents
[Strands](https://strandsagents.com/latest/) provides a framework for building LLM applications with complex workflows, focusing on model-driven agentic development.

## Cleanup

After completing the examples:

1. Remove AgentCore Runtime deployments
2. Clean up any created ECR repositories
