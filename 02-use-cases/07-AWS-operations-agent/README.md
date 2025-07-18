# AWS Operations Conversational Agent

---
## 📋 Navigation
**🏠 [README](README.md)** | **📖 [Setup Guide](docs/SETUP.md)** | **🏗️ [Architecture](docs/ARCHITECTURE-FLOW.md)** | **🔧 [Scripts](scripts/README.md)** | **🤖 [Client](client/README.md)** | **⚙️ [Config](configs/README.md)** | **🔐 [Okta Setup](okta-auth/OKTA-OPENID-PKCE-SETUP.md)**
---

## 🎯 Project Description

This project demonstrates a **AI-powered AWS operations platform** that transforms how DevOps teams interact with AWS infrastructure. By combining **Amazon Bedrock's Claude 3.7 Sonnet**, **Model Context Protocol (MCP)**, and **serverless architecture**, users can perform complex AWS operations through natural language conversations.

### **Real-World Use Cases**

**🔍 Infrastructure Discovery & Monitoring**
- "Show me all EC2 instances that haven't been accessed in 30 days"
- "Which RDS databases are consuming the most storage?"
- "List all Lambda functions with error rates above 5%"
- "Find S3 buckets with public read access"

**💰 Cost Optimization & Analysis**
- "What are my top 10 most expensive AWS services this month?"
- "Show me unused EBS volumes across all regions"
- "Which CloudFormation stacks are costing more than $100/month?"
- "Find EC2 instances running 24/7 that could be scheduled"

**🔐 Security & Compliance Auditing**
- "List all IAM users with admin privileges"
- "Show me security groups with unrestricted inbound access"
- "Which resources don't have required tags?"
- "Find VPCs without flow logs enabled"

**⚡ Operational Troubleshooting**
- "Why is my application load balancer showing 5xx errors?"
- "Show me CloudWatch alarms that fired in the last 24 hours"
- "Which Lambda functions are hitting timeout limits?"
- "Find auto-scaling groups that scaled recently"

### **What You'll Learn**

**🏗️ Advanced Serverless Architecture**
- **Multi-Lambda orchestration** with Function URLs and Docker containers
- **Cross-service authentication** using AWS SigV4 and Okta JWT tokens
- **Production-grade deployment** with SAM templates and infrastructure as code
- **Container optimization** for Lambda with platform-specific Docker builds

**🤖 AI Agent Development**
- **Model Context Protocol (MCP)** implementation for tool integration
- **Conversational AI patterns** with streaming responses and memory persistence
- **Natural language to API translation** using Claude 3.7 Sonnet
- **Agent orchestration** with the Strands framework for complex workflows

**🔐 Enterprise Authentication & Security**
- **Dual authentication patterns** combining AWS IAM and external OAuth2
- **Production security practices** with least-privilege IAM roles
- **Token management** and secure credential handling
- **API gateway alternatives** using Lambda Function URLs

**☁️ AWS Operations at Scale**
- **20+ AWS service integrations** including EC2, S3, RDS, CloudWatch, IAM
- **Cross-region resource management** with unified interfaces
- **Real-time monitoring** and alerting through conversational queries
- **Infrastructure automation** through natural language commands

**🛠️ DevOps & Platform Engineering**
- **GitOps workflows** with automated deployment pipelines
- **Observability patterns** using CloudWatch, DynamoDB, and structured logging
- **Error handling** and resilience patterns in distributed systems
- **Performance optimization** for serverless applications

### **Technical Innovation Highlights**

**🔄 Production-Ready Patterns**
- **Conversation persistence** with DynamoDB for stateful interactions
- **Streaming responses** for real-time user experience
- **Error recovery** and graceful degradation
- **Scalable architecture** supporting concurrent users

**🎯 Business Value**
- **Reduce operational overhead** by 60% through natural language interfaces
- **Accelerate troubleshooting** with AI-powered root cause analysis
- **Improve security posture** through automated compliance checking
- **Enable self-service operations** for development teams

