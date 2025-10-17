# Basic AgentCore Runtime

This CloudFormation template deploys a basic Amazon Bedrock AgentCore Runtime with a simple Strands agent. This is the simplest possible AgentCore deployment, perfect for getting started and understanding the core concepts without additional complexity.

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

This template creates a minimal AgentCore deployment that includes:

- **AgentCore Runtime**: Hosts a simple Strands agent
- **ECR Repository**: Stores the Docker container image
- **IAM Roles**: Provides necessary permissions
- **CodeBuild Project**: Automatically builds the ARM64 Docker image
- **Lambda Functions**: Custom resources for automation


This makes it ideal for:
- Learning AgentCore basics
- Quick prototyping
- Understanding the core deployment pattern
- Building a foundation before adding complexity

## Architecture

![Basic AgentCore Runtime Architecture](architecture.png)

The architecture consists of:

- **User**: Sends questions to the agent and receives responses
- **AWS CodeBuild**: Builds the ARM64 Docker container image with the agent code
- **Amazon ECR Repository**: Stores the container image
- **AgentCore Runtime**: Hosts the Basic Agent container
  - **Basic Agent**: Simple Strands agent that processes user queries
  - Invokes Amazon Bedrock LLMs to generate responses
- **IAM Roles**: 
  - IAM role for CodeBuild (builds and pushes images)
  - IAM role for Agent Execution (runtime permissions)
- **Amazon Bedrock LLMs**: Provides the AI model capabilities for the agent

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

3. **Bedrock Model Access**: Enable access to Amazon Bedrock models in your AWS region
   - Navigate to [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock/)
   - Go to "Model access" and request access to:
     - Anthropic Claude models (recommended: Claude 3.5 Sonnet or Claude 3 Haiku)
   - [Bedrock Model Access Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

4. **Required Permissions**: Your AWS user/role needs permissions for:
   - CloudFormation stack operations
   - ECR repository management
   - IAM role creation
   - Lambda function creation
   - CodeBuild project creation
   - BedrockAgentCore resource creation

## Deployment

### Option 1: Using the Deploy Script (Recommended)

```bash
# Make the script executable
chmod +x deploy.sh

# Deploy the stack
./deploy.sh
```

The script will:
1. Deploy the CloudFormation stack
2. Wait for stack creation to complete
3. Display the AgentCore Runtime ID

### Option 2: Using AWS CLI

```bash
# Deploy the stack
aws cloudformation create-stack \
  --stack-name basic-agent-demo \
  --template-body file://template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2

# Wait for stack creation
aws cloudformation wait stack-create-complete \
  --stack-name basic-agent-demo \
  --region us-west-2

# Get the Runtime ID
aws cloudformation describe-stacks \
  --stack-name basic-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentRuntimeId`].OutputValue' \
  --output text
```

### Option 3: Using AWS Console

1. Navigate to [CloudFormation Console](https://console.aws.amazon.com/cloudformation/)
2. Click "Create stack" → "With new resources"
3. Upload the `template.yaml` file
4. Enter stack name: `basic-agent-demo`
5. Review parameters (or use defaults)
6. Check "I acknowledge that AWS CloudFormation might create IAM resources"
7. Click "Create stack"

### Deployment Time

- **Expected Duration**: 10-15 minutes
- **Main Steps**:
  - Stack creation: ~2 minutes
  - Docker image build (CodeBuild): ~8-10 minutes
  - Runtime provisioning: ~2-3 minutes

## Testing

### Using AWS CLI

```bash
# Get the Runtime ID from stack outputs
RUNTIME_ID=$(aws cloudformation describe-stacks \
  --stack-name basic-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentRuntimeId`].OutputValue' \
  --output text)

# Invoke the agent
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-id $RUNTIME_ID \
  --qualifier DEFAULT \
  --payload '{"prompt": "What is 2+2?"}' \
  --region us-west-2 \
  response.json

# View the response
cat response.json
```

### Using AWS Console

1. Navigate to [Bedrock AgentCore Console](https://console.aws.amazon.com/bedrock-agentcore/)
2. Go to "Runtimes" in the left navigation
3. Find your runtime (name starts with `basic_agent_demo_`)
4. Click on the runtime name
5. Click "Test" button
6. Enter test payload:
   ```json
   {
     "prompt": "What is 2+2?"
   }
   ```
7. Click "Invoke"



## Sample Queries

Try these queries to test your basic agent:

1. **Simple Math**:
   ```json
   {"prompt": "What is 2+2?"}
   ```

2. **General Knowledge**:
   ```json
   {"prompt": "What is the capital of France?"}
   ```

3. **Explanation Request**:
   ```json
   {"prompt": "Explain what Amazon Bedrock is in simple terms"}
   ```

4. **Creative Task**:
   ```json
   {"prompt": "Write a haiku about cloud computing"}
   ```

5. **Reasoning**:
   ```json
   {"prompt": "If I have 5 apples and give away 2, how many do I have left?"}
   ```

## Cleanup

### Using the Cleanup Script (Recommended)

```bash
# Make the script executable
chmod +x cleanup.sh

# Delete the stack
./cleanup.sh
```

### Using AWS CLI

```bash
aws cloudformation delete-stack \
  --stack-name basic-agent-demo \
  --region us-west-2

# Wait for deletion to complete
aws cloudformation wait stack-delete-complete \
  --stack-name basic-agent-demo \
  --region us-west-2
```

### Using AWS Console

1. Navigate to [CloudFormation Console](https://console.aws.amazon.com/cloudformation/)
2. Select the `basic-agent-demo` stack
3. Click "Delete"
4. Confirm deletion
