# Claude Code Headless Mode for Amazon Bedrock AgentCore

This folder contains the complete implementation for deploying Claude Code as an autonomous agent on Amazon Bedrock AgentCore.

## Overview

Claude Code is an AI-powered coding assistant that can autonomously complete programming tasks. This integration packages Claude Code as an AgentCore-compatible agent that:

- 🤖 **Runs autonomously** without interactive UI using headless mode
- 🚀 **Deploys to AgentCore** for scalable, serverless execution
- 🔧 **Uses Amazon Bedrock** for model inference (no Anthropic API key required)
- 📝 **Handles complex tasks** with multi-step reasoning and file operations
- 💰 **Cost-effective** - typical tasks cost under $0.50

## Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│   User Request  │────▶│  AgentCore Runtime   │────▶│  Claude Code    │
│   (JSON)        │     │  (Container)         │     │  (Headless)     │
└─────────────────┘     └──────────────────────┘     └─────────────────┘
                                 │                            │
                                 ▼                            ▼
                        ┌──────────────────────┐     ┌─────────────────┐
                        │  Amazon Bedrock      │◀────│  Code Execution │
                        │  Claude Models       │     │  & File Ops     │
                        └──────────────────────┘     └─────────────────┘
```

## Prerequisites

- **AWS Account** with appropriate permissions
- **AWS CLI** configured (`aws configure`)
- **Python 3.10+** installed
- **Docker** (optional, for local testing)
- **Node.js 20+** (for Claude Code CLI, installed in container)
- **Amazon Bedrock** model access enabled for Claude models
- **AgentCore CLI Toolkit** - REQUIRED for deployment commands:
  ```bash
  pip install bedrock-agentcore-starter-toolkit
  ```

## Quick Start

### 1. Install Dependencies

```bash
# From the repository root, navigate to claude-code directory
cd 03-integrations/claude-code

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# IMPORTANT: Install AgentCore CLI toolkit (provides 'agentcore' command)
pip install bedrock-agentcore-starter-toolkit

# Verify AgentCore CLI is installed
agentcore --version
# If you get "command not found", ensure your virtual environment is activated

# Optional: Install Claude Code CLI for local testing only
# (The container will install this automatically during build)
npm install -g @anthropic-ai/claude-code
```

### 2. Configure for Bedrock

The integration is pre-configured to use Amazon Bedrock. The following environment variables are automatically set in the Dockerfile:

```bash
CLAUDE_CODE_USE_BEDROCK=1
AWS_REGION=us-east-1  # Or your preferred region
CLAUDE_CODE_MAX_OUTPUT_TOKENS=4096
MAX_THINKING_TOKENS=1024
```

### 3. Set Up IAM Role (Required for AWS Deployment)

If you want Claude Code to deploy websites to S3 and CloudFront, you need to set up an IAM role:

```bash
cd headless-mode/iam

# Make the script executable
chmod +x setup-iam-role.sh

# Run the IAM setup script
./setup-iam-role.sh

# This will output an IAM Role ARN that you'll use in the next step
```

The IAM role grants permissions to:
- Invoke Bedrock models
- Create and manage S3 buckets (with prefix 'claude-code-*')
- Create and manage CloudFront distributions
- Write CloudWatch logs

### 4. Deploy to AgentCore

**Important:** We use a manual deployment approach to preserve our custom Dockerfile with Node.js and Claude Code CLI.

```bash
cd .. # Back to headless-mode directory

# Make the deployment script executable
chmod +x deploy_claude_code.py

# Run the deployment script
python deploy_claude_code.py

# The script will:
# 1. Create an ECR repository
# 2. Build the Docker image with our custom Dockerfile
# 3. Push the image to ECR
# 4. Deploy the agent runtime to AgentCore

