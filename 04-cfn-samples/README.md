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

**Quick start:**
```bash
cd mcp-server-agentcore-runtime
./deploy.sh
./test.sh
```


## Prerequisites

Before deploying any CloudFormation template, ensure you have:

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
   ```bash
   aws configure
   ```
