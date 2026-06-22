# Event-Driven Claims Agent — Documentation

The Event-Driven Claims Agent is an insurance claims processor built on Amazon Bedrock AgentCore. It demonstrates a dual-agent architecture where a Claims Processor evaluates submissions, a Validation Agent reviews decisions, and the system routes outcomes to auto-approval or human review based on confidence scoring.

## Where to Start

| Your goal | Start here |
|-----------|-----------|
| Deploy and try it out | [README Quick Start](../README.md#quick-start) |
| Understand how it works | [Architecture](ARCHITECTURE.md) |
| Modify it for your use case | [Tutorial: Make It Your Own](tutorial.md) |
| Look up a specific setting | [Configuration Reference](CONFIGURATION.md) |
| Understand why a choice was made | [Decision Records](decisions/README.md) |
| Deploy step-by-step (manual) | [Deployment Guide](deployment.md) |

## Prerequisites

- AWS Account with Bedrock model access (Claude Sonnet 4)
- AgentCore CLI (`agentcore --version` ≥ 1.0.0-preview.13)
- Node.js 18+ (for CDK)
- Docker or Finch (for container builds)
- Python 3.12+ with uv
- AWS CLI v2 configured

## Documentation Index

| Document | Description |
|----------|-------------|
| [Architecture](ARCHITECTURE.md) | System components, data flows, dual-agent pipeline, and Mermaid diagrams |
| [Tutorial](tutorial.md) | Guided walkthrough: change thresholds, add policies, add tools, adapt the domain |
| [Deployment](deployment.md) | One-command deploy, manual step-by-step, local dev, verification, and teardown |
| [Configuration](CONFIGURATION.md) | Every env var, Cedar policy, Cognito setting, model config, and memory parameter |
| [Decisions](decisions/README.md) | 10 Architectural Decision Records explaining why each choice was made |
