# Claude Code Integration for Amazon Bedrock AgentCore

This integration enables Claude Code to run autonomously on Amazon Bedrock AgentCore, providing powerful AI-driven code generation capabilities without requiring an Anthropic API key.

## 📁 Folder Structure

This integration provides two approaches for using Claude Code with AgentCore:

### 1. **headless-mode/** - Production Deployment
Complete implementation for deploying Claude Code as an autonomous agent on Amazon Bedrock AgentCore.

**Use this when you want to:**
- Deploy Claude Code to AgentCore Runtime
- Run autonomous coding tasks in the cloud
- Build production-ready coding automation
- Scale code generation capabilities

**Key Features:**
- Full AgentCore deployment with Docker container
- Configured for Amazon Bedrock inference
- Production-ready with CloudWatch monitoring
- Cost-effective (~$0.30-0.50 per task)

[📖 See headless-mode/README.md for detailed deployment instructions](headless-mode/README.md)

### 2. **python-sdk/** - Programmatic Access
Python SDK wrapper for programmatic interaction with Claude Code.

**Use this when you want to:**
- Integrate Claude Code into Python applications
- Build custom workflows with Claude Code
- Develop local prototypes
- Create automated code generation pipelines

**Key Features:**
- Simple Python API for Claude Code
- AgentCore-compatible wrapper
- Local and remote execution support
- Session management for multi-turn interactions

[📖 See python-sdk/README.md for SDK documentation](python-sdk/README.md)

## 🚀 Quick Start

### For AgentCore Deployment (Recommended)

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

# Step 5: Configure and deploy with Docker runtime
# Replace YOUR_ACCOUNT_ID with your AWS account ID
ROLE_ARN="arn:aws:iam::YOUR_ACCOUNT_ID:role/claude-code-agentcore-role"
agentcore configure -e claude_code_agent.py \
  --execution-role $ROLE_ARN \
  --container-runtime docker \
  --requirements-file requirements.txt \
  --ecr auto

# Step 6: Launch the agent
agentcore launch

# Step 7: Invoke the agent with example prompt
agentcore invoke '{
  "prompt": "Create a modern coffee shop website called Brew Haven with menu, location, and contact sections. Deploy it to S3 and CloudFront."
}'
```

### For Python SDK Usage

```bash
# Navigate to python-sdk
cd python-sdk

# Install dependencies
pip install -r requirements.txt

# Use in your Python code
from claude_code_sdk_wrapper import ClaudeCodeSDK

sdk = ClaudeCodeSDK()
result = sdk.execute("Create a REST API with FastAPI")
print(result['result'])
```

## 🔧 Prerequisites

- **AWS Account** with Bedrock access
- **Python 3.10+**
- **AWS CLI** configured
- **Bedrock Model Access** for Claude models
- **AgentCore Toolkit** (for deployment): `pip install bedrock-agentcore-starter-toolkit`

## 📊 Key Benefits

- ✅ **No Anthropic API Key Required** - Uses Amazon Bedrock
- ✅ **Autonomous Operation** - Runs without human intervention
- ✅ **Cost Effective** - ~$0.30-0.50 per complex task
- ✅ **Scalable** - Leverages AgentCore's serverless architecture
- ✅ **Production Ready** - Complete with monitoring and logging

## 📚 Documentation

- [Headless Mode Documentation](headless-mode/README.md) - Full deployment guide
- [Python SDK Documentation](python-sdk/README.md) - SDK usage and examples
- [Example Prompts](headless-mode/examples/example_prompts.json) - Sample tasks

## 🧪 Testing

Test scripts are provided in the root directory:

```bash
# Test headless mode
python test_headless_mode.py

# Test Python SDK
python test_python_sdk.py
```

## 🎯 Use Cases

- **Code Generation** - Create complete applications from descriptions
- **Code Refactoring** - Improve existing code quality and performance
- **Test Creation** - Generate comprehensive test suites
- **Documentation** - Auto-generate documentation for codebases
- **Migration** - Convert code between frameworks or languages
- **Analysis** - Review code for security, performance, and best practices

## 📦 What's Included

```
claude-code/
├── README.md                    # This file
├── requirements.txt             # Shared Python dependencies
├── test_headless_mode.py        # Test script for headless mode
├── test_python_sdk.py          # Test script for Python SDK
│
├── headless-mode/              # AgentCore deployment
│   ├── claude_code_agent.py    # Main agent implementation
│   ├── requirements.txt        # Agent dependencies
│   ├── Dockerfile              # Container configuration
│   ├── README.md              # Detailed deployment guide
│   └── examples/              # Example prompts
│
└── python-sdk/                 # Python SDK wrapper
    ├── claude_code_sdk_wrapper.py # SDK implementation
    ├── requirements.txt        # SDK dependencies
    ├── README.md              # SDK documentation
    └── examples/              # Usage examples
```

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
