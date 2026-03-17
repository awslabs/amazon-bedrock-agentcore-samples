# 📚 Amazon Bedrock AgentCore Tutorials

This folder contains Hands-on tutorials for building, deploying, and managing AI agents with Amazon Bedrock AgentCore.

AgentCore services work independently or together, with any agentic framework (Strands Agents, LangChain, LangGraph, CrewAI, etc.) and any model.

![Amazon Bedrock AgentCore Overview](images/agentcore_overview.png)

## Prerequisites

- An AWS account with Amazon Bedrock access
- Python 3.10+ and Jupyter Notebook (or JupyterLab)
- AWS CLI configured with appropriate credentials
- Basic familiarity with AI agents and AWS services

## Tutorials

### 01 - [Runtime](01-AgentCore-runtime/) | [Deep Dive Video](https://www.youtube.com/live/wizEw5a4gvM?si=7owv5C-kgU8UTzPl)

Deploy and scale AI agents on a secure, serverless runtime -- regardless of framework, protocol, or model. Covers hosting agents, MCP servers, A2A, and bi-directional streaming.

### 02 - [Gateway](02-AgentCore-gateway/) | [Deep Dive Video](https://www.youtube.com/live/atWXM5lziY8?si=qKEzTbU1-15B8pQ0)

Turn APIs, Lambda functions, and existing services into MCP-compatible tools without managing integrations. Includes examples for auth, access control, sensitive data masking, and more.

### 03 - [Identity](03-AgentCore-identity/) | [Deep Dive Video](https://www.youtube.com/live/wv2doVDF7KQ?si=sxt2lOufwt7cOeUY)

Manage agent identity and access across AWS services and third-party apps (Slack, Zoom) using standard identity providers (Okta, Entra, Cognito). Covers inbound auth, outbound auth, and 3LO flows.

### 04 - [Memory](04-AgentCore-memory/) | [Deep Dive Video](https://www.youtube.com/live/-N4v6-kJgwA)

Add fully managed memory to your agents for personalized experiences. Explore short-term memory, long-term memory, branching, and security patterns.

### 05 - [Tools](05-AgentCore-tools/) | [Deep Dive Video](https://www.youtube.com/live/z3lAJ-Nf_lk?si=Tf45AR3mZVo9rweL)

Use AgentCore's built-in tools: **Code Interpreter** for secure code execution, and **Browser Tool** for web navigation and form completion.

### 06 - [Observability](06-AgentCore-observability/) | [Deep Dive Video](https://www.youtube.com/watch?v=wWQgawUPr1k)

Trace, debug, and monitor agent performance with OpenTelemetry-compatible telemetry. Works for agents hosted on Runtime, self-hosted agents, Lambda-based agents, and EKS-hosted agents.

### 07 - [Evaluations](07-AgentCore-evaluations/) | [Deep Dive Video](https://www.youtube.com/live/i0h7xA8cqYs?si=ZSR_-iQRjju-2H04)

Assess agent quality with built-in and custom evaluators across dimensions like correctness, helpfulness, and safety. Includes creating evaluators, running evaluations, and using results.

### 08 - [Policy](08-AgentCore-policy/) | [Deep Dive Video](https://www.youtube.com/watch?v=q_9htaugcgI)

Define and enforce security controls using Cedar language policies to prevent data leakage and authority overreach. Covers natural language policy authoring and fine-grained access control.

### 09 - [End-to-End Workshop](09-AgentCore-E2E/) | [Deep Dive Video](https://youtu.be/gI_qvheaSoA?si=Pa6VzGXzopuX_koW&t=490)

Build a complete agent step by step, combining Runtime, Gateway, Identity, Memory, and more into a production-ready solution.

## Where to Start

- **New to AgentCore?** Start with [01 - Runtime](01-AgentCore-runtime/) and work through the tutorials in order.
- **Looking for a specific capability?** Jump directly to any tutorial -- each one is self-contained.
- **Want the full picture?** The [End-to-End Workshop](09-AgentCore-E2E/) ties all the components together.

## Resources

- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/) -- Official developer guide and API reference
- [AgentCore Deep Dives Playlist](https://www.youtube.com/live/wzIQDPFQx30?si=K4EgotJ6DDj7Ri41) -- Video playlist covering each component in detail
