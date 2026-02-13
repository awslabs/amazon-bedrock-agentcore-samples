# Concierge Shopping Agent - Deployment Guide

Complete deployment guide for the Concierge Agent system with Amplify backend, CDK infrastructure, and web UI.

## Prerequisites

### Required Tools
- **Node.js**: v18+ (v20 recommended)
- **npm**: v9+
- **AWS CLI**: v2+ configured with credentials
- **Docker**: For building agent container images
- **jq**: For JSON parsing - `brew install jq` (macOS) or `apt-get install jq` (Linux)

### AWS Account Requirements
- AWS account with appropriate permissions

### AWS Permissions Required
- Amplify deployment permissions
- CDK deployment permissions (CloudFormation, IAM, etc.)
- Bedrock permissions (AgentCore)
- S3, DynamoDB, Cognito, ECR

### API Keys (Optional)

API keys enable additional features but are not required for basic functionality.

**Note:** Without API keys, shopping features will be disabled, but the agent will still work.

#### SERP API (Product Search)

The shopping assistant requires SERP API for product search functionality.

1. **Sign up** at: https://serpapi.com/users/sign_up  # pragma: allowlist secret
2. **Configure** using the setup script:
   ```bash
   ./scripts/set-api-keys.sh
   ```
   This will prompt you for your API key and store it in AWS Systems Manager Parameter Store as `/concierge-agent/shopping/serp-api-key`

## Quick Start

Deploy all components with npm scripts:

```bash
# Install dependencies
npm install
cd amplify
npm install
cd ..

# 1. Deploy backend (Cognito, DynamoDB, AppSync)
npm run deploy:amplify

# 2. Deploy MCP servers (Cart + Shopping)
npm run deploy:mcp

# 3. Deploy main agent (Runtime + Gateway + Memory)
npm run deploy:agent
```

### Payment Integration

You have three options for payment integration:

#### Option 1: Mock Mode (No Visa Credentials Required)

Deploy with mock Visa APIs - no real payment processing:

```bash
npm run deploy:frontend --mock
```

No additional setup needed. The application will use mock data for all payment-related features.


#### Option 2: Visa Payment integration

