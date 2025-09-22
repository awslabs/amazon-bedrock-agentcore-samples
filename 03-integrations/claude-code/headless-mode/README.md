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
- **Node.js 20+** (for Claude Code CLI)
- **Amazon Bedrock** model access enabled for Claude models
- **AgentCore Toolkit** (`pip install bedrock-agentcore-starter-toolkit`)

## Quick Start

### 1. Install Dependencies

```bash
# From the claude-code directory
cd 03-integrations/claude-code

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Install AgentCore toolkit
pip install bedrock-agentcore-starter-toolkit

# Install Claude Code CLI globally (optional, for local testing)
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

### 3. Deploy to AgentCore

```bash
cd headless-mode

# Configure the agent
agentcore configure -e claude_code_agent.py

# Deploy to cloud (builds container with CodeBuild)
agentcore launch

# The deployment will output:
# ✅ Agent ARN: arn:aws:bedrock-agentcore:region:account:runtime/claude_code_agent-xxxxx
# ✅ CloudWatch Logs: /aws/bedrock-agentcore/runtimes/claude_code_agent-xxxxx-DEFAULT
```

### 4. Invoke the Agent

```bash
# Basic code generation
agentcore invoke '{
  "prompt": "Create a Python FastAPI application with user authentication"
}'

# Complex multi-file project
agentcore invoke '{
  "prompt": "Build a complete React TypeScript application with routing, state management, and tests"
}'

# Code refactoring
agentcore invoke '{
  "prompt": "Refactor this code for better performance and add comprehensive tests",
  "context": "def calculate(n): result = []; for i in range(n): if is_prime(i): result.append(i); return result"
}'
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

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:*:*:inference-profile/*"
    },
    {
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

**Note:** Additional permissions (S3, CloudFront, etc.) can be added if you want Claude Code to deploy infrastructure.

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

1. **"Claude Code not found" error**
   - The Claude Code CLI is installed in the container during build
   - For local testing, install: `npm install -g @anthropic-ai/claude-code`

2. **Authentication errors**
   - Ensure AWS credentials are configured: `aws configure`
   - Verify Bedrock model access is enabled in your region

3. **Timeout errors**
   - Increase timeout: Set `CLAUDE_CODE_TIMEOUT` environment variable
   - Complex tasks may take 3-5 minutes

4. **Permission denied errors**
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
