# Weather-Based Activity Planning Agent
ded in this repository are for experimental and educational purposes only. They demonstrate concepts and techniques but are not intended for direct use in production environments.

This CloudFormation template deploys a complete, production-ready Amazon Bedrock AgentCore Runtime with a sophisticated weather-based activity planning agent. This demonstrates the full power of AgentCore by integrating Browser tool, Code Interpreter, Memory, and S3 storage in a single deployment.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Deployment](#deployment)
- [Testing](#testing)
- [Sample Queries](#sample-queries)
- [How It Works](#how-it-works)
- [Cleanup](#cleanup)
- [Cost Estimate](#cost-estimate)
- [Troubleshooting](#troubleshooting)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

## Overview

This template creates a comprehensive AgentCore deployment that showcases:

### Core Components

- **AgentCore Runtime**: Hosts a Strands agent with multiple tools
- **Browser Tool**: Web automation for scraping weather data from weather.gov
- **Code Interpreter**: Python code execution for weather analysis
- **Memory**: Stores user activity preferences
- **S3 Bucket**: Stores generated activity recommendations
- **ECR Repository**: Container image storage
- **IAM Roles**: Comprehensive permissions for all components

### Agent Capabilities

The Weather Activity Planner agent can:

1. **Scrape Weather Data**: Uses browser automation to fetch 8-day forecasts from weather.gov
2. **Analyze Weather**: Generates and executes Python code to classify days as GOOD/OK/POOR
3. **Retrieve Preferences**: Accesses user activity preferences from memory
4. **Generate Recommendations**: Creates personalized activity suggestions based on weather and preferences
5. **Store Results**: Saves recommendations as Markdown files in S3

### Use Cases

- Weather-based activity planning
- Automated web scraping and data analysis
- Multi-tool agent orchestration
- Memory-driven personalization
- Asynchronous task processing

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                       CloudFormation Stack                            │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    AgentCore Runtime                            │ │
│  │  ┌───────────────────────────────────────────────────────────┐ │ │
│  │  │         Weather Activity Planner Agent                    │ │ │
│  │  │                                                           │ │ │
│  │  │  Workflow:                                                │ │ │
│  │  │  1. Extract city from query                              │ │ │
│  │  │  2. Scrape weather data (Browser Tool) ──────────┐       │ │ │
│  │  │  3. Generate analysis code (LLM)                 │       │ │ │
│  │  │  4. Execute code (Code Interpreter) ─────────┐   │       │ │ │
│  │  │  5. Get preferences (Memory) ────────────┐   │   │       │ │ │
│  │  │  6. Generate recommendations             │   │   │       │ │ │
│  │  │  7. Store in S3 (use_aws tool) ──────┐   │   │   │       │ │ │
│  │  └──────────────────────────────────────│───│───│───│───────┘ │ │
│  └───────────────────────────────────────────│───│───│───│─────────┘ │
│                                               │   │   │   │           │
│  ┌────────────────────────────────────────────│───│───│───│─────────┐ │
│  │  Browser Tool                              │   │   │   │         │ │
│  │  - WebSocket connection                    │   │   │   │         │ │
│  │  - Puppeteer automation                    │   │   │   │         │ │
│  │  - Weather.gov scraping                    │   │   │   │         │ │
│  └────────────────────────────────────────────┘   │   │   │         │ │
│                                                    │   │   │           │
│  ┌─────────────────────────────────────────────────│───│───│────────┐ │
│  │  Code Interpreter Tool                         │   │   │        │ │
│  │  - Weather classification logic                │   │   │        │ │
│  │  - Data analysis                               │   │   │        │ │
│  └────────────────────────────────────────────────┘   │   │        │ │
│                                                        │   │          │
│  ┌──────────────────────────────────────────────────────│───│───────┐ │
│  │  Memory                                             │   │       │ │
│  │  - Activity preferences by weather type            │   │       │ │
│  │  - User session data                               │   │       │ │
│  │  - 30-day retention                                │   │       │ │
│  └────────────────────────────────────────────────────┘   │       │ │
│                                                            │         │
│  ┌──────────────────────────────────────────────────────────│──────┐ │
│  │  S3 Bucket (Results Storage)                            │      │ │
│  │  - Markdown activity recommendations                    │      │ │
│  │  - Versioning enabled                                   │      │ │
│  │  - Private access only                                  │      │ │
│  └─────────────────────────────────────────────────────────┘      │ │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Supporting Infrastructure                                      │ │
│  │  - ECR Repository (ARM64 container image)                       │ │
│  │  - CodeBuild (automated image building)                         │ │
│  │  - Lambda (custom resources & memory initialization)            │ │
│  │  - IAM Roles (comprehensive permissions)                        │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

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
     - Anthropic Claude 3.7 Sonnet (for browser automation)
     - Anthropic Claude 3.5 Sonnet or Haiku (for agent reasoning)
   - [Bedrock Model Access Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

4. **Required Permissions**: Your AWS user/role needs permissions for:
   - CloudFormation stack operations
   - ECR repository management
   - IAM role creation
   - Lambda function creation
   - CodeBuild project creation
   - BedrockAgentCore resource creation (Runtime, Browser, CodeInterpreter, Memory)
   - S3 bucket creation

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
3. Display all resource IDs (Runtime, Browser, CodeInterpreter, Memory, S3 Bucket)

### Option 2: Using AWS CLI

```bash
# Deploy the stack
aws cloudformation create-stack \
  --stack-name weather-agent-demo \
  --template-body file://template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2

# Wait for stack creation
aws cloudformation wait stack-create-complete \
  --stack-name weather-agent-demo \
  --region us-west-2

# Get all outputs
aws cloudformation describe-stacks \
  --stack-name weather-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs'
```

### Option 3: Using AWS Console

1. Navigate to [CloudFormation Console](https://console.aws.amazon.com/cloudformation/)
2. Click "Create stack" → "With new resources"
3. Upload the `template.yaml` file
4. Enter stack name: `weather-agent-demo`
5. Review parameters (or use defaults)
6. Check "I acknowledge that AWS CloudFormation might create IAM resources"
7. Click "Create stack"

### Deployment Time

- **Expected Duration**: 15-20 minutes
- **Main Steps**:
  - Stack creation: ~2 minutes
  - Docker image build (CodeBuild): ~10-12 minutes
  - Runtime and tools provisioning: ~3-5 minutes
  - Memory initialization: ~1 minute

## Testing

### Using AWS CLI

```bash
# Get the Runtime ID from stack outputs
RUNTIME_ID=$(aws cloudformation describe-stacks \
  --stack-name weather-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentRuntimeId`].OutputValue' \
  --output text)

# Get the S3 bucket name
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name weather-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`ResultsBucket`].OutputValue' \
  --output text)

# Invoke the agent
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-id $RUNTIME_ID \
  --qualifier DEFAULT \
  --payload '{"prompt": "What should I do this weekend in Richmond VA?"}' \
  --region us-west-2 \
  response.json

# View the immediate response
cat response.json

# Wait a few minutes for processing, then check S3 for results
aws s3 ls s3://$BUCKET_NAME/

# Download the results
aws s3 cp s3://$BUCKET_NAME/results.md ./results.md
cat results.md
```

### Using AWS Console

1. Navigate to [Bedrock AgentCore Console](https://console.aws.amazon.com/bedrock-agentcore/)
2. Go to "Runtimes" in the left navigation
3. Find your runtime (name starts with `weather_agent_demo_`)
4. Click on the runtime name
5. Click "Test" button
6. Enter test payload:
   ```json
   {
     "prompt": "What should I do this weekend in Richmond VA?"
   }
   ```
7. Click "Invoke"
8. View the immediate response
9. Wait 2-3 minutes for background processing
10. Navigate to [S3 Console](https://console.aws.amazon.com/s3/) to download results.md from the results bucket

## Sample Queries

Try these queries to test the weather agent:

1. **Weekend Planning**:
   ```json
   {"prompt": "What should I do this weekend in Richmond VA?"}
   ```

2. **Specific City**:
   ```json
   {"prompt": "Plan activities for next week in San Francisco"}
   ```

3. **Different Location**:
   ```json
   {"prompt": "What outdoor activities can I do in Seattle this week?"}
   ```

4. **Vacation Planning**:
   ```json
   {"prompt": "I'm visiting Austin next week. What should I plan based on the weather?"}
   ```

## How It Works

### Step-by-Step Workflow

1. **User Query**: "What should I do this weekend in Richmond VA?"

2. **City Extraction**: Agent extracts "Richmond VA" from the query

3. **Weather Scraping** (Browser Tool):
   - Navigates to weather.gov
   - Searches for Richmond VA
   - Clicks "Printable Forecast"
   - Extracts 8-day forecast data (date, high, low, conditions, wind, precipitation)
   - Returns JSON array of weather data

4. **Code Generation** (LLM):
   - Agent generates Python code to classify weather days
   - Classification rules:
     - GOOD: 65-80°F, clear, no rain
     - OK: 55-85°F, partly cloudy, slight rain
     - POOR: <55°F or >85°F, cloudy/rainy

5. **Code Execution** (Code Interpreter):
   - Executes the generated Python code
   - Returns list of tuples: `[('2025-09-16', 'GOOD'), ('2025-09-17', 'OK'), ...]`

6. **Preference Retrieval** (Memory):
   - Fetches user activity preferences from memory
   - Preferences stored by weather type:
     ```json
     {
       "good_weather": ["hiking", "beach volleyball", "outdoor picnic"],
       "ok_weather": ["walking tours", "outdoor dining", "park visits"],
       "poor_weather": ["indoor museums", "shopping", "restaurants"]
     }
     ```

7. **Recommendation Generation** (LLM):
   - Combines weather analysis with user preferences
   - Creates day-by-day activity recommendations
   - Formats as Markdown document

8. **Storage** (S3 via use_aws tool):
   - Saves recommendations to S3 bucket as `results.md`
   - User can download and review recommendations

### Asynchronous Processing

The agent runs asynchronously to handle long-running tasks:
- Immediate response: "Processing started..."
- Background processing: Completes all steps
- Results available in S3 after ~2-3 minutes

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
# Empty the S3 bucket first (required before deletion)
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name weather-agent-demo \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`ResultsBucket`].OutputValue' \
  --output text)

aws s3 rm s3://$BUCKET_NAME --recursive

# Delete the stack
aws cloudformation delete-stack \
  --stack-name weather-agent-demo \
  --region us-west-2

# Wait for deletion to complete
aws cloudformation wait stack-delete-complete \
  --stack-name weather-agent-demo \
  --region us-west-2
```

### Using AWS Console

1. Navigate to [S3 Console](https://console.aws.amazon.com/s3/)
2. Find the bucket (name starts with `weather-agent-demo-agentcore-cfn-results`)
3. Empty the bucket
4. Navigate to [CloudFormation Console](https://console.aws.amazon.com/cloudformation/)
5. Select the `weather-agent-demo` stack
6. Click "Delete"
7. Confirm deletion