**Important:** Visa credentials must be obtained directly from Visa. To onboard please follow the steps in [Visa Documentation.](visa-documentation/visa-payment-integration-guide.md#onboarding-process)

##### Option 2.1: Visa integration via Proxy

If you have Visa API credentials and want to deploy to production:

1. **Export Visa secrets** to AWS Secrets Manager:
   ```bash
   ./scripts/export-visa-secrets.sh
   ```
   This will prompt you for credentials and store them securely.

2. **Deploy Visa Lambda proxy**:
   ```bash
   npm run deploy:visa-lambda
   ```

3. **Deploy frontend**:
   ```bash
   npm run deploy:frontend
   ```

##### Option 2.2:  Visa integration via Local Backend Server

If you have Visa API credentials and want to develop locally:

1. **Export Visa secrets** to AWS Secrets Manager:
   ```bash
   ./scripts/export-visa-secrets.sh
   ```

2. **Follow the local backend server setup**:
   See [Visa Local Server README](concierge_agent/local-visa-server/README.md) for complete instructions.

   Quick summary:
   - You'll need 2 terminals, both signed into AWS
   - Terminal 1: Run `npm run dev` and open `https://vcas.local.com:9000`
   - Terminal 2: Run the local Visa backend server and open `http://localhost:5001`


## Deployment Dive Deep

### Step 1: Amplify Backend (~4 min)

Deploys Cognito, DynamoDB tables, and AppSync API.

```bash
npm run deploy:amplify
```

**What this deploys:**
- Cognito User Pool with web client and M2M client
- AppSync GraphQL API
- DynamoDB tables (UserProfile, Wishlist, Feedback)
- CloudFormation exports for cross-stack references

**Expected outputs:**
- `amplify_outputs.json` file created
- CloudFormation exports:
  - `ConciergeAgent-{deploymentId}-Auth-UserPoolId`
  - `ConciergeAgent-{deploymentId}-Auth-ClientId`
  - `ConciergeAgent-{deploymentId}-Auth-MachineClientId`
  - `ConciergeAgent-{deploymentId}-Data-UserProfileTableName`
  - `ConciergeAgent-{deploymentId}-Data-WishlistTableName`
  - `ConciergeAgent-{deploymentId}-Data-FeedbackTableName`

**Verification:**
```bash
# Check if amplify_outputs.json exists
ls amplify_outputs.json

# View CloudFormation exports
aws cloudformation list-exports --query "Exports[?contains(Name, 'ConciergeAgent')]"
```

### Step 2: MCP Servers (~60 sec)

Deploys Cart and Shopping MCP runtimes as separate stacks.

**Before deploying**, optionally configure API keys:

```bash
chmod +x scripts/set-api-keys.sh
./scripts/set-api-keys.sh
chmod +x scripts/export-visa-secrets.sh
./scripts/export-visa-secrets.sh
```

Deploy all MCP servers:

```bash
npm run deploy:mcp
```

**What this deploys:**
- **CartStack** - Shopping cart management with DynamoDB and Visa Secrets Manager access
- **ShoppingStack** - Product search tools with SerpAPI integration
- Both use OAuth authentication and integrate with Cognito

**Expected outputs:**
- `CartStack-{deploymentId}-RuntimeArn`
- `ShoppingStack-{deploymentId}-RuntimeArn`
- Runtime IDs for each stack

**Verification:**
```bash
# Check MCP runtime exports
aws cloudformation list-exports --query "Exports[?contains(Name, 'RuntimeArn')]"
```

### Step 3: Agent Stack (~4 min)

Deploys main supervisor agent with memory and gateway.

```bash
npm run deploy:agent
```

**What this deploys:**
- Agent Runtime with JWT authentication
- Memory resource for conversation persistence
- AgentCore Gateway connecting to MCP servers
- OAuth2 Credential Provider for M2M authentication
- IAM roles with permissions for DynamoDB, Bedrock, Memory, Gateway
- SSM parameter storing gateway URL

**Expected outputs:**
- `MainRuntimeArn` - Main agent runtime ARN
- `MemoryId` - Conversation memory ID
- `GatewayUrl` - Gateway endpoint URL
- `GatewayId` - Gateway ID
- `OAuthProviderArn` - OAuth provider ARN

**Post-deployment:**
The `sync-gateway.sh` script automatically runs to update the runtime with the gateway URL.

**Verification:**
```bash
# Check agent stack outputs
aws cloudformation describe-stacks \
  --stack-name AgentStack-shopping \
  --query 'Stacks[0].Outputs'

# Verify gateway URL in SSM
aws ssm get-parameter --name /concierge-agent/shopping/gateway-url
```

### Step 4: Visa Lambda Proxy (~2 min) - Optional

Deploys Lambda proxy for Visa API integration in production environments.

**Note:** Only deploy this if you have Visa API credentials and want to use real payment processing. Skip this step if using mock mode.

**Before deploying**, ensure you've exported Visa secrets:
```bash
./scripts/export-visa-secrets.sh
```

Deploy the Visa Lambda proxy:
```bash
npm run deploy:visa-lambda
```

**What this deploys:**
- Lambda function with Visa API integration
- API Gateway endpoints for Visa operations
- IAM roles with Secrets Manager access
- CORS configuration for frontend access

**Expected outputs:**
- `VisaLambdaStack-{deploymentId}-ApiUrl` - API Gateway endpoint URL
- Lambda function ARN

**Verification:**
```bash
# Check Visa Lambda stack outputs
aws cloudformation describe-stacks \
  --stack-name VisaLambdaStack-shopping \
  --query 'Stacks[0].Outputs'

# Test the API endpoint
curl https://<api-url>/health
```

### Step 5: Frontend (~3 min) - Optional

Deploys web UI to Amplify Hosting with CI/CD.

**Deployment options:**

**Option A: Deploy with Mock Visa APIs (No Visa credentials required)**
```bash
npm run deploy:frontend --mock
```

**Option B: Deploy with Real Visa Integration (Requires Step 4)**
```bash
npm run deploy:frontend
```

**What this deploys:**
- Amplify Hosting app
- CloudFront distribution
- GitHub integration for automatic builds
- Environment variables for agent connection
- Visa API configuration (mock or real based on deployment option)

**Expected outputs:**
- Live app URL (CloudFront distribution)
- Amplify app ID

**Verification:**
```bash
# Check frontend stack outputs
aws cloudformation describe-stacks \
  --stack-name FrontendStack \
  --query 'Stacks[0].Outputs'

# Visit the deployed URL
```

**Note:** The local Visa server only works with local development (`npm run dev`). When deploying to CloudFront, you must either:
- Use mock mode (`--mock` flag), or
- Deploy the Visa Lambda proxy (Step 4) for real payment processing


## Configuration

### Deployment ID

Configure via `deployment-config.json` in project root:

```json
{
  "deploymentId": "shopping",
  "description": "Unique identifier for this deployment"
}
```

Change `deploymentId` to deploy multiple independent instances in the same AWS account.

### Environment Variables

**Agent Container** (automatically configured):
```bash
MEMORY_ID=<memory-id>
USER_PROFILE_TABLE_NAME=<table-name>
WISHLIST_TABLE_NAME=<table-name>
FEEDBACK_TABLE_NAME=<table-name>
DEPLOYMENT_ID=<deployment-id>
GATEWAY_CLIENT_ID=<cognito-client-id>
GATEWAY_USER_POOL_ID=<user-pool-id>
GATEWAY_SCOPE=concierge-gateway/invoke
```

**Web UI** (auto-generated in `web-ui/.env.local`):
```env
VITE_AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:...
VITE_AGENT_ENDPOINT_NAME=DEFAULT
VITE_AWS_REGION=us-east-1
```

## Deployment Scripts Reference

| Script | Description | Time |
|--------|-------------|------|
| `npm run deploy` | Deploy Amplify + MCP + Agent + Visa Lambda | ~10 min |
| `npm run deploy:amplify` | Deploy Amplify backend only | ~4 min |
| `npm run deploy:mcp` | Deploy MCP servers only | ~60 sec |
| `npm run deploy:agent` | Deploy Agent stack only | ~4 min |
| `npm run deploy:visa-lambda` | Deploy Visa Lambda proxy | ~2 min |
| `npm run deploy:frontend` | Deploy web UI to Amplify Hosting | ~3 min |
| `npm run dev` | Start local development server | - |
| `npm run build` | Build web UI for production | - |
| `npm run clean` | Delete all resources (frontend, agent, MCP, Visa Lambda, Amplify) | ~6 min |
| `npm run clean:frontend` | Delete frontend only | ~1 min |
| `npm run clean:agent` | Delete agent stack only | ~2 min |
| `npm run clean:mcp` | Delete MCP servers only | ~1 min |
| `npm run clean:visa-lambda` | Delete Visa Lambda proxy only | ~1 min |
| `npm run clean:amplify` | Delete Amplify backend only | ~2 min |

## Troubleshooting

### Amplify Deployment Issues

**Issue:** `amplify_outputs.json` not created
```bash
# Solution: Ensure deployment completed successfully
npm run deploy:amplify

# Check CloudFormation stack status
aws cloudformation describe-stacks --stack-name amplify-*
```

**Issue:** Cognito exports not found
```bash
# Solution: Verify exports exist
aws cloudformation list-exports --query "Exports[?contains(Name, 'ConciergeAgent')]"
```

### MCP Deployment Issues

**Issue:** MCP stack deployment fails
```bash
# Solution: Ensure Amplify is deployed first
npm run deploy:amplify

# Verify Docker is running
docker ps

# Check agent code paths exist
ls -la concierge_agent/mcp_cart_tools/
ls -la concierge_agent/mcp_shopping_tools/
```

### Agent Stack Deployment Issues

**Issue:** Cannot import MCP runtime ARN
```bash
# Solution: Ensure MCP stacks are deployed first
npm run deploy:mcp

# Verify MCP exports
aws cloudformation list-exports --query "Exports[?contains(Name, 'RuntimeArn')]"
```

**Issue:** Docker build fails
```bash
# Solution: Ensure Docker is running
docker ps

# Test build locally
cd concierge_agent/supervisor_agent
docker build -t test-build .
```

**Issue:** OAuth provider creation fails
```bash
# Solution: Check Lambda logs
aws logs tail /aws/lambda/AgentStack-*-OAuthProviderLambda* --follow

# Verify IAM permissions for Lambda
```

### Gateway Issues

**Issue:** Gateway returns "An internal error occurred"

**Solution:** Enable debug mode to see detailed errors:

```bash
# Get gateway ID from stack outputs
GATEWAY_ID=$(aws cloudformation describe-stacks \
  --stack-name AgentStack-shopping \
  --query 'Stacks[0].Outputs[?OutputKey==`GatewayId`].OutputValue' \
  --output text)

# Enable debugging
aws bedrock-agentcore-control update-gateway \
  --gateway-identifier $GATEWAY_ID \
  --exception-level DEBUG
```

Or update the gateway construct in CDK to include `exceptionLevel: 'DEBUG'`.

### Web UI Issues

**Issue:** `.env.local` not created
```bash
# Solution: Ensure agent stack is deployed
npm run deploy:agent

# Manually configure
./scripts/setup-web-ui-env.sh
```

**Issue:** Authentication fails
```bash
# Check Cognito configuration
cat web-ui/.env.local

# Verify user exists
aws cognito-idp list-users --user-pool-id <pool-id>
```

**Issue:** Agent not responding
```bash
# Check Agent Runtime ARN is correct
cat web-ui/.env.local

# Verify runtime is active
aws bedrock-agentcore list-runtimes
```

### Common Issues
**AWS CLI**: Ensure AWS CLI is configured with credentials and running the latest version

**API Gateway logging**: Ensure API Gateway logs are enabled in CloudWatch

**Error: CloudWatch Logs role ARN must be set in account settings to enable logging (Service: ApiGateway, Status Code: 400**

1. Create the IAM role for API Gateway to push logs to CloudWatch:

   ```aws iam create-role --role-name APIGatewayCloudWatchLogsRole --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"apigateway.amazonaws.com"},"Action":"sts:AssumeRole"}]}'```

2. Attach the managed policy that allows pushing logs:

   ```aws iam attach-role-policy --role-name APIGatewayCloudWatchLogsRole --policy-arn arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs```

3. Configure API Gateway account settings to use this role:

   ```aws apigateway update-account --patch-operations op=replace,path=/cloudwatchRoleArn,value=arn:aws:iam::<account_id>:role/APIGatewayCloudWatchLogsRole```

**AgentCore Observability**: Enable CloudWatch Transaction Search and log delivery for debugging


One-time account setup for CloudWatch Transaction Search (enables traces/spans)
1. Open CloudWatch console
2. Navigate to Application Signals (APM) → Transaction search
3. Click "Enable Transaction Search"
4. Check "Ingest spans as structured logs"
5. Click Save

Per-resource log delivery (configure in AgentCore Console)
1. Open AgentCore Console → select Runtime/Memory/Gateway
2. Scroll to "Log delivery" section → Click "Add"
3. Select CloudWatch Logs, choose APPLICATION_LOGS type
4. Save

Enable Runtime tracing (per runtime)
1. Open AgentCore Console → Runtime agents → select runtime
2. Scroll to "Tracing" section → Enable


**Docker build fails**: Ensure Docker is running

**Permission errors**: Check IAM roles have Bedrock and DynamoDB permissions

**Frontend build fails**: Check TypeScript errors in `web-ui/src`

**Runtime connection fails**: Verify runtime ARN in `.env.local`

**CloudFormation export not found**: Ensure deployment order (Amplify → MCP → Agent)

## Updating the System

### Update Agent Code
```bash
# Make changes to concierge_agent/supervisor_agent/
npm run deploy:agent
```

### Update MCP Server Code
```bash
# Make changes to concierge_agent/mcp_cart_tools/ or mcp_shopping_tools/
# Touch Dockerfiles to force rebuild
find concierge_agent/mcp_* -name Dockerfile -exec touch {} \;
npm run deploy:mcp
```

### Update Amplify Backend
```bash
# Make changes to amplify/
npm run deploy:amplify
```

### Update Web UI
```bash
# Make changes to web-ui/src/
# For local development
npm run dev

# For deployed frontend
npm run deploy:frontend
```

## Clean Up

### Delete All Resources
```bash
npm run clean
```

This deletes (in order):
1. Frontend (Amplify Hosting)
2. Agent stack (Runtime, Memory, Gateway, OAuth Provider)
3. MCP servers (Cart and Shopping)
4. Amplify backend (Cognito, AppSync, DynamoDB)

### Partial Cleanup
```bash
# Delete only frontend
npm run clean:frontend

# Delete only agent stack
npm run clean:agent

# Delete only MCP servers
npm run clean:mcp

# Delete only Amplify backend
npm run clean:amplify
```

**Note:** Some resources may require manual deletion:
- CloudWatch log groups
- SSM parameters
- Secrets Manager secrets (Visa credentials)

## Cost Considerations

### Amplify Stack
- Cognito: Free tier available
- AppSync: Pay per request
- DynamoDB: On-demand pricing
- Lambda: Free tier available

### Infrastructure Stacks
- **Bedrock AgentCore**: Pay per invocation
- **Memory**: Pay per operation
- **ECR**: Minimal storage costs
- **MCP Runtimes**: Pay per invocation
- **Gateway**: Pay per request

### Optimization Tips
- Delete sandbox environments when not in use
- Use on-demand pricing for DynamoDB
- Monitor Bedrock usage
- Set up billing alerts

## Recommendations

1. **Use Amplify Pipelines** instead of sandbox:
```bash
npx ampx pipeline-deploy --branch main
```

2. **Use CDK Pipelines** for infrastructure stacks

3. **Enable monitoring**:
   - CloudWatch dashboards
   - X-Ray tracing
   - Bedrock usage metrics

4. **Security hardening**:
   - Enable MFA for Cognito
   - Restrict IAM permissions
   - Enable CloudTrail logging
   - Store API keys in AWS Secrets Manager

5. **Backup strategy**:
   - DynamoDB point-in-time recovery
   - Regular configuration backups

### Next Steps

After successful deployment:
1. Create Cognito users (admin only)
2. Test agent with sample queries
3. Monitor agent performance
4. Customize agent prompts as needed
5. Configure production environment
6. Set up monitoring and alerts

## Additional Resources

- [Infrastructure README](infrastructure/README.md) 
- [Main README](README.md)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
- [Amplify Documentation](https://docs.amplify.aws/)