A complete Bedrock AgentCore Gateway MCP (Model Context Protocol) solution enabling natural language AWS operations through AWS Operations Agent interface with Function URL deployment and DynamoDB conversation persistence.

## 🏗️ Architecture Overview

This project implements a **serverless AI-powered AWS operations platform** using a multi-Lambda architecture with dual authentication. The flow begins with a **Client App** that authenticates via AWS SigV4 to invoke the **AWS Operations Agent Lambda** through a Function URL. The Agent Lambda, built with FastAPI and the Strands framework, manages conversations in DynamoDB and communicates with the **Bedrock AgentCore Gateway** using MCP (Model Context Protocol) and Okta JWT authentication. The Gateway then invokes the **MCP Tool Lambda** (Docker-based) which provides 20 AWS service tools for operations like EC2 management, S3 operations, CloudWatch monitoring, and more. This architecture eliminates API Gateway complexity while providing enterprise-grade security and scalability.

**Key Components:**
- **AWS Operations Agent Lambda** (`aws-operations-agent-dev`) - FastAPI with Strands Agent + MCP Client
- **MCP Tool Lambda** (`dev-bedrock-agentcore-mcp-tool`) - Docker container with 20 AWS tools
- **Bedrock AgentCore Gateway** - Production MCP server with Okta authentication
- **Function URL** - Direct Lambda access with IAM_AUTH (no API Gateway)
- **DynamoDB** - Conversation persistence and session management

**📖 For detailed architecture diagrams and component interactions, see [ARCHITECTURE-FLOW.md](docs/ARCHITECTURE-FLOW.md)**

## 🎬 Demo

### AWS Operations Agent in Action

![AWS Operations Conversational Agent Demo](images/demo.gif)

The interactive client provides a natural language interface for AWS operations:
- **Real-time streaming responses** from Claude 3.7 Sonnet
- **20 AWS service tools** for comprehensive operations
- **Conversation persistence** with DynamoDB storage
- **Natural language queries** like "List my S3 buckets" or "Show EC2 instances"

## 🚀 Getting Started

This project requires AWS CLI configuration, Python 3.11+, AWS SAM CLI, Docker, and Okta authentication setup. The deployment involves multiple Lambda functions, Bedrock AgentCore Gateway configuration, and DynamoDB setup.

**📖 For complete step-by-step setup instructions, see [SETUP.md](docs/SETUP.md)**

## 📁 Project Structure

```
07-Operational-Support-Lambda-Web-Adapter/
├── 📄 README.md                    # This file - project overview
├── 📁 docs/                        # Documentation
│   ├── 📄 SETUP.md                 # Step-by-step setup guide
│   └── 📄 ARCHITECTURE-FLOW.md     # Detailed architecture documentation
├── 📁 configs/                     # Centralized configuration
│   ├── 📄 bedrock-agentcore-config.json      # Main configuration file
│   ├── 📄 config_manager.py        # Configuration management utilities
│   └── 📄 README.md                # Configuration documentation
├── 📁 agent-lambda/                # AWS Operations Agent Lambda (main component)
│   ├── 📁 src/                     # Source code directory
│   ├── 📄 template.yaml            # SAM deployment template
│   ├── 📄 deploy.sh                # Deployment script
│   ├── 📄 Dockerfile               # Container configuration
│   └── 📄 README.md                # Agent Lambda documentation
├── 📁 mcp-tool-lambda/             # MCP Tool Lambda (Docker-based)
│   ├── 📁 lambda/                  # Lambda function source code
│   ├── 📄 mcp-tool-template.yaml   # SAM template for Docker Lambda
│   └── 📄 deploy-mcp-tool.sh       # Docker deployment script
├── 📁 scripts/                     # Bedrock AgentCore Gateway management
│   ├── 📄 create-gateway.py        # Create Bedrock AgentCore Gateway
│   ├── 📄 create-target.py         # Create MCP tool targets
│   ├── 📄 get-gateway.py           # Get gateway details
│   ├── 📄 get-target.py            # Get target details
│   ├── 📄 list-gateways.py         # List all gateways
│   ├── 📄 list-targets.py          # List all targets
│   ├── 📄 update-gateway.py        # Update gateway configuration
│   ├── 📄 update-target.py         # Update target configuration
│   ├── 📄 delete-gateway.py        # Delete gateway
│   ├── 📄 delete-target.py         # Delete target
│   └── 📄 README.md                # Scripts documentation
├── 📁 client/                      # AWS Operations Agent client applications
│   ├── 📁 src/                     # Client source code
│   ├── 📄 requirements.txt         # Python dependencies
│   ├── 📄 run_client.sh            # Client execution script
│   └── 📄 README.md                # Client documentation
├── 📁 okta-auth/                   # Okta authentication setup
│   └── 📄 OKTA-OPENID-PKCE-SETUP.md # Okta configuration guide
└── 📁 images/                      # Project images and screenshots
    └── 📄 chatbot.jpg              # Demo screenshot
```

