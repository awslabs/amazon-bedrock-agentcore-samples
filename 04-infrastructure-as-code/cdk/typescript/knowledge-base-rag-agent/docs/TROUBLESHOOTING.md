# Troubleshooting Guide - Bedrock AgentCore Template

This guide provides solutions to common issues encountered during deployment and operation of the Bedrock AgentCore Template. Issues are organized by deployment phase and include specific error messages, root causes, and step-by-step solutions.

## Quick Diagnostic Commands

Before diving into specific issues, run these commands to gather diagnostic information:

```bash
# Check AWS credentials and region
aws sts get-caller-identity
aws configure get region

# Verify CDK installation and bootstrap status
cdk --version
cdk ls

# Check stack status
aws cloudformation describe-stacks --query 'Stacks[?contains(StackName, `knowledge-base-rag`)].{Name:StackName,Status:StackStatus}' --output table

# View recent CloudFormation events
aws cloudformation describe-stack-events --stack-name knowledge-base-rag-agent-api-dev --max-items 10
```

## Phase 1: Environment Preparation Issues

### Issue: AWS CLI Not Configured
**Error Message:** `Unable to locate credentials`
**Symptoms:** AWS commands fail with authentication errors

**Solution:**
```bash
# Configure AWS CLI with your credentials
aws configure

# Or use environment variables
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_DEFAULT_REGION=us-east-1

# Verify configuration
aws sts get-caller-identity
```

### Issue: CDK Bootstrap Required
**Error Message:** `This stack uses assets, so the toolkit stack must be deployed to the environment`
**Symptoms:** CDK deployment fails before creating any resources

**Solution:**
```bash
# Bootstrap CDK in your account and region
cd infrastructure
npx cdk bootstrap

# If using a specific profile
npx cdk bootstrap --profile your-profile-name

# Verify bootstrap stack exists
aws cloudformation describe-stacks --stack-name CDKToolkit
```

### Issue: Node.js Version Incompatibility
**Error Message:** `Node.js version X.X.X is not supported`
**Symptoms:** npm install fails or CDK commands don't work

**Solution:**
```bash
# Check current Node.js version
node --version

# Install Node.js 18+ using nvm (recommended)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 18
nvm use 18

# Or download from nodejs.org
# Verify installation
node --version  # Should show 18.x.x or higher
```

### Issue: Missing Environment Variables
**Error Message:** `Environment variable X is not defined`
**Symptoms:** CDK synthesis or deployment fails

**Solution:**
```bash
# Copy and edit environment file
cp infrastructure/.env.example infrastructure/.env

# Edit with required values
nano infrastructure/.env

# Required variables:
ENVIRONMENT=dev
AWS_REGION=us-east-1
ADMIN_EMAIL=your-email@domain.com
COGNITO_DOMAIN_PREFIX=unique-prefix-12345

# Verify environment file
cat infrastructure/.env
```

## Phase 2: Infrastructure Deployment Issues

### Issue: Bedrock Model Access Denied
**Error Message:** `AccessDeniedException: You don't have access to the model`
**Symptoms:** Bedrock stack deployment fails

**Solution:**
1. **Request Model Access:**
   - Go to Amazon Bedrock console
   - Navigate to "Model access" in left sidebar
   - Click "Request model access"
   - Select "Claude Sonnet 4" and submit request
   - Wait for approval (usually immediate)

2. **Verify Access:**
```bash
# Check available models
aws bedrock list-foundation-models --region us-east-1 --query 'modelSummaries[?contains(modelId, `claude-sonnet-4`)].modelId'

# Should return: ["anthropic.claude-sonnet-4-20250514-v1:0"]
```

### Issue: OpenSearch Serverless Quota Exceeded
**Error Message:** `LimitExceededException: Account limit exceeded for collections`
**Symptoms:** OpenSearch stack deployment fails

**Solution:**
```bash
# Check current collections
aws opensearchserverless list-collections

# Delete unused collections if at limit
aws opensearchserverless delete-collection --id collection-id

# Or request quota increase through AWS Support
```

### Issue: CloudFormation Stack Rollback
**Error Message:** `Stack is in ROLLBACK_COMPLETE state`
**Symptoms:** Deployment fails and stack rolls back

**Solution:**
```bash
# Check stack events for root cause
aws cloudformation describe-stack-events --stack-name failed-stack-name --max-items 20

# Delete failed stack and retry
aws cloudformation delete-stack --stack-name failed-stack-name

# Wait for deletion to complete
aws cloudformation wait stack-delete-complete --stack-name failed-stack-name

# Retry deployment
./scripts/deploy.sh dev
```

