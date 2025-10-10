# CloudFormation Samples for Amazon Bedrock AgentCore

Production-ready CloudFormation templates for deploying Amazon Bedrock AgentCore resources.

## Overview

These CloudFormation templates enable you to:
- Deploy AgentCore resources consistently across environments
- Automate infrastructure provisioning with Infrastructure as Code
- Maintain version control of your infrastructure
- Implement AWS best practices for security and monitoring

## 📚 Available Samples

### 01. [Hosting MCP Server on AgentCore Runtime](./mcp-server-agentcore-runtime/)

Deploy a complete MCP (Model Context Protocol) server with automated Docker image building and JWT authentication.

**What it deploys:**
- Amazon ECR Repository for Docker images
- AWS CodeBuild for automated ARM64 builds
- Amazon Cognito for JWT authentication
- IAM roles with least-privilege policies
- Lambda functions for custom resource automation
- Amazon Bedrock AgentCore Runtime hosting the MCP server

**Sample MCP Tools:**
- `add_numbers` - Adds two numbers
- `multiply_numbers` - Multiplies two numbers
- `greet_user` - Greets a user by name

**Deployment time:** ~10-15 minutes  
**Estimated cost:** ~$50-100/month

**Quick start:**
```bash
cd mcp-server-agentcore-runtime
./deploy.sh
./test.sh
```

---

### 02. [Basic Agent Runtime](./basic-runtime/)

Deploy a basic AgentCore Runtime with a simple Strands agent - no additional tools or memory.

**What it deploys:**
- Amazon ECR Repository
- AWS CodeBuild for ARM64 Docker image building
- IAM roles with least-privilege policies
- Lambda functions for automation
- Basic AgentCore Runtime with simple agent

**Use case:** Simple agent deployment without memory, code interpreter, or browser tools

**Deployment time:** ~10-15 minutes  
**Estimated cost:** ~$50-100/month

**Quick start:**
```bash
aws cloudformation create-stack \
  --stack-name basic-agent-demo \
  --template-body file://basic-runtime/template.yaml \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

---

### 03. [Multi-Agent Runtime](./multi-agent-runtime/)

Deploy a multi-agent system where Agent1 (orchestrator) can invoke Agent2 (specialist) for complex tasks.

**What it deploys:**
- Two ECR Repositories (one per agent)
- AWS CodeBuild projects for both agents
- IAM roles with agent-to-agent invocation permissions
- Lambda functions for automation
- Two AgentCore Runtimes with agent-to-agent communication

**Architecture:**
- **Agent1 (Orchestrator)**: Routes requests and delegates to Agent2
- **Agent2 (Specialist)**: Handles detailed analysis and complex tasks

**Deployment time:** ~15-20 minutes  
**Estimated cost:** ~$100-200/month

**Quick start:**
```bash
aws cloudformation create-stack \
  --stack-name multi-agent-demo \
  --template-body file://multi-agent-runtime/template.yaml \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

---

### 04. [Weather Agent with Tools and Memory](./weather-agent-runtime/)

Deploy a complete weather-based activity planning agent with browser automation, code interpreter, and memory.

**What it deploys:**
- Amazon ECR Repository
- AWS CodeBuild for ARM64 Docker image building
- S3 bucket for results storage
- IAM roles with comprehensive permissions
- Lambda functions for automation
- AgentCore Runtime with Strands agent
- **Browser Tool** for web scraping weather data
- **Code Interpreter Tool** for weather analysis
- **Memory** for storing user preferences

**Features:**
- Scrapes weather data from weather.gov using browser automation
- Analyzes weather conditions using Python code execution
- Stores and retrieves user activity preferences
- Generates personalized activity recommendations
- Saves results to S3 bucket

**Deployment time:** ~15-20 minutes  
**Estimated cost:** ~$100-150/month

**Quick start:**
```bash
aws cloudformation create-stack \
  --stack-name weather-agent-demo \
  --template-body file://weather-agent-runtime/template.yaml \
  --capabilities CAPABILITY_IAM \
  --region us-west-2
```

---

## Prerequisites

Before deploying any CloudFormation template, ensure you have:

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
   ```bash
   aws configure
   ```
