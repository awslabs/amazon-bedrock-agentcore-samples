# Typescript Mastra AI example for Amazon Bedrock AgentCore Runtime

This project implements the HTTP protocol contract for Amazon Bedrock AgentCore Runtime using [Express.js](https://expressjs.com/). It provides a foundation for integrating [Typescript Mastra AI](https://mastra.ai/) with Amazon Bedrock AgentCore Runtime.

| Information         | Details                                                                      |
|---------------------|------------------------------------------------------------------------------|
| Agent type          | Streaming                                                                    |
| Agentic Framework   | Mastra AI (TypeScript)                                                       |
| LLM model           | OpenAI GPT-4o-mini                                                           |
| Components          | AgentCore Runtime, Express.js, Mastra Agents with Tools                      |
| Example complexity  | Easy                                                                         |

## Overview

Amazon Bedrock AgentCore Runtime provides a secure, serverless hosting environment for deploying AI agents. This implementation creates REST API endpoints that comply with the AgentCore HTTP protocol contract.

### Features

- **Streaming Responses**: Real-time token-by-token streaming of agent responses
- **Mastra Agent with Tools**: Utility agent equipped with three specialized tools:
  - `getCurrentTimeTool`: Get current time in any timezone
  - `calculateTool`: Perform arithmetic operations (add, subtract, multiply, divide)
  - `generateRandomNumberTool`: Generate random numbers within a specified range
- **Express.js Server**: HTTP server implementing the AgentCore protocol
- **CloudFormation Deployment**: Automated deployment to AWS with Docker containerization
- **SSM Integration**: Agent runtime configuration stored in Parameter Store

## Prerequisites

- **Node.js 20 or 21**: Required by Mastra framework
  - [Download Node.js](https://nodejs.org/en/download/)
  - Verify installation: `node --version`
- **npm**: Package manager (comes with Node.js)
  - Verify installation: `npm --version`
- **TypeScript**: TypeScript compiler (installed as dev dependency)
- **AWS account**: You need an active AWS account with appropriate permissions
  - [Create an AWS account](https://aws.amazon.com/account/)
  - [AWS Management Console access](https://aws.amazon.com/console/)
- **AWS CLI**: Install and configure AWS CLI with your credentials
  - [Install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  - [Configure AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)
- **OpenAI API key** (for the GPT-4o-mini model), [docs](https://openai.com/index/openai-api/)

## Local Development & Testing

```bash
git clone https://github.com/awslabs/amazon-bedrock-agentcore-samples.git
cd 03-integrations/agentic-frameworks/typescript_mastra
```

### OpenAI API Key

> [!IMPORTANT]  
> Make sure to replace `<ValidAPIKey>` with valid API key from [OpenAI](https://openai.com/index/openai-api/).

```bash
export OPENAI_API_KEY="<ValidAPIKey>"
```

### Build and Run

```bash
# Install dependencies
npm install

# Build the TypeScript project
npm run build

# Start the server
npm start

# Or run in development mode with auto-reload
npm run dev
```

The application will start on `http://localhost:8080`

### Test the Endpoints

**Test /invocations (streaming response):**

```bash
# Simple greeting
curl --no-buffer -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: gfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmt" \
  -d '{"prompt": "Hello, how are you?"}'

# Test with calculation tool
curl --no-buffer -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: gfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmt" \
  -d '{"prompt": "What is 12345 multiplied by 6789?"}'

# Test with time tool
curl --no-buffer -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: gfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmt" \
  -d '{"prompt": "What is the current time in Tokyo?"}'
```

> **Note**: The `--no-buffer` flag ensures you see the streaming response in real-time.

**Test /ping:**

```bash
curl http://localhost:8080/ping
```

## Deploy to AgentCore Runtime Using AWS CloudFormation

### Step 1: Deploy CloudFormation Stack

> [!IMPORTANT]  
> Make sure to replace `<ValidAPIKey>` with valid API key from [OpenAI](https://openai.com/index/openai-api/).

```bash
# Deploy the CloudFormation stack
aws cloudformation create-stack \
  --stack-name ts-mastra-agent \
  --template-body file://cloudformation/github-source.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters \
    ParameterKey=AgentName,ParameterValue=tsmastraagent \
    ParameterKey=OpenAIApiKey,ParameterValue=<ValidAPIKey>

# Wait for stack creation to complete
aws cloudformation wait stack-create-complete \
  --stack-name ts-mastra-agent

# Get stack outputs
aws cloudformation describe-stacks \
  --stack-name ts-mastra-agent \
  --query "Stacks[0].Outputs" \
  --output table
```

### Step 2: Testing

Once your agent is deployed, you can test it using the [invoke script](./scripts/invoke-agent.ts).

The script retrieves the Agent Runtime ARN from SSM Parameter Store and invokes the deployed agent with streaming support.

```bash
# Set your AWS region (if different from default)
export AWS_REGION=us-east-1

# Invoke the agent with default prompt
AGENT_NAME=tsmastraagent npm run invoke-agent

# Invoke with a custom prompt
AGENT_NAME=tsmastraagent PROMPT="What is 123 times 456?" npm run invoke-agent

# Test with timezone tool
AGENT_NAME=tsmastraagent PROMPT="What time is it in Paris?" npm run invoke-agent

# Test with random number generation
AGENT_NAME=tsmastraagent PROMPT="Generate a random number between 1 and 100" npm run invoke-agent
```

The script will:
1. Retrieve the Agent Runtime ARN from SSM Parameter Store at `/hostagent/agentcore/tsmastraagent/runtime-arn`
2. Invoke the agent runtime with your prompt
3. Stream the response in real-time to your terminal

## Cleanup

To delete all resources created by the CloudFormation stack:

```bash
# Delete the CloudFormation stack
aws cloudformation delete-stack \
  --stack-name ts-mastra-agent

# Wait for stack deletion to complete
aws cloudformation wait stack-delete-complete \
  --stack-name ts-mastra-agent

# Verify deletion
aws cloudformation describe-stacks \
  --stack-name ts-mastra-agent | grep -q "does not exist" && echo "Stack successfully deleted"
```
