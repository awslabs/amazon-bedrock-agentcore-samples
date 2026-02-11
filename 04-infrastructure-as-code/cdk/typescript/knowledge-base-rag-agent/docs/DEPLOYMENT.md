# Deployment Guide - Bedrock AgentCore Template

This guide provides step-by-step instructions for deploying the Bedrock AgentCore Template.

## Overview

The deployment process consists of four main phases:
1. **Environment Preparation** - Set up prerequisites and configure your environment
2. **Infrastructure Deployment** - Deploy AWS resources using CDK
3. **Knowledge Base Configuration** - Upload documents for RAG
4. **Application Testing** - Validate functionality

**Estimated Time**: 30-45 minutes

## Phase 1: Environment Preparation

### 1.1 Prerequisites Verification

```bash
# Check AWS CLI
aws --version
aws sts get-caller-identity

# Check Node.js (requires 18+)
node --version
npm --version

# Check CDK CLI
cdk --version

# Check Docker (required for AgentCore Runtime container)
docker --version

# Check Python (for agent development)
python3 --version
```

### 1.2 Repository Setup

```bash
# Clone the repository
git clone <repository-url>
cd knowledge-base-rag-agent

# Install dependencies
npm install

# Build web console
npm run build --workspace=web-console
```

### 1.3 Environment Configuration

```bash
# Copy environment template
cp infrastructure/.env.example infrastructure/.env

# Edit the environment file
nano infrastructure/.env
```

**Required Environment Variables:**
```bash
ENVIRONMENT=dev
AWS_REGION=us-east-1
ADMIN_EMAIL=admin@yourdomain.com
```

### 1.4 AWS Account Preparation

```bash
# Bootstrap CDK (first-time setup only)
cd infrastructure
npx cdk bootstrap

# Verify Bedrock model access
aws bedrock list-foundation-models --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `claude-sonnet-4`)].modelId'
```

## Phase 2: Infrastructure Deployment

### 2.1 Pre-Deployment Validation

```bash
cd infrastructure

# Run type checking
npm run build

# Synthesize CloudFormation templates
npm run synth
```

### 2.2 Deploy Infrastructure

```bash
# Deploy all stacks
./scripts/deploy.sh
```

**Deployment Order:**
1. **SharedResourcesStack** - Common resources and Lambda layers
2. **NetworkStack** - VPC and networking (if enabled)
3. **StorageStack** - S3 buckets and KMS keys
4. **CognitoStack** - User authentication
5. **DatabaseStack** - DynamoDB tables
6. **OpenSearchStack** - Vector database
7. **MemoryStack** - AgentCore Memory
8. **RuntimeStack** - AgentCore Runtime
9. **ApiStack** - API Gateway and Lambda
10. **MonitoringStack** - CloudWatch dashboards
11. **WebConsoleStack** - CloudFront and web UI

**Expected Duration:** 15-25 minutes

### 2.3 Verify Deployment

```bash
# Check stack outputs
aws cloudformation describe-stacks \
  --stack-name AgentCoreApiStack \
  --query 'Stacks[0].Outputs'
```

**Key Outputs:**
- `ApiEndpoint` - API Gateway URL
- `WebsiteUrl` - CloudFront URL (from WebConsoleStack)
- `UserPoolId` - Cognito User Pool ID

## Phase 3: Knowledge Base Configuration

### 3.1 Upload Documents

```bash
# Get the knowledge base bucket name
BUCKET_NAME=$(aws ssm get-parameter \
  --name /AgentCoreTemplate/KnowledgeBaseBucket \
  --query 'Parameter.Value' --output text)

# Upload example documents
aws s3 cp docs/knowledge-base-examples/ s3://$BUCKET_NAME/ --recursive

# Verify upload
aws s3 ls s3://$BUCKET_NAME/
```

### 3.2 Supported Document Formats

- PDF files (`.pdf`)
- Text files (`.txt`)
- Markdown files (`.md`)
- Word documents (`.docx`)
- HTML files (`.html`)

## Phase 4: Application Testing

### 4.1 Access Web Interface

```bash
# Get CloudFront URL
WEB_URL=$(aws ssm get-parameter \
  --name /AgentCoreTemplate/WebsiteUrl \
  --query 'Parameter.Value' --output text 2>/dev/null || \
  aws cloudformation describe-stacks \
  --stack-name AgentCoreWebConsoleStack \
  --query 'Stacks[0].Outputs[?OutputKey==`WebsiteUrl`].OutputValue' \
  --output text)

echo "Web Interface URL: $WEB_URL"
```

### 4.2 Create Test User

1. Open the CloudFront URL in your browser
2. Click "Sign Up" to create a new account
3. Verify your email address
4. Log in to the application

### 4.3 Test Agent Functionality

**Test Scenarios:**
1. "Hello, how can you help me?"
2. "What is Amazon Bedrock?"
3. "Tell me about the documents you have access to"

### 4.4 API Testing

```bash
# Get API URL
API_URL=$(aws ssm get-parameter \
  --name /AgentCoreTemplate/ApiEndpoint \
  --query 'Parameter.Value' --output text)

# Test health endpoint (no auth required)
curl -X GET "$API_URL/health"
```

## Troubleshooting

### Common Issues

**CDK Bootstrap Required:**
```bash
npx cdk bootstrap aws://ACCOUNT-ID/REGION
```

**Bedrock Model Access Denied:**
1. Go to Amazon Bedrock console
2. Navigate to "Model access"
3. Request access to Claude Sonnet 4

**Docker Not Running:**
```bash
# Docker is required for building the AgentCore Runtime container
# Start Docker and verify
docker info
```

**AgentCore Runtime Not Starting:**
```bash
# Check CloudWatch logs
aws logs tail /aws/bedrock-agentcore/runtime --follow
```

### Getting Help

1. Check CloudWatch Logs for detailed error information
2. Review CloudFormation Events for deployment issues
3. Verify all prerequisites are properly configured
4. Check AWS service quotas

## Cleanup

To remove all deployed resources:

```bash
cd infrastructure
npx cdk destroy --all
```

**Note:** This will delete all data including:
- Knowledge base documents
- Conversation history
- User accounts

## Next Steps

After successful deployment:

1. **Customize Agent** - Modify `infrastructure/agent/src/agent.py`
2. **Add Tools** - Create new tools in `infrastructure/agent/src/tools/`
3. **Upload Content** - Add your documents to the knowledge base
4. **Configure Memory** - Adjust memory strategies in `agentcore-memory-stack.ts`
5. **Brand Web UI** - Customize the web interface in `web-console/`

## Security Validation

After deployment, validate security controls:

```bash
# Verify S3 encryption
aws s3api get-bucket-encryption --bucket $BUCKET_NAME

# Check IAM roles
aws iam list-roles --query 'Roles[?contains(RoleName, `AgentCore`)].RoleName'

# Test unauthenticated access (should return 401)
curl -X POST $API_URL/chat/invoke \
  -H "Content-Type: application/json" \
  -d '{"message":"test"}'
```

For detailed security information, see [SECURITY.md](SECURITY.md).

---

*This guide provides the essential steps for deploying the Bedrock AgentCore Template. For detailed architecture information, see [ARCHITECTURE.md](ARCHITECTURE.md).*