3. **Access to Amazon Bedrock AgentCore** (preview)
4. **IAM Permissions** to create:
   - CloudFormation stacks
   - IAM roles and policies
   - ECR repositories
   - Lambda functions
   - CodeBuild projects
   - AgentCore resources
   - S3 buckets (for weather agent)

## General Usage Pattern

Each sample follows a consistent structure:

```bash
# Deploy
aws cloudformation create-stack \
  --stack-name <stack-name> \
  --template-body file://<sample-directory>/template.yaml \
  --capabilities CAPABILITY_IAM \
  --region <region>

# Monitor deployment
aws cloudformation describe-stacks \
  --stack-name <stack-name> \
  --region <region>

# Cleanup
aws cloudformation delete-stack \
  --stack-name <stack-name> \
  --region <region>
```

Default values:
- Stack name: Varies by sample (see quick start commands)
- Region: `us-east-1` (or `us-west-2` for weather agent)

## Repository Structure

```
04-cfn-samples/
├── README.md                          # This file
├── mcp-server-agentcore-runtime/     # MCP Server sample
│   ├── deploy.sh                      # Deployment script
│   ├── test.sh                        # Testing script
│   ├── cleanup.sh                     # Cleanup script
│   ├── mcp-server-template.yaml       # CloudFormation template
│   ├── get_token.py                   # Authentication helper
│   ├── test_mcp_server.py             # MCP client test
│   ├── README.md                      # Sample documentation
│   └── DETAILED_GUIDE.md              # Technical deep-dive
├── basic-runtime/                     # Basic agent sample
│   └── template.yaml                  # CloudFormation template
├── multi-agent-runtime/               # Multi-agent sample
│   └── template.yaml                  # CloudFormation template
└── weather-agent-runtime/             # Weather agent sample
    └── template.yaml                  # CloudFormation template
```

## Why CloudFormation?

**Benefits:**
- ✅ **Repeatable** - Deploy identical infrastructure across environments
- ✅ **Version Controlled** - Track infrastructure changes in Git
- ✅ **Automated** - No manual console clicking
- ✅ **Rollback** - Automatic rollback on failures
- ✅ **Cost Tracking** - Tag resources for cost allocation
- ✅ **Best Practices** - Built-in security and monitoring

**vs. Manual Deployment:**
- Manual: 30+ console clicks, error-prone, hard to replicate
- CloudFormation: One command, consistent, auditable

## Cost Optimization

All samples include:
- Cost estimates in their documentation
- Resource tagging for cost tracking
- Cleanup commands to avoid unnecessary charges
- Recommendations for production optimization

**Approximate Monthly Costs:**
- Basic Runtime: ~$50-100
- MCP Server: ~$50-100
- Multi-Agent: ~$100-200
- Weather Agent: ~$100-150

**Note:** Costs vary by region and usage. Delete stacks when not in use.

## Security Best Practices

All templates implement:
- Least-privilege IAM roles
- Encrypted secrets management
- No hardcoded credentials
- VPC support for network isolation
- CloudTrail integration for auditing
- Resource tagging for governance

## Troubleshooting

### Stack Creation Fails

Check CloudFormation events:
```bash
aws cloudformation describe-stack-events \
  --stack-name <stack-name> \
  --region <region>
```

### Permission Issues

Ensure your IAM user/role has:
- `CloudFormationFullAccess` or equivalent
- Permissions to create all resources in the template
- `iam:PassRole` for service roles

### CodeBuild Failures

Check CodeBuild logs:
```bash
aws codebuild batch-get-builds \
  --ids <build-id> \
  --region <region>
```

### Resource Limits

Check AWS service quotas:
```bash
aws service-quotas list-service-quotas \
  --service-code <service-code>
```

## Additional Resources

- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [AWS CloudFormation Documentation](https://docs.aws.amazon.com/cloudformation/)
- [CloudFormation Best Practices](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/best-practices.html)
- [CloudFormation Template Reference](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/AWS_BedrockAgentCore.html)
- [Original Tutorials](../01-tutorials/)

## Contributing

We welcome contributions! To add a new CloudFormation sample:

1. Create a new directory: `<sample-name>/`
2. Include required files:
   - `template.yaml` - CloudFormation template
   - `README.md` - Sample documentation (optional but recommended)
3. Follow the existing pattern and structure
4. Update this README with your sample

See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT-0 License - see the [LICENSE](../LICENSE) file for details.
