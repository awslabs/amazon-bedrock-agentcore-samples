# Deployment Guide

Complete guide for deploying the Real Estate Multi-Agent System.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Deploy Agents to AWS](#deploy-agents-to-aws)
4. [Run Locally](#run-locally)
5. [Deploy to Production](#deploy-to-production)
6. [Monitoring & Maintenance](#monitoring--maintenance)

## Prerequisites

### Required Software

```bash
# Python 3.8 or higher
python3 --version

# Node.js 16 or higher
node --version
npm --version

# AWS CLI configured
aws --version
aws configure  # If not already configured

# AgentCore CLI
pip install bedrock-agentcore-cli
agentcore --version
```

### AWS Permissions

Your AWS IAM user/role needs these permissions:
- `bedrock-agentcore:*` - For agent deployment
- `cognito-idp:*` - For OAuth setup
- `iam:CreateRole`, `iam:AttachRolePolicy` - For execution roles
- `ecr:*` - For container registry
- `logs:*` - For CloudWatch logs

### AWS Region

This project uses `us-east-1` by default. To use a different region, update:
- `setup_cognito_automated.py` - Line with `region='us-east-1'`
- `deploy_agents_with_oauth.py` - Region configuration
- `ui-backend/server.py` - Boto3 client region

## Initial Setup

### 1. Clone and Navigate

```bash
git clone <your-repo>
cd A2A-realestate-agents
```

### 2. Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r realestate_coordinator/requirements.txt
pip install -r propertysearchagent_strands/requirements.txt
pip install -r propertybookingagent_strands/requirements.txt
pip install -r ui-backend/requirements.txt
```

### 3. Verify AWS Access

```bash
aws sts get-caller-identity
```

Should output your AWS account ID and user ARN.

## Deploy Agents to AWS

### Step 1: Setup Cognito OAuth

```bash
python setup_cognito_automated.py
```

This creates:
- Cognito User Pool
- OAuth 2.0 client with client credentials flow
- Resource server with custom scope
- Saves config to `cognito_config.json`

**Time:** ~2 minutes

### Step 2: Deploy Agents

```bash
python deploy_agents_with_oauth.py
```

This deploys:
1. **Property Search Agent**
   - Searches properties by location, price, type, bedrooms
   - Deployed as container to AgentCore Runtime
   - Protected by OAuth JWT authorizer

2. **Property Booking Agent**
   - Creates and manages property bookings
   - Checks booking status
   - Protected by OAuth JWT authorizer

3. **Real Estate Coordinator**
   - Orchestrates sub-agents using A2A protocol
   - Natural language understanding
   - Protected by OAuth JWT authorizer

**Time:** ~10-15 minutes (includes container builds and deployments)

**Output:**
```
✅ Successfully deployed 3 agent(s):
  • property_search_agent
    ARN: arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/property_search_agent-XXXXX
  • property_booking_agent
    ARN: arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/property_booking_agent-XXXXX
  • realestate_coordinator
    ARN: arn:aws:bedrock-agentcore:us-east-1:ACCOUNT:runtime/realestate_coordinator-XXXXX
```

Deployment info saved to `deployment_info.json`.

### Step 3: Verify Deployment

```bash
# Quick coordinator test
python test_coordinator_quick.py
```

## Run Locally

### Backend Server

```bash
./start-backend.sh
```

The backend:
- Loads deployment config from `deployment_info.json`
- Fetches fresh OAuth token from Cognito
- Initializes coordinator agent
- Starts Flask API on port 5000

**Endpoints:**
- `GET /api/health` - Health check
- `GET /api/config` - Get configuration
- `POST /api/chat` - Send message to coordinator
- `POST /api/token/refresh` - Refresh OAuth token

### React UI

In a new terminal:

```bash
./start-ui.sh
```

The UI:
- Installs npm dependencies (first time)
- Starts React dev server on port 3000
- Opens browser automatically

**Access:** http://localhost:3000

## Deploy to Production

### Option 1: Deploy Backend to AWS Lambda

```python
# Create Lambda deployment package
cd ui-backend
pip install -r requirements.txt -t package/
cd package
zip -r ../lambda-deployment.zip .
cd ..
zip -g lambda-deployment.zip server.py

# Create Lambda function
aws lambda create-function \
  --function-name real-estate-backend \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT:role/lambda-execution-role \
  --handler server.lambda_handler \
  --zip-file fileb://lambda-deployment.zip \
  --timeout 120 \
  --memory-size 512

# Create API Gateway
# (Use AWS Console or CloudFormation)
```

### Option 2: Deploy Backend to ECS/Fargate

```dockerfile
# Create Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY ui-backend/requirements.txt .
RUN pip install -r requirements.txt

COPY ui-backend/ .
COPY realestate_coordinator/ ./realestate_coordinator/
COPY common/ ./common/
COPY deployment_info.json .

EXPOSE 5000
CMD ["python", "server.py"]
```

```bash
# Build and push to ECR
docker build -t real-estate-backend .
aws ecr create-repository --repository-name real-estate-backend
docker tag real-estate-backend:latest ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/real-estate-backend:latest
docker push ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/real-estate-backend:latest

# Deploy to ECS (use AWS Console or CloudFormation)
```

### Deploy UI to S3 + CloudFront

```bash
cd ui

# Build production bundle
npm run build

# Upload to S3
aws s3 sync build/ s3://your-bucket-name/ --delete

# Create CloudFront distribution
# (Use AWS Console or CloudFormation)

# Update API URL in production
# Set REACT_APP_API_URL environment variable
```

### Deploy UI to AWS Amplify

```bash
# Install Amplify CLI
npm install -g @aws-amplify/cli

# Initialize Amplify
cd ui
amplify init

# Add hosting
amplify add hosting

# Publish
amplify publish
```

## Monitoring & Maintenance

### View Agent Logs

```bash
# View coordinator logs
agentcore logs realestate_coordinator

# View search agent logs
agentcore logs property_search_agent

# View booking agent logs
agentcore logs property_booking_agent

# Follow logs in real-time
agentcore logs realestate_coordinator --follow
```

### CloudWatch Logs

Agents automatically log to CloudWatch:
- Log Group: `/aws/bedrock-agentcore/runtime/<agent-name>`
- Retention: 7 days (configurable)

### Update Agents

```bash
# Make changes to agent code
vim realestate_coordinator/agent.py

# Redeploy
cd realestate_coordinator
agentcore launch --auto-update-on-conflict
```

### Refresh OAuth Token

Tokens expire after 60 minutes. The backend auto-refreshes, but to manually refresh:

```bash
python get_fresh_token.py
```

### Update OAuth Configuration

```bash
# Update Cognito settings
aws cognito-idp update-user-pool-client \
  --user-pool-id us-east-1_XXXXXXXXX \
  --client-id XXXXXXXXXXXXXXXXXX \
  --allowed-o-auth-flows client_credentials \
  --allowed-o-auth-scopes a2a-agents/invoke

# Redeploy agents with new config
python deploy_agents_with_oauth.py
```

### Scale Agents

AgentCore automatically scales based on load. To configure:

```yaml
# In .bedrock_agentcore.yaml
aws:
  scaling:
    min_instances: 1
    max_instances: 10
    target_cpu_utilization: 70
```

### Cost Optimization

- **Agents**: Pay per invocation + compute time
- **Cognito**: Free tier covers most development use
- **CloudWatch**: Logs incur storage costs
- **Model Usage**: Claude Sonnet charges per token

To reduce costs:
- Use smaller models for simple tasks
- Implement caching for repeated queries
- Set log retention to 1-3 days
- Use reserved capacity for production

## Troubleshooting

### Deployment Fails

```bash
# Check AgentCore CLI version
agentcore --version

# Update if needed
pip install --upgrade bedrock-agentcore-cli

# Check AWS permissions
aws iam get-user

# View detailed error logs
agentcore logs <agent-name> --tail 100
```

### OAuth Errors

```bash
# Verify Cognito configuration
aws cognito-idp describe-user-pool --user-pool-id us-east-1_XXXXXXXXX

# Test token generation
python get_fresh_token.py

# Check token validity
python -c "
import json, base64
with open('.bearer_token') as f:
    token = f.read()
payload = token.split('.')[1]
payload += '=' * (4 - len(payload) % 4)
print(json.dumps(json.loads(base64.urlsafe_b64decode(payload)), indent=2))
"
```

### Agent Not Responding

```bash
# Check agent status
agentcore list

# View recent logs
agentcore logs <agent-name> --tail 50

# Test agent directly
python test_coordinator_quick.py

# Restart agent (redeploy)
cd <agent-directory>
agentcore launch --auto-update-on-conflict
```

## Rollback

### Rollback Agent Deployment

```bash
# List previous versions
agentcore versions <agent-name>

# Rollback to previous version
agentcore rollback <agent-name> --version <version-id>
```

### Rollback Cognito Changes

Cognito changes are not easily reversible. Best practice:
- Keep backup of `cognito_config.json`
- Document all manual changes
- Use Infrastructure as Code (CloudFormation/Terraform)

## Security Best Practices

1. **Rotate OAuth Credentials**
   ```bash
   # Generate new client secret
   aws cognito-idp update-user-pool-client \
     --user-pool-id <pool-id> \
     --client-id <client-id> \
     --generate-secret
   ```

2. **Enable CloudTrail**
   - Track all API calls to agents
   - Monitor for suspicious activity

3. **Use VPC Endpoints**
   - Keep agent traffic within AWS network
   - Reduce exposure to internet

4. **Implement Rate Limiting**
   - Protect against abuse
   - Use API Gateway throttling

5. **Regular Updates**
   - Keep dependencies updated
   - Monitor security advisories

## Support

- **AgentCore Issues**: AWS Support or AgentCore documentation
- **OAuth/Cognito**: AWS Cognito documentation
- **Application Issues**: Check logs and troubleshooting section

---

**Last Updated:** November 2025
