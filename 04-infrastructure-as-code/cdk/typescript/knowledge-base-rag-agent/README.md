# Knowledge Base RAG Agent

An AWS CDK template for deploying AI agents using Amazon Bedrock AgentCore with Knowledge Base integration and web interface. This template demonstrates production-ready patterns for building conversational AI applications.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Quick Start](#quick-start)
- [Managing the Knowledge Base](#managing-the-knowledge-base)
- [Testing Your Deployment](#testing-your-deployment)
- [Customization](#customization)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [Cost Estimation](#cost-estimation)
- [Additional Resources](#additional-resources)

## Architecture Overview

This solution deploys a complete conversational AI system using Amazon Bedrock AgentCore:

- **AgentCore Runtime** - Containerized AI agent with Claude Sonnet 4
- **AgentCore Memory** - Short-term and long-term memory for conversation context
- **Knowledge Base** - OpenSearch Serverless for vector storage and RAG
- **REST API** - API Gateway with Lambda integration and Cognito authentication
- **Web Interface** - Next.js chat interface with CloudFront distribution
- **Document Storage** - S3 bucket for knowledge base content

**Key Features:**
- 🤖 Framework-agnostic AI agent (Strands SDK)
- 🧠 Persistent memory with semantic extraction
- 📚 Vector search using OpenSearch Serverless
- 🌐 Clean web interface for testing
- 🔒 Comprehensive security controls
- 🚀 One-command deployment
- 📖 Educational code with detailed comments

## Quick Start

### Prerequisites

- AWS Account with Bedrock access
- AWS CLI configured
- Node.js 24.8.0+ and npm 10.0.0+
- CDK CLI installed (`npm install -g aws-cdk`)
- Docker installed and running (required for building the AgentCore Runtime container)
- Python 3.12+ (for agent development)

### Deployment

1. **Clone and check prerequisites**:

   ```bash
   git clone <repository-url>
   cd knowledge-base-rag-agent
   
   # Check all prerequisites are installed
   ./scripts/check-prerequisites.sh
   ```

2. **Install dependencies and build**:

   ```bash
   npm install  # Installs all dependencies
   npm run build --workspace=web-console  # Build web interface
   ```

3. **Deploy infrastructure**:

   ```bash
   ./scripts/deploy.sh  # Checks prerequisites and deploys all stacks
   ```

4. **Access the application**:
   - Web interface available at the CloudFront URL from deployment output
   - Admin credentials stored in AWS Secrets Manager (see deployment output)

## Managing the Knowledge Base

After deployment, upload documents to the knowledge base for the agent to reference.

### Quick Upload with Script (Recommended)

```bash
# Upload example documents and wait for sync to complete
./scripts/upload-documents.sh --examples --wait

# Or upload your own documents
./scripts/upload-documents.sh your-documents/ --wait

# Just trigger sync without uploading new documents
./scripts/upload-documents.sh --sync-only
```

### Manual Upload (Alternative)

```bash
# Get the knowledge base bucket name
BUCKET_NAME=$(aws ssm get-parameter \
  --name /AgentCoreTemplate/KnowledgeBaseBucket \
  --query 'Parameter.Value' --output text)

# Upload documents (PDF, TXT, MD, DOCX, HTML)
aws s3 cp your-documents/ s3://$BUCKET_NAME/ --recursive
```

For more details, see [Knowledge Base Examples](docs/knowledge-base-examples/README.md).

## Testing Your Deployment

### Using the Web Interface

1. Open the CloudFront URL provided after deployment
2. Log in with the credentials from deployment output
3. Ask questions like:
   - "What is Amazon Bedrock?"
   - "How do I use the AI assistant?"
   - "What are best practices for agents?"

### Using the API

```bash
# Get API endpoint
API_URL=$(aws ssm get-parameter \
  --name /AgentCoreTemplate/ApiEndpoint \
  --query 'Parameter.Value' --output text)

# Health check (no auth required)
curl $API_URL/health

# Chat with the agent (requires authentication)
curl -X POST $API_URL/chat/invoke \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "message": "What is Amazon Bedrock?",
    "sessionId": "test-session-123"
  }'
```

For detailed API examples, see [API Usage Guide](docs/API_USAGE.md).

## Project Structure

```
knowledge-base-rag-agent/
├── README.md                    # This file
├── docs/                        # Documentation
│   ├── knowledge-base-examples/ # Sample documents for testing
│   └── *.md                    # API usage, security, configuration guides
├── infrastructure/             # CDK infrastructure code
│   ├── lib/stacks/            # CDK stacks (AgentCore, API, Web, etc.)
│   ├── agent/                 # Python agent code (Strands SDK)
│   ├── src/functions/         # Lambda function code
│   └── bin/                   # CDK app entry point
├── web-console/               # Next.js web interface
└── scripts/                   # Deployment and utility scripts
```

## AgentCore Architecture

The template uses Amazon Bedrock AgentCore for agent deployment:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web Console                               │
│                    (CloudFront + S3)                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway                                 │
│                   (REST API + Cognito)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AgentCore Runtime                              │
│              (Containerized Strands Agent)                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  • Claude Sonnet 4 (via Bedrock)                        │   │
│  │  • RAG via OpenSearch Serverless                        │   │
│  │  • Session isolation per user                           │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ AgentCore Memory│ │    OpenSearch   │ │   S3 Documents  │
│  (STM + LTM)    │ │   Serverless    │ │  (Knowledge)    │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

## Cost Estimation

Estimated monthly costs for development/demo usage:

- **AgentCore Runtime**: ~$20-80 (based on usage)
- **AgentCore Memory**: ~$5-20
- **OpenSearch Serverless**: ~$50-150
- **Lambda**: ~$1-5
- **API Gateway**: ~$1-10
- **S3**: ~$1-5

**Total**: ~$78-270/month

Use the [AWS Pricing Calculator](https://calculator.aws) for detailed estimates.

## Security

This template implements comprehensive security controls following AWS best practices:

- ✅ **Authentication & Authorization** - Cognito User Pool with API Gateway authorizers
- ✅ **Encryption** - At rest (S3, OpenSearch, DynamoDB) and in transit (HTTPS/TLS 1.2+)
- ✅ **Network Security** - S3 public access blocked, CloudFront OAC
- ✅ **IAM Least Privilege** - All roles scoped to minimum required permissions
- ✅ **Session Isolation** - AgentCore Runtime provides per-user session isolation
- ✅ **Audit Logging** - CloudWatch logs for all services
- ✅ **No Hardcoded Secrets** - All credentials managed by AWS services

### Known Dependency Vulnerabilities

The web console has known vulnerabilities in transitive dependencies from `aws-amplify` and `@aws-amplify/ui-react`:

- **fast-xml-parser** (high) - DoS vulnerability in AWS SDK v3, awaiting upstream fix
- **lodash** (moderate) - Prototype pollution in @aws-amplify/ui

These are upstream issues that will be resolved when AWS Amplify updates their dependencies. The vulnerabilities are DoS-related (not RCE) and affect server-side XML parsing which is not directly exposed in this application.

For detailed security information, see [Security Documentation](docs/SECURITY.md).

## Customization

This template is designed for easy customization:

1. **Agent Instructions** - Modify `infrastructure/agent/src/agent.py`
2. **Model Selection** - Change the `modelId` in stack props (see [Model Configuration](docs/MODEL_CONFIGURATION.md))
3. **Agent Tools** - Add new tools in `infrastructure/agent/src/tools/`
4. **Memory Strategies** - Configure in `agentcore-memory-stack.ts`
5. **Knowledge Base Content** - Upload documents to the S3 bucket
6. **Web Interface** - Customize React components in `web-console/`
7. **API Endpoints** - Add new routes in the API Gateway stack

## Troubleshooting

### Common Issues

**Docker Not Running**
```bash
# Docker is required for building the AgentCore Runtime container
# Start Docker and verify it's running
docker info
```

**Bedrock Model Not Found**
- Verify Bedrock is available in your region
- Check AWS Console → Amazon Bedrock → Model catalog
- The template uses cross-region inference profiles

**CDK Bootstrap Required**
```bash
npx cdk bootstrap aws://ACCOUNT-ID/REGION
```

**Agent Not Responding**
- Check CloudWatch logs: `/aws/lambda/AgentCoreApi-Chat`
- Verify AgentCore Runtime status in Bedrock console
- Ensure documents are uploaded to knowledge base S3 bucket

For detailed troubleshooting, see [Troubleshooting Guide](docs/TROUBLESHOOTING.md).

## Additional Resources

- 📖 **[API Usage Guide](docs/API_USAGE.md)** - Programmatic access examples
- 🤖 **[Model Configuration Guide](docs/MODEL_CONFIGURATION.md)** - Foundation models and inference profiles
- 📚 **[Knowledge Base Examples](docs/knowledge-base-examples/)** - Sample documents for testing
- 🏗️ **[Architecture Guide](docs/ARCHITECTURE.md)** - Detailed technical architecture
- 🚀 **[Deployment Guide](docs/DEPLOYMENT.md)** - Step-by-step deployment instructions
- 🔧 **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- 🔒 **[Security Guide](docs/SECURITY.md)** - Security best practices and validation

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