### Issue: IAM Permission Denied
**Error Message:** `User: arn:aws:iam::account:user/username is not authorized to perform: action`
**Symptoms:** CDK deployment fails with permission errors

**Solution:**
1. **Attach Required Policies:**
   - `AdministratorAccess` (for development)
   - Or specific policies for production:
     - `IAMFullAccess`
     - `CloudFormationFullAccess`
     - `S3FullAccess`
     - `LambdaFullAccess`
     - Custom policy for Bedrock and OpenSearch

2. **Verify Permissions:**
```bash
# Check current user permissions
aws iam get-user
aws iam list-attached-user-policies --user-name your-username
```

### Issue: Resource Name Conflicts
**Error Message:** `AlreadyExistsException: Resource already exists`
**Symptoms:** Stack deployment fails due to naming conflicts

**Solution:**
```bash
# Update environment variables with unique values
nano infrastructure/.env

# Change these to unique values:
COGNITO_DOMAIN_PREFIX=bedrock-agent-unique-12345
PROJECT_NAME=knowledge-base-rag-agent-unique

# Redeploy with new names
./scripts/deploy.sh dev
```

## Phase 3: Knowledge Base Configuration Issues

### Issue: Knowledge Base Ingestion Fails
**Error Message:** `IngestionJob status: FAILED`
**Symptoms:** Documents not appearing in knowledge base

**Solution:**
```bash
# Get ingestion job details
KB_ID=$(aws cloudformation describe-stacks \
  --stack-name knowledge-base-rag-agent-bedrock-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseId`].OutputValue' \
  --output text)

# Check ingestion job status
aws bedrock-agent list-ingestion-jobs --knowledge-base-id $KB_ID

# Common fixes:
# 1. Check document formats (only PDF, TXT, MD, DOCX supported)
# 2. Verify file sizes (< 50MB per file)
# 3. Check S3 bucket permissions
# 4. Ensure documents contain readable text
```

### Issue: No Documents in S3 Bucket
**Error Message:** `No objects found in bucket`
**Symptoms:** Knowledge base has no content to ingest

**Solution:**
```bash
# Get bucket name
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name knowledge-base-rag-agent-bedrock-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseBucket`].OutputValue' \
  --output text)

# Upload example documents
aws s3 cp docs/knowledge-base-examples/ s3://$BUCKET_NAME/ --recursive --exclude "README.md"

# Verify upload
aws s3 ls s3://$BUCKET_NAME/

# Trigger new ingestion
DATA_SOURCE_ID=$(aws bedrock-agent list-data-sources \
  --knowledge-base-id $KB_ID \
  --query 'dataSourceSummaries[0].dataSourceId' \
  --output text)

aws bedrock-agent start-ingestion-job \
  --knowledge-base-id $KB_ID \
  --data-source-id $DATA_SOURCE_ID
```

### Issue: Knowledge Base Returns No Results
**Error Message:** `No relevant documents found`
**Symptoms:** Agent cannot find information from uploaded documents

**Solution:**
1. **Verify Ingestion Completed:**
```bash
# Check ingestion job status
aws bedrock-agent list-ingestion-jobs --knowledge-base-id $KB_ID

# Status should be "COMPLETE"
```

2. **Test Knowledge Base Directly:**
```bash
# Test retrieval
aws bedrock-agent-runtime retrieve \
  --knowledge-base-id $KB_ID \
  --retrieval-query text="test query" \
  --retrieval-configuration 'vectorSearchConfiguration={numberOfResults=5}'
```

3. **Check Document Content:**
   - Ensure documents contain searchable text
   - Verify documents are in supported formats
   - Check that document content matches your queries

## Phase 4: Application Testing Issues

### Issue: Web Interface Not Loading
**Error Message:** `403 Forbidden` or `404 Not Found`
**Symptoms:** CloudFront URL returns errors

**Solution:**
```bash
# Check CloudFront distribution status
aws cloudfront list-distributions \
  --query 'DistributionList.Items[?contains(Comment, `bedrock-agent`)].{Id:Id,Status:Status,DomainName:DomainName}'

# Status should be "Deployed" (can take 10-15 minutes)

# Check S3 bucket policy
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name knowledge-base-rag-agent-web-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`WebsiteBucket`].OutputValue' \
  --output text)

aws s3api get-bucket-policy --bucket $BUCKET_NAME
```

### Issue: User Registration Fails
**Error Message:** `InvalidParameterException: Invalid email address format`
**Symptoms:** Cannot create user accounts

