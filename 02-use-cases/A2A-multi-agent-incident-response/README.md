# Agent-to-Agent (A2A) Multi-Agent System on Amazon Bedrock AgentCore for Incident Response Logging

A comprehensive implementation of the Agent-to-Agent (A2A) protocol using specialized agents running on Amazon Bedrock `AgentCore` runtime, demonstrating intelligent coordination for AWS infrastructure monitoring and operations management. This repository walks you through setting up three core agents to answer questions about incidents and metrics in your AWS accounts and search for best remediation strategies. A monitoring agent (built using the `Strands` Agents SDK) is responsible for handling all questions related to metrics and logs within AWS and cross AWS accounts. A remediation agent (built using `OpenAI`'s Agents SDK) is responsible to doing efficient web searches for best remediation strategies and optimization techniques that the user can ask for. Both agents run on separate runtimes as `A2A` servers and utilize all `AgentCore` primitives - memory for context management, observability for deep level analysis about both agents, gateway for access to tools (`Cloudwatch`, `JIRA` and `TAVILY` APIs) and `AgentCore` identity for enabling inbound and outbound access into the agent and then into the resources that the agent can access using OAuth 2.0 and APIs. These two agents are then managed by a host `Google ADK` agent that acts as a client and delegates tasks to each of these agents using A2A on Runtime. The Google ADK host agent runs on a separate `AgentCore` runtime of its own.

## What is A2A?

**Agent-to-Agent (A2A)** is an open standard protocol that enables seamless communication and collaboration between AI agents across different platforms and implementations. The A2A protocol defines:

- **Agent Discovery**: Standardized agent cards that describe capabilities, skills, and communication endpoints
- **Communication Format**: JSON-RPC 2.0-based message format for reliable agent-to-agent communication
- **Authentication**: OAuth 2.0-based security model for secure inter-agent communication
- **Interoperability**: Platform-agnostic design allowing agents from different frameworks to collaborate

Learn more about the A2A protocol: [A2A Specification](https://a2a.foundation/)

## A2A Support on Amazon Bedrock AgentCore

Amazon Bedrock AgentCore provides native support for the A2A protocol, enabling you to:

- **Deploy A2A-compliant agents** as runtime services with automatic endpoint management
- **Secure authentication** via AWS Cognito OAuth 2.0 integration
- **Agent discovery** through standardized agent card endpoints
- **Scalable deployment** leveraging AWS infrastructure for production workloads
- **Built-in observability** with CloudWatch integration and OpenTelemetry support

AgentCore simplifies A2A agent deployment by handling infrastructure, authentication, scaling, and monitoring automatically.

## System Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        Host Orchestrator Agent                     │
│                    (Google ADK + A2A Protocol)                     │
│  • Fetches IDP configuration from SSM Parameter Store              │
│  • Discovers remote agents via agent cards                         │
│  • Routes requests to appropriate specialist agents                │
│  • Coordinates multi-agent collaboration                           │
└────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴──────────────┐
                    │    A2A Protocol (OAuth)    │
                    │   JSON-RPC 2.0 Messages    │
                    └─────────────┬──────────────┘
                                  │
          ┌───────────────────────┴────────────────────────┐
          │                                                 │
┌─────────▼──────────────┐                   ┌────────────▼────────────┐
│  Monitoring Agent      │                   │  Ops Orchestrator Agent │
│  (Bedrock AgentCore)   │                   │  (Bedrock AgentCore)    │
│                        │                   │                         │
│  • CloudWatch logs     │                   │  • Web search for best  │
│  • Metrics analysis    │                   │    practices            │
│  • Dashboard review    │                   │  • JIRA ticket creation │
│  • Alarm management    │                   │  • Remediation guidance │
│  • A2A Server (port    │                   │  • A2A Server (port     │
│    9000)               │                   │    9000)                │
└────────────────────────┘                   └─────────────────────────┘
```

## Architecture Overview

```bash
TODO: Architecture video
```

## Demo

```bash
TODO: Demo video
```

## Prerequisites

1. **AWS Account**: You need an active AWS account with appropriate permissions
   - [Create AWS Account](https://aws.amazon.com/account/)
   - [AWS Console Access](https://aws.amazon.com/console/)

2. **AWS CLI**: Install and configure AWS CLI with your credentials
   - [Install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
   - [Configure AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)

   ```bash
   aws configure
   ```

3. **Bedrock Model Access**: Enable access to Amazon Bedrock Anthropic Claude 4.0 models in your AWS region
   - Navigate to [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock/)
   - Go to "Model access" and request access to:
     - Anthropic Claude 4.0 Sonnet model
     - Anthropic Claude 3.5 Haiku model
   - [Amazon Bedrock Model Access Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

4. Install uv using [guide](https://docs.astral.sh/uv/getting-started/installation/).

5. **Supported Regions**: This solution is currently tested and supported in the following AWS regions:

   | Region Code   | Region Name          | Status      |
   |---------------|----------------------|-------------|
   | `us-west-2`   | US West (Oregon)     | ✅ Supported |

   > **Note**: To deploy in other regions, you'll need to update the DynamoDB prefix list mappings in `cloudformation/vpc-stack.yaml`. See the [VPC Stack documentation](cloudformation/vpc-stack.yaml) for details.

## Deployment Steps

### Step 1: Deploy AWS Cognito Stack

```bash
aws cloudformation create-stack \
    --stack-name cognito-stack-a2a \
    --template-body file://cloudformation/cognito.yaml \
    --capabilities CAPABILITY_IAM \
    --region us-west-2
```

### Step 2: Deploy Monitoring Strands Agent

```bash
aws cloudformation create-stack \
    --stack-name monitor-agent-a2a \
    --template-body file://cloudformation/monitoring_agent.yaml \
    --capabilities CAPABILITY_IAM \
    --region us-west-2
```