# The deployment will output:
# ✅ Agent Runtime ARN: arn:aws:bedrock-agentcore:region:account:runtime/claude-code-agent-runtime
# ✅ Container Image: account-id.dkr.ecr.region.amazonaws.com/bedrock-agentcore-claude-code-agent:latest
```

**Note:** The deployment script (`deploy_claude_code.py`) preserves our custom Dockerfile with Node.js and Claude Code CLI installation, which is essential for the agent to work properly.

### 5. Invoke the Agent

After deployment, you can invoke the agent using the AWS CLI:

```bash
# Replace with your actual runtime ARN from the deployment output
aws bedrock-agentcore invoke-agent-runtime \
    --agent-runtime-arn arn:aws:bedrock-agentcore:us-east-1:YOUR_ACCOUNT_ID:runtime/claude_code_agent_runtime \
    --region us-east-1 \
    --payload '{"prompt": "Create a coffee shop website called Brew Haven with menu, location, and contact sections. Deploy it to S3 and CloudFront."}' \
    claude_code_agent_response.json

# View the response
cat claude_code_agent_response.json
```

#### Example Prompts

```bash
# Basic code generation
aws bedrock-agentcore invoke-agent-runtime \
    --agent-runtime-arn YOUR_RUNTIME_ARN \
    --region us-east-1 \
    --payload '{"prompt": "Create a Python FastAPI application with user authentication"}' \
    response.json

# Complex multi-file project
aws bedrock-agentcore invoke-agent-runtime \
    --agent-runtime-arn YOUR_RUNTIME_ARN \
    --region us-east-1 \
    --payload '{"prompt": "Build a complete React TypeScript application with routing, state management, and tests"}' \
    response.json

# Code refactoring
aws bedrock-agentcore invoke-agent-runtime \
    --agent-runtime-arn YOUR_RUNTIME_ARN \
    --region us-east-1 \
    --payload '{"prompt": "Refactor this code for better performance and add comprehensive tests", "context": "def calculate(n): result = []; for i in range(n): if is_prime(i): result.append(i); return result"}' \
    response.json
