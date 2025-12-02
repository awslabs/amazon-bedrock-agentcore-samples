# AgentCore Browser Tool with Playwright and Google ADK on Runtime

## Introduction
This tutorial demonstrates how to build a web research agent using Google ADK framework with AgentCore Browser and deploy it to AWS Bedrock AgentCore Runtime.

## Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                  AgentCore Runtime (Container)              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Google ADK Agent                                     │  │
│  │  ├── LiteLLM → Bedrock Claude Haiku 4.5               │  │
│  │  └── Browser Tool → AgentCore Browser (Playwright)    │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites
- Python 3.10+
- AWS credentials configured (`aws configure`)
- AWS Account with Bedrock model access (Claude Haiku 4.5)
- IAM permissions for AgentCore Browser

## Usage
See the notebook: [01-agentcore-browser-tool-adk-playwright-runtime.ipynb](01-agentcore-browser-tool-adk-playwright-runtime.ipynb)

## Sample Prompts
- `"Hello, what can you do?"`
- `"Browse https://news.ycombinator.com and list the top 3 stories"`

## Clean Up
```bash
agentcore stop-session
agentcore destroy --force
```