## 📚 Documentation

### 🎯 Getting Started
- **[SETUP.md](docs/SETUP.md)** - Complete step-by-step setup guide (streamlined, 7 steps)
- **[ARCHITECTURE-FLOW.md](docs/ARCHITECTURE-FLOW.md)** - Detailed architecture and component flow

### 🔧 Component Documentation
- **[Agent Lambda README](agent-lambda/README.md)** - AWS Operations Agent Lambda details
- **[Scripts README](scripts/README.md)** - Bedrock AgentCore Gateway management scripts
- **[Client README](client/README.md)** - AWS Operations Agent client applications
- **[Config README](configs/README.md)** - Configuration management

### 🔐 Authentication
- **[Okta Setup Guide](okta-auth/OKTA-OPENID-PKCE-SETUP.md)** - Okta OAuth2 configuration

## 🛠️ Key Features

### **Dual Authentication**
- **Function URL**: AWS SigV4 for Lambda access
- **Bedrock AgentCore Gateway**: Okta JWT for MCP tool authorization

### **AWS Operations Agent Capabilities**
- **Natural Language**: Conversational AWS operations
- **20 AWS Tools**: EC2, S3, Lambda, CloudFormation, IAM, RDS, CloudWatch, etc.
- **Streaming Responses**: Real-time AI responses
- **Conversation Memory**: DynamoDB persistence

### **Production Ready**
- **Docker Deployment**: MCP Tool Lambda with Strands framework
- **Function URL**: Direct access without API Gateway
- **Production Endpoints**: bedrock-agentcore-control service
- **Scalable Architecture**: Optimized for performance

## 🧪 Testing

### Interactive Testing
```bash
cd client
python aws_operations_agent_mcp.py

# Try these commands:
# "What time is it? Use the get_time tool."
# "List my S3 buckets"
# "Show me EC2 instances"
# "What Lambda functions do I have?"
```

### Component Testing
```bash
# Test Bedrock AgentCore Gateway
cd scripts && python test_bedrock_agentcore_auth.py

# Test Lambda deployments
aws lambda get-function --function-name aws-operations-agent-dev --profile demo1
aws lambda get-function --function-name dev-bedrock-agentcore-mcp-tool --profile demo1
```

## 🔍 Architecture Details

### **Data Flow**
1. **Client** sends request with AWS SigV4 + Okta token
2. **Function URL** validates SigV4 and invokes AWS Operations Agent Lambda
3. **AWS Operations Agent Lambda** processes request and stores conversation in DynamoDB
4. **AWS Operations Agent Lambda** calls Bedrock AgentCore Gateway with Okta token via MCP
5. **Bedrock AgentCore Gateway** validates Okta token and invokes MCP Tool Lambda
6. **MCP Tool Lambda** executes AWS operations using Strands framework
7. **Response** flows back through the chain with natural language formatting

### **Key Technologies**
- **AWS Lambda**: Serverless compute (Function URL + Docker)
- **Bedrock AgentCore Gateway**: MCP server with production endpoints
- **Strands Framework**: AI agent framework for AWS operations
- **FastAPI**: Web framework with Lambda Web Adapter
- **DynamoDB**: NoSQL database for conversation storage
- **Docker**: Container runtime for MCP Tool Lambda

