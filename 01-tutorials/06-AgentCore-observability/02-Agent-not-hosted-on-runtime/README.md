# AgentCore Observability for Open Source Agents not on AgentCore Runtime

This repository contains examples to showcase AgentCore Observability for popular AI Open Source frameworks **not** hosted on Amazon Bedrock AgentCore Runtime using Amazon OpenTelemetry Python Instrumentation and Amazon CloudWatch. Observability helps developers trace, debug, and monitor agent performance in production through unified operational dashboards. With support for OpenTelemetry compatible telemetry and detailed visualizations of each step of the agent workflow, Amazon CloudWatch GenAI Observability enables developers to easily gain visibility into agent behavior and maintain quality standards at scale.

We will create an agent with the following opensource agent frameworks: 

- **CrewAI**
- **LangGraph**
- **Strands Agents**

## Project Structure

```
02-open-source-agents-3p/
├── CrewAI/
│   ├── .env.example
│   ├── CrewAI_Observability.ipynb
│   └── requirements.txt
├── Langgraph/
│   ├── .env.example
│   ├── Langgraph_Observability.ipynb
│   └── requirements.txt
└── Strands/
    ├── .env.example
    ├── requirements.txt
    └── Strands_Observability.ipynb
```

## Getting Started

Each framework has its own directory with:
- A Jupyter notebook demonstrating the framework's capabilities
- A requirements.txt file listing necessary dependencies
- An .env.example file showing required environment variables

## Usage

1. Navigate to the directory of the framework you want to explore
2. Install the requirements: `pip install -r requirements.txt`
3. Configure your AWS credentials 
3. Copy the .env.example file to .env and update the variables
4. Open and run the Jupyter notebook

## Frameworks Overview

### CrewAI
[CrewAI](https://www.crewai.com/) enables the creation of autonomous AI agents that can work together in roles to accomplish tasks.

### LangGraph
[LangGraph](https://www.langchain.com/langgraph) extends LangChain with stateful, multi-actor applications. It's particularly useful for creating complex reasoning systems with LLMs.

### Strands Agents
[ Strands](https://strandsagents.com/latest/) provides a framework for building LLM applications with complex workflows, focusing on model driven agentic developement.

## Clean Up 

Please delete the Log groups and associated resources created on Amazon CloudWatch.