**Solution:**
```bash
# Check Cognito User Pool configuration
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name knowledge-base-rag-agent-api-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
  --output text)

# Verify email configuration
aws cognito-idp describe-user-pool --user-pool-id $USER_POOL_ID

# Common fixes:
# 1. Use valid email format (user@domain.com)
# 2. Check email verification settings
# 3. Verify SES configuration if using custom email
```

### Issue: API Gateway Timeout
**Error Message:** `504 Gateway Timeout`
**Symptoms:** API requests take too long or fail

**Solution:**
```bash
# Check Lambda function logs
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/bedrock-agent"

# View recent errors
aws logs filter-log-events \
  --log-group-name "/aws/lambda/bedrock-agent-chat-dev" \
  --start-time $(date -d '1 hour ago' +%s)000

# Common fixes:
# 1. Increase Lambda timeout (default: 30 seconds)
# 2. Increase Lambda memory allocation
# 3. Check Bedrock service quotas
# 4. Verify network connectivity
```

### Issue: Agent Responses Are Slow
**Error Message:** No error, but responses take > 30 seconds
**Symptoms:** Long wait times for agent responses

**Solution:**
1. **Check Bedrock Quotas:**
```bash
# View service quotas
aws service-quotas list-service-quotas --service-code bedrock
```

2. **Optimize Lambda Configuration:**
   - Increase memory allocation (more memory = faster CPU)
   - Enable provisioned concurrency for consistent performance
   - Optimize knowledge base queries

3. **Monitor Performance:**
```bash
# Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=bedrock-agent-chat-dev \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average
```

## Phase 5: Production Issues

### Issue: High Costs
**Symptoms:** Unexpected AWS charges

**Solution:**
1. **Monitor Usage:**
```bash
# Check Bedrock usage
aws bedrock get-model-invocation-logging-configuration

# Monitor OpenSearch costs
aws opensearchserverless list-collections
```

2. **Optimize Configuration:**
   - Implement request caching
   - Optimize knowledge base queries
   - Set up cost alerts and budgets
   - Use reserved capacity where applicable

### Issue: Security Concerns
**Symptoms:** Security scan findings or compliance issues

**Solution:**
1. **Review Security Settings:**
```bash
# Check S3 bucket encryption
aws s3api get-bucket-encryption --bucket $BUCKET_NAME

# Review IAM policies
aws iam list-roles --query 'Roles[?contains(RoleName, `bedrock-agent`)].RoleName'
```

2. **Implement Security Best Practices:**
   - Enable CloudTrail logging
   - Configure VPC deployment
   - Implement API rate limiting
   - Use customer-managed KMS keys
   - Enable GuardDuty monitoring

## General Debugging Strategies

### 1. Check CloudWatch Logs
```bash
# List all log groups for the application
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/bedrock-agent"

# View recent logs
aws logs tail /aws/lambda/bedrock-agent-chat-dev --follow
```

### 2. Monitor CloudFormation Events
```bash
# Check stack events for errors
aws cloudformation describe-stack-events \
  --stack-name knowledge-base-rag-agent-api-dev \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED`]'
```

### 3. Validate Configuration
```bash
# Run the validation script
./scripts/validate-deployment.sh dev

# Check environment configuration
cat infrastructure/.env

# Verify CDK synthesis
cd infrastructure && npm run synth
```

### 4. Test Individual Components
```bash
# Test API endpoints directly
API_URL=$(aws cloudformation describe-stacks \
  --stack-name knowledge-base-rag-agent-api-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text)

curl -X GET "$API_URL/health"

# Test Bedrock directly
aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-sonnet-4-20250514-v1:0 \
  --body '{"messages":[{"role":"user","content":"Hello"}],"max_tokens":100}' \
  --cli-binary-format raw-in-base64-out \
  response.json
```

## Getting Additional Help

### AWS Support Resources
- **AWS Support Center**: For service-specific issues and quota increases
- **AWS Documentation**: Comprehensive guides for all services used
- **AWS Forums**: Community support and discussions
- **AWS re:Post**: Q&A platform for technical questions

### Monitoring and Alerting
Set up proactive monitoring to catch issues early:

```bash
# Create CloudWatch dashboard
aws cloudwatch put-dashboard \
  --dashboard-name "AgentCore-Monitoring" \
  --dashboard-body file://monitoring/dashboard.json

# Set up cost alerts
aws budgets create-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget file://cost-budget.json
```

### Log Analysis
Use CloudWatch Insights for advanced log analysis:

```sql
-- Query for errors in Lambda logs
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 20
```

---

*This troubleshooting guide covers the most common issues encountered during deployment and operation. For issues not covered here, check CloudWatch logs for detailed error information and consult AWS documentation for service-specific guidance.*