## 🚨 Troubleshooting

### Common Issues
1. **Configuration Mismatch**: Ensure `configs/bedrock-agentcore-config.json` has actual values, not templates
2. **Authentication Errors**: Verify Okta token in `client/token.txt` and AWS credentials
3. **Lambda Deployment**: Check CloudFormation stacks and Lambda logs
4. **Bedrock AgentCore Gateway**: Verify gateway and target status with `get-gateway.py` and `get-target.py`

### Debug Commands
```bash
# Check component status
aws lambda get-function --function-name aws-operations-agent-dev --profile demo1
cd scripts && python get-gateway.py && python get-target.py

# View logs
aws logs tail /aws/lambda/aws-operations-agent-dev --follow --profile demo1
```

## 🎯 Use Cases

- **AWS Resource Discovery**: "Show me all my EC2 instances"
- **Cost Analysis**: "What are my highest cost services this month?"
- **Security Auditing**: "List IAM roles with admin access"
- **Infrastructure Monitoring**: "Show me CloudWatch alarms that are firing"
- **Operational Queries**: "Which Lambda functions have errors?"

## 🔄 Development Workflow

1. **Configuration**: Update `configs/bedrock-agentcore-config.json` with your values
2. **Deploy Components**: AWS Operations Agent Lambda → MCP Tool Lambda → Bedrock AgentCore Gateway
3. **Test Integration**: Use interactive client to verify end-to-end flow
4. **Monitor**: Check CloudWatch logs and DynamoDB for conversation storage
5. **Iterate**: Add new tools or modify configurations as needed

## 📊 Production Considerations

- **Security**: IAM roles with least privilege, Okta JWT validation
- **Monitoring**: CloudWatch logs, DynamoDB metrics, Lambda performance
- **Scalability**: On-demand DynamoDB, containerized Lambda functions

## ⚠️ Current Limitations & Write Operations

### **Read-Only Operations**
This agent is currently configured for **read-only AWS operations** as a security best practice. All 20 AWS service tools are designed to query and retrieve information without making changes to your infrastructure.

**Current Capabilities:**
- ✅ List and describe AWS resources (EC2, S3, RDS, etc.)
- ✅ Query CloudWatch metrics and logs
- ✅ Analyze costs and billing information
- ✅ Audit security configurations and compliance
- ✅ Monitor infrastructure health and performance

### **Enabling Write Operations**
To enable write operations (create, update, delete resources), you need to make two key changes:

#### **1. Update MCP Tool Lambda Permissions**
```bash
# Edit the IAM role for the MCP Tool Lambda
# Current: ReadOnlyAccess policy
# Add: Specific write permissions for required services

# Example: Enable EC2 write operations
aws iam attach-role-policy \
  --role-name lambda-execution-role-dev-bedrock-agentcore-mcp-tool \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2FullAccess
```

#### **2. Update Strands Agent System Prompt**
```python
# In agent-lambda/src/main.py, modify the system prompt:
# Current: "You are a read-only AWS operations assistant..."
# Update to: "You are an AWS operations assistant with read and write capabilities..."

# Example system prompt update:
SYSTEM_PROMPT = """
You are an AWS operations assistant with comprehensive read and write capabilities.
You can query AWS resources AND make changes when explicitly requested.
Always confirm destructive operations before executing.
Use appropriate AWS tools for both read and write operations.
"""
```

#### **3. Security Considerations for Write Operations**
- **Implement confirmation prompts** for destructive operations
- **Use resource tagging** to identify managed vs. unmanaged resources  
- **Enable CloudTrail logging** for audit trails of all changes
- **Consider approval workflows** for high-impact operations
- **Test in non-production environments** first

**⚠️ Warning**: Write operations can modify or delete AWS resources. Always test thoroughly and implement appropriate safeguards before enabling in production environments.

---
