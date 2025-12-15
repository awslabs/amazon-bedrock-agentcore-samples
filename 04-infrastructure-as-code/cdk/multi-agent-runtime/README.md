# Multi-Agent AgentCore Runtime - CDK

This CDK stack demonstrates a multi-agent architecture where one agent (orchestrator) can invoke another agent (specialist) to handle complex tasks. This pattern is useful for building sophisticated AI systems with specialized capabilities.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Deployment](#deployment)
- [Testing](#testing)
- [Sample Queries](#sample-queries)
- [Cleanup](#cleanup)
- [Cost Estimate](#cost-estimate)
- [Troubleshooting](#troubleshooting)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

## Overview

This CDK stack creates a two-agent system that demonstrates agent-to-agent communication:

### Agent 1: Orchestrator Agent
- **Role**: Main entry point for user queries
- **Capabilities**:
  - Handles simple queries directly
  - Delegates complex tasks to Agent 2
  - Has a tool to invoke Agent 2's runtime
- **Use Cases**: Routing, task delegation, simple Q&A

### Agent 2: Specialist Agent
- **Role**: Expert agent for detailed analysis
- **Capabilities**:
  - Provides in-depth analytical responses
  - Handles complex reasoning tasks
  - Focuses on accuracy and completeness
- **Use Cases**: Data analysis, expert knowledge, detailed explanations

### Key Features

- **Multi-Agent Communication**: Agent 1 can invoke Agent 2 using `bedrock-agentcore:InvokeAgentRuntime`
- **Automatic Orchestration**: Agent 1 decides when to delegate based on query complexity
- **Independent Deployment**: Each agent has its own ECR repository and runtime
- **Modular Architecture**: Easy to extend with additional specialized agents

## Architecture

![Multi-Agent AgentCore Runtime Architecture](architecture.png)

The architecture consists of:

- **User**: Sends questions to Agent 1 (Orchestrator) and receives responses
- **Agent 1 - Orchestrator Agent**:
  - **AWS CodeBuild**: Builds the ARM64 Docker container image for Agent 1
  - **Amazon ECR Repository**: Stores Agent 1's container image
  - **AgentCore Runtime**: Hosts the Orchestrator Agent
    - Routes simple queries directly
    - Delegates complex queries to Agent 2 using the `call_specialist_agent` tool
    - Invokes Amazon Bedrock LLMs for reasoning
  - **IAM Role**: Permissions to invoke Agent 2's runtime and access Bedrock
- **Agent 2 - Specialist Agent**:
  - **AWS CodeBuild**: Builds the ARM64 Docker container image for Agent 2
  - **Amazon ECR Repository**: Stores Agent 2's container image
  - **AgentCore Runtime**: Hosts the Specialist Agent
    - Provides detailed analysis and expert responses
    - Invokes Amazon Bedrock LLMs for in-depth reasoning
  - **IAM Role**: Standard runtime permissions and Bedrock access
- **Amazon Bedrock LLMs**: Provides AI model capabilities for both agents
- **Agent-to-Agent Communication**: Agent 1 can invoke Agent 2's runtime via `bedrock-agentcore:InvokeAgentRuntime` API

## Prerequisites

### AWS Account Setup

1. **AWS Account**: You need an active AWS account with appropriate permissions
   - [Create AWS Account](https://aws.amazon.com/account/)
   - [AWS Console Access](https://aws.amazon.com/console/)

2. **AWS CLI**: Install and configure AWS CLI with your credentials
   - [Install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
   - [Configure AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)
   
   ```bash
   aws configure
   ```

3. **Python 3.10+** and **AWS CDK v2** installed
   ```bash
   # Install CDK
   npm install -g aws-cdk
   
   # Verify installation
   cdk --version
   ```

4. **CDK version 2.220.0 or later** (for BedrockAgentCore support)

5. **Bedrock Model Access**: Enable access to Amazon Bedrock models in your AWS region
   - Navigate to [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock/)
   - Go to "Model access" and request access to:
     - Anthropic Claude models
   - [Bedrock Model Access Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

6. **Required Permissions**: Your AWS user/role needs permissions for:
   - CloudFormation stack operations
   - ECR repository management
   - IAM role creation
   - Lambda function creation
   - CodeBuild project creation
   - BedrockAgentCore resource creation

## Deployment

### CDK vs CloudFormation

This is the **CDK version** of the multi-agent runtime. If you prefer CloudFormation, see the [CloudFormation version](../../cloudformation/multi-agent-runtime/).

### Option 1: Quick Deploy (Recommended)

```bash
# Install dependencies
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy
cdk deploy
```

### Option 2: Step by Step

```bash
# 1. Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Bootstrap CDK in your account/region (first time only)
cdk bootstrap

# 4. Synthesize the CloudFormation template (optional)
cdk synth

# 5. Deploy the stack
cdk deploy --require-approval never

# 6. Get outputs
cdk list
```

### Deployment Time

- **Expected Duration**: 15-20 minutes
- **Main Steps**:
  - Stack creation: ~2 minutes
  - Docker image builds (CodeBuild): ~10-12 minutes
  - Runtime provisioning: ~3-5 minutes

## Testing

### Test Agent 1 (Orchestrator)

Agent 1 is your main entry point. It will handle simple queries directly or delegate to Agent 2 for complex tasks.

#### Using AWS CLI

```bash
# Get Agent1 Runtime ID
AGENT1_ID=$(aws cloudformation describe-stacks \
  --stack-name MultiAgentDemo \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`Agent1RuntimeId`].OutputValue' \
  --output text)

# Test with a simple query (Agent1 handles directly)
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-id $AGENT1_ID \
  --qualifier DEFAULT \
  --payload '{"prompt": "Hello, how are you?"}' \
  --region us-east-1 \
  response.json

# Test with a complex query (Agent1 delegates to Agent2)
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-id $AGENT1_ID \
  --qualifier DEFAULT \
  --payload '{"prompt": "Provide a detailed analysis of cloud computing benefits"}' \
  --region us-east-1 \
  response.json

cat response.json
```

### Using AWS Console

1. Navigate to [Bedrock AgentCore Console](https://console.aws.amazon.com/bedrock-agentcore/)
2. Go to "Runtimes" in the left navigation
3. Find Agent1 runtime (name starts with `MultiAgentDemo_OrchestratorAgent`)
4. Click on the runtime name
5. Click "Test" button
6. Enter test payload:
   ```json
   {
     "prompt": "Hello, how are you?"
   }
   ```
7. Click "Invoke"

### Test Agent 2 (Specialist) Directly

You can also test Agent 2 directly to see its specialized capabilities.

```bash
# Get Agent2 Runtime ID
AGENT2_ID=$(aws cloudformation describe-stacks \
  --stack-name MultiAgentDemo \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`Agent2RuntimeId`].OutputValue' \
  --output text)

# Invoke Agent2 directly
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-id $AGENT2_ID \
  --qualifier DEFAULT \
  --payload '{"prompt": "Explain quantum computing in detail"}' \
  --region us-east-1 \
  response.json
```

## Sample Queries

### Queries that Agent 1 Handles Directly

These simple queries don't require specialist knowledge:

1. **Greetings**:
   ```json
   {"prompt": "Hello, how are you?"}
   ```

2. **Simple Math**:
   ```json
   {"prompt": "What is 5 + 3?"}
   ```

### Queries that Trigger Agent 2 Delegation

These complex queries require expert analysis:

1. **Detailed Analysis**:
   ```json
   {"prompt": "Provide a detailed analysis of the benefits and drawbacks of serverless architecture"}
   ```

2. **Expert Knowledge**:
   ```json
   {"prompt": "Explain the CAP theorem and its implications for distributed systems"}
   ```

3. **Complex Reasoning**:
   ```json
   {"prompt": "Compare and contrast different machine learning algorithms for time series forecasting"}
   ```

4. **In-depth Explanation**:
   ```json
   {"prompt": "Provide expert analysis on best practices for securing cloud infrastructure"}
   ```

## Cleanup

### Using CDK (Recommended)

```bash
cdk destroy
```

### Using AWS CLI

```bash
aws cloudformation delete-stack \
  --stack-name MultiAgentDemo \
  --region us-east-1

# Wait for deletion to complete
aws cloudformation wait stack-delete-complete \
  --stack-name MultiAgentDemo \
  --region us-east-1
```

### Using AWS Console

1. Navigate to [CloudFormation Console](https://console.aws.amazon.com/cloudformation/)
2. Select the `MultiAgentDemo` stack
3. Click "Delete"
4. Confirm deletion

## Cost Estimate

### Monthly Cost Breakdown (us-east-1)

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| **AgentCore Runtimes** | 2 runtimes, minimal usage | ~$10-20 |
| **ECR Repositories** | 2 repositories, <2GB storage | ~$0.20 |
| **CodeBuild** | Occasional builds | ~$2-4 |
| **Lambda** | Custom resource executions | ~$0.01 |
| **CloudWatch Logs** | Agent logs | ~$1.00 |
| **Bedrock Model Usage** | Pay per token | Variable* |

**Estimated Total: ~$13-25/month** (excluding Bedrock model usage)

*Bedrock costs depend on your usage patterns and chosen models. See [Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/) for details.

### Cost Optimization Tips

- **Delete when not in use**: Use `cdk destroy` to remove all resources
- **Monitor usage**: Set up CloudWatch billing alarms
- **Choose efficient models**: Select appropriate Bedrock models for your use case

## Troubleshooting

### CDK Bootstrap Required

If you see bootstrap errors:
```bash
cdk bootstrap aws://ACCOUNT-NUMBER/REGION
```

### Permission Issues

Ensure your IAM user/role has:
- `CDKToolkit` permissions or equivalent
- Permissions to create all resources in the stack
- `iam:PassRole` for service roles

### Python Dependencies

Install dependencies in the project directory:
```bash
pip install -r requirements.txt
```

### Build Failures

Check CodeBuild logs in the AWS Console:
1. Go to CodeBuild console
2. Find the build projects (names contain "agent1-build" and "agent2-build")
3. Check build history and logs

### Agent Communication Issues

If Agent 1 can't invoke Agent 2:
1. Check IAM permissions for `bedrock-agentcore:InvokeAgentRuntime`
2. Verify Agent 2 runtime is running
3. Check CloudWatch logs for both agents

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](../../CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.