```

## Usage Examples

### Example 1: Generate a REST API

```bash
agentcore invoke '{
  "prompt": "Create a complete REST API with FastAPI including:
    - User model with SQLAlchemy
    - CRUD operations
    - JWT authentication
    - Input validation with Pydantic
    - Unit tests with pytest"
}'
```

**Expected Output:**
- Multiple Python files created (models.py, routes.py, auth.py, tests/)
- Complete working API with all requested features
- Documentation and setup instructions

### Example 2: Analyze and Refactor Code

```bash
agentcore invoke '{
  "prompt": "Analyze this Python code for performance issues and refactor it with best practices",
  "context": "paste your code here"
}'
```

### Example 3: Create Full-Stack Application

```bash
agentcore invoke '{
  "prompt": "Create a full-stack task management application with:
    - React frontend with TypeScript
    - Node.js/Express backend
    - MongoDB database schema
    - Docker Compose setup
    - README with setup instructions"
}'
```

## Configuration Options

### Payload Parameters

```json
{
  "prompt": "Your task description",
  "session_id": "optional-session-id-for-continuity",
  "continue": false,
  "allowed_tools": "Bash,Read,Write,Replace,Search,List,WebFetch",
  "output_format": "json",
  "permission_mode": "acceptEdits",
  "append_system_prompt": "Optional additional instructions"
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAUDE_CODE_USE_BEDROCK` | Enable Bedrock integration | `1` |
| `AWS_REGION` | AWS region for Bedrock | `us-east-1` |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | Maximum output tokens | `4096` |
| `MAX_THINKING_TOKENS` | Maximum thinking tokens | `1024` |
| `CLAUDE_CODE_VERBOSE` | Enable verbose logging | `false` |
| `CLAUDE_CODE_TIMEOUT` | Execution timeout (seconds) | `600` |

## Response Format

```json
{
  "success": true,
  "result": "Detailed completion message with created files and instructions",
  "session_id": "uuid-for-session-continuation",
  "metadata": {
    "cost_usd": 0.45,
    "duration_ms": 180000,
    "num_turns": 58
  },
  "error": null
}
```

## IAM Permissions

The AgentCore execution role needs the following permissions:

### Core Permissions (Required)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockModelAccess",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:*:*:inference-profile/*"
    },
    {
      "Sid": "ECRAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

### Additional Permissions for AWS Deployment (Optional)

If you want Claude Code to deploy websites to S3 and CloudFront, add these permissions:

```json
{
  "Sid": "S3Operations",
  "Effect": "Allow",
  "Action": [
    "s3:CreateBucket",
    "s3:PutBucket*",
    "s3:PutObject",
    "s3:PutObjectAcl"
  ],
  "Resource": [
    "arn:aws:s3:::claude-code-*",
    "arn:aws:s3:::claude-code-*/*"
  ]
},
{
  "Sid": "CloudFrontOperations",
  "Effect": "Allow",
  "Action": [
    "cloudfront:CreateDistribution",
    "cloudfront:GetDistribution"
  ],
  "Resource": "*"
}
```

**Note:** The IAM setup script in `iam/setup-iam-role.sh` automatically configures all these permissions.

## Files in This Directory

- **claude_code_agent.py** - Main agent implementation with AgentCore entrypoint
- **requirements.txt** - Python dependencies for the agent
- **Dockerfile** - Container configuration with Claude Code CLI and Bedrock setup
- **.dockerignore** - Files to exclude from Docker build
- **.bedrock_agentcore.yaml** - AgentCore deployment configuration
- **examples/** - Example prompts and usage patterns

## Testing

### Local Testing

```bash
# Test the agent locally (from parent directory)
cd ..
python test_headless_mode.py
```

### Container Testing

```bash
# Build container locally
docker build -t claude-code-agent .

# Run container
docker run -p 8080:8080 \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  -e AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN \
  claude-code-agent

# Test endpoint
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Create a hello world Python script"}'
```

## Monitoring

After deployment, monitor your agent through:

1. **CloudWatch Logs**
   ```bash
   aws logs tail /aws/bedrock-agentcore/runtimes/claude_code_agent-xxxxx-DEFAULT --follow
   ```

2. **AgentCore Status**
   ```bash
   agentcore status
   ```

3. **GenAI Observability Dashboard**
   - Navigate to CloudWatch Console
   - Select GenAI Observability → Agent Core

## Cost Optimization

- **Typical costs**: $0.30-0.50 per complex task
- **Optimize by**:
  - Setting appropriate token limits
  - Using session continuity for related tasks
  - Batching similar operations

## Troubleshooting

### Common Issues

1. **"agentcore: command not found" error**
   - The AgentCore CLI must be installed first:
     ```bash
     pip install bedrock-agentcore-starter-toolkit
     ```
   - Ensure your virtual environment is activated:
     ```bash
     source venv/bin/activate  # On Windows: venv\Scripts\activate
     ```
   - Verify installation:
     ```bash
     agentcore --version
     ```

2. **"Claude Code not found" error**
   - The Claude Code CLI is installed in the container during build
   - For local testing, install: `npm install -g @anthropic-ai/claude-code`

3. **Authentication errors**
   - Ensure AWS credentials are configured: `aws configure`
   - Verify Bedrock model access is enabled in your region

4. **Timeout errors**
   - Increase timeout: Set `CLAUDE_CODE_TIMEOUT` environment variable
   - Complex tasks may take 3-5 minutes

5. **Permission denied errors**
   - Check IAM role has Bedrock invoke permissions
   - Verify the execution role was created during deployment

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
agentcore invoke '{
  "prompt": "Your task",
  "verbose": true
}' --verbose
```

## Limitations

- **File system**: Claude Code operates in a containerized environment
- **Internet access**: Limited to allowed tools (WebFetch)
- **Execution time**: Default 10-minute timeout
- **AWS operations**: Requires additional IAM permissions

## License

This integration is provided as-is for educational and experimental purposes. Ensure compliance with your organization's policies and AWS service terms.
