# Claude Code Integration for Amazon Bedrock AgentCore

This integration enables Claude Code to run autonomously on Amazon Bedrock AgentCore, providing powerful AI-driven code generation capabilities without requiring an Anthropic API key.

## 🎯 Overview

Claude Code Headless Mode provides a complete implementation for deploying Claude Code as an autonomous agent on Amazon Bedrock AgentCore. This enables you to run coding tasks in the cloud with full automation capabilities.

**Key Features:**
- ✅ **No Anthropic API Key Required** - Uses Amazon Bedrock
- ✅ **Autonomous Operation** - Runs without human intervention  
- ✅ **Cost Effective** - ~$0.30-0.50 per complex task
- ✅ **Scalable** - Leverages AgentCore's serverless architecture
- ✅ **Production Ready** - Complete with monitoring and logging

## 🚀 Quick Start

### Prerequisites

- **AWS Account** with Bedrock access
- **Python 3.10+**
- **AWS CLI** configured
- **Docker** installed (for local testing)
- **Bedrock Model Access** for Claude models
- **AgentCore Toolkit**: `pip install bedrock-agentcore-starter-toolkit`

### Installation Steps

```bash
# Step 1: Install dependencies
cd 03-integrations/claude-code
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Step 2: Install required packages including AgentCore CLI
pip install -r requirements.txt
pip install bedrock-agentcore-starter-toolkit

# Step 3: Navigate to headless mode directory
cd headless-mode

# Step 4: Set up IAM role (for AWS deployment features)
cd iam && chmod +x setup-iam-role.sh && ./setup-iam-role.sh && cd ..

# Step 5: Deploy using the manual deployment script
# This preserves our custom Dockerfile with Node.js and Claude Code CLI
chmod +x deploy_claude_code.py
python deploy_claude_code.py

# The script will build, push to ECR, and deploy the agent

# Step 6: Invoke the agent with example prompt
# Replace YOUR_RUNTIME_ARN with the ARN from deployment output
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn YOUR_RUNTIME_ARN \
  --region us-east-1 \
  --payload '{"input": {"prompt": "Create a modern coffee shop website called Brew Haven with menu, location, and contact sections. Deploy it to S3 and CloudFront."}}' \
  response.json
```

### Local Testing

You can test the agent locally before deploying:

```bash
# Build and run the Docker container
cd headless-mode
docker build -t claude-code-headless .
docker run -d --name claude-code-headless -p 8080:8080 -v ~/.aws:/root/.aws:ro claude-code-headless

# Test the agent
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"input": {"prompt": "Create a simple hello.py file that prints Hello, World!"}}' \
  | python3 -m json.tool

# Clean up
docker stop claude-code-headless
docker rm claude-code-headless
```

## 📚 Documentation

- [Headless Mode Documentation](headless-mode/README.md) - Detailed deployment guide
- [Example Prompts](headless-mode/examples/example_prompts.json) - Sample tasks for testing

## 🎯 Use Cases

- **Code Generation** - Create complete applications from descriptions
- **Code Refactoring** - Improve existing code quality and performance
- **Test Creation** - Generate comprehensive test suites
- **Documentation** - Auto-generate documentation for codebases
- **Migration** - Convert code between frameworks or languages
- **Analysis** - Review code for security, performance, and best practices
- **AWS Infrastructure** - Generate CloudFormation/CDK templates and deploy resources

## 📦 Project Structure

```
claude-code/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── test_headless_mode.py        # Test script for headless mode
│
└── headless-mode/              # AgentCore deployment
    ├── agent.py                # Main agent implementation
    ├── deploy_claude_code.py   # Deployment script
    ├── Dockerfile              # Container configuration
    ├── pyproject.toml          # Python project configuration
    ├── uv.lock                 # Dependency lock file
    ├── README.md              # Detailed deployment guide
    ├── examples/              # Example prompts
    │   └── example_prompts.json
    └── iam/                   # IAM configuration
        ├── permissions-policy.json
        ├── trust-policy.json
        └── setup-iam-role.sh
```

## 🧪 Testing

Test script is provided in the root directory:

```bash
# Test headless mode deployment
python test_headless_mode.py
```

## 📊 Performance & Cost

- **Task Duration**: 10-30 seconds for typical tasks
- **Cost**: ~$0.30-0.50 per complex task
- **Concurrency**: Supports multiple simultaneous requests
- **Scaling**: Auto-scales based on demand

## 🔄 Coming Soon

- **Python SDK** - A Python wrapper for programmatic access to Claude Code will be added in a future update, enabling:
  - Integration into Python applications
  - Custom workflow development
  - Batch processing capabilities
  - Advanced session management

## 🤝 Contributing

Contributions are welcome! Please:
1. Test your changes locally
2. Update relevant documentation
3. Submit a pull request

## 📄 License

This integration is provided as-is for educational and experimental purposes. Ensure compliance with your organization's policies and AWS service terms.

## 🙏 Acknowledgments

- Claude Code by Anthropic
- Amazon Bedrock AgentCore team
- AWS SDK for Python (boto3)
