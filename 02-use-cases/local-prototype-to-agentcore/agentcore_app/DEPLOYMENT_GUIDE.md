# AgentCore Insurance App - Deployment Guide

## Quick Deployment Options

### Option 1: Automated Deployment (5-10 minutes)

**Best for**: Quick setup, demos, getting started

```bash
./deploy_all.sh
```

This single command deploys everything automatically.

### Option 2: Manual Step-by-Step (20-30 minutes)

**Best for**: Learning, customization, troubleshooting

Follow the detailed steps in [README.md](README.md)

---

## Automated Deployment Details

### Prerequisites

Before running `./deploy_all.sh`, ensure you have:

- ✅ AWS CLI configured with admin access
- ✅ Python 3.10+
- ✅ jq command-line tool
- ✅ Docker Desktop (for local testing)
- ✅ Bedrock model access enabled

### What Gets Deployed

1. **Insurance API** (Lambda + API Gateway)
   - FastAPI application
   - Auto insurance data endpoints
   - API key authentication

2. **MCP Gateway** (AgentCore Gateway)
   - OAuth2 authentication (Cognito)
   - OpenAPI integration
   - MCP tool exposure

3. **AgentCore Identity**
   - Workload Identity (inbound auth)
   - API Key Provider (outbound auth)
   - Secure credential management

4. **Strands Agent** (AgentCore Runtime)
   - IAM execution role
   - Cognito user pool
   - Agent runtime deployment
   - Memory integration
   - Observability enabled

### Deployment Time

- **Automated**: 5-10 minutes
- **Manual**: 20-30 minutes

### Post-Deployment

After successful deployment:

```bash
# View logs
agentcore logs --tail 50

# Invoke agent
cd cloud_strands_insurance_agent
source .env
cd 1_pre_req_setup/cognito_auth
./refresh_token.sh
export BEARER_TOKEN=$(jq -r '.bearer_token' cognito_config.json)
cd ../..

agentcore invoke --bearer-token $BEARER_TOKEN \
  '{"user_input": "Can you help me get a quote?", "actor_id": "user123"}'
```

---

## Manual Deployment Steps

### Step 1: Deploy Insurance API

```bash
cd cloud_insurance_api/deployment
./deploy.sh
```

### Step 2: Setup MCP Gateway

```bash
cd ../../cloud_mcp_server
./setup.sh
```

### Step 3: Configure Identity

```bash
cd ../cloud_strands_insurance_agent
cp .env_example .env
# Edit .env with your values
./setup_identity.sh
```

### Step 4: Deploy Agent

```bash
# Setup IAM
cd 1_pre_req_setup/iam_roles_setup
./setup_role.sh

# Setup Cognito
cd ../cognito_auth
./setup_cognito.sh

# Configure and deploy
cd ../..
ROLE_ARN=$(aws iam get-role --role-name BedrockAgentCoreExecutionRole --query 'Role.Arn' --output text)
agentcore configure -e "agentcore_strands_insurance_agent.py" --name insurance_agent_strands -er $ROLE_ARN

source .env
agentcore launch \
  -env MCP_SERVER_URL="$MCP_SERVER_URL" \
  -env MCP_ACCESS_TOKEN="$MCP_ACCESS_TOKEN" \
  -env MODEL_NAME="$MODEL_NAME" \
  -env AWS_REGION="$AWS_REGION" \
  -env WORKLOAD_IDENTITY_ARN="$WORKLOAD_IDENTITY_ARN" \
  -env WORKLOAD_IDENTITY_ID="$WORKLOAD_IDENTITY_ID" \
  -env API_KEY_PROVIDER_NAME="$API_KEY_PROVIDER_NAME"
```

---

## Troubleshooting

### Automated Deployment Failed

If `./deploy_all.sh` fails:

1. **Check which step failed** - The script shows clear step numbers
2. **Run that step manually** - Follow the manual steps for that component
3. **Check logs** - Look at the error message for details
4. **Continue from where it failed** - You don't need to start over

### Common Issues

| Issue | Solution |
|-------|----------|
| AWS CLI not configured | Run `aws configure` |
| Python not found | Install Python 3.10+ |
| jq not found | Install jq: `brew install jq` (macOS) |
| Docker not running | Start Docker Desktop |
| Region mismatch | Ensure `.env` has `AWS_REGION="us-east-1"` |
| Token expired | Run `./refresh_token.sh` in cognito_auth folder |

### Getting Help

- **Deployment Checklist**: [cloud_strands_insurance_agent/DEPLOYMENT_CHECKLIST.md](cloud_strands_insurance_agent/DEPLOYMENT_CHECKLIST.md)
- **Troubleshooting Guide**: [cloud_strands_insurance_agent/DEPLOYMENT_TROUBLESHOOTING.md](cloud_strands_insurance_agent/DEPLOYMENT_TROUBLESHOOTING.md)
- **Identity Guide**: [cloud_strands_insurance_agent/IDENTITY_QUICK_START.md](cloud_strands_insurance_agent/IDENTITY_QUICK_START.md)

---

## Verification

After deployment, verify everything works:

```bash
# 1. Check agent is deployed
cat cloud_strands_insurance_agent/.bedrock_agentcore.yaml

# 2. Check environment variables are set
cat cloud_strands_insurance_agent/.bedrock_agentcore.yaml | grep -A 20 environment

# 3. Test invocation
cd cloud_strands_insurance_agent
agentcore invoke '{"user_input": "test"}' --bearer-token $BEARER_TOKEN

# 4. Check logs
agentcore logs --tail 50
```

### Success Criteria

✅ Insurance API returns 200 OK  
✅ MCP Gateway has tools available  
✅ Identity resources created  
✅ Agent responds to invocations  
✅ No "client initialization failed" errors  
✅ Memory is created and working  

---

## Clean Up

To remove all deployed resources:

```bash
# Delete agent runtime
agentcore delete

# Delete CloudFormation stacks
aws cloudformation delete-stack --stack-name insurance-api-dev

# Delete Identity resources
cd cloud_strands_insurance_agent
python cleanup_duplicate_memories.py --delete

# Delete IAM roles and Cognito (manual via AWS Console)
```

---

## Next Steps

After successful deployment:

1. **Explore the agent**: Try different insurance queries
2. **Check observability**: View traces in CloudWatch GenAI Dashboard
3. **Test memory**: Ask follow-up questions with the same actor_id
4. **Customize**: Modify the agent code for your use case

For more information, see the main [README.md](README.md)
