# Cloud Strands Insurance Agent with AWS Bedrock AgentCore

This guide shows how to deploy and run a Strands-based Insurance Agent that connects to AWS AgentCore Gateway MCP services for handling auto insurance quotes and vehicle information queries.

![Bedrock AgentCore Insurance App Conversation](agentcore_strands_conversation.gif)

## Prerequisites

- AWS account with appropriate permissions
- Docker Desktop or Finch installed and running
- Python 3.10+
- AWS CLI installed and configured
- jq command-line JSON processor

## Project Structure

```
cloud_strands_insurance_agent/
├── agentcore_strands_insurance_agent.py  # Main agent code
├── requirements.txt                      # Dependencies
├── 1_pre_req_setup/                      # Setup scripts
│   ├── cognito_auth/                     # Authentication setup
│   │   ├── setup_cognito.sh              # Interactive setup script
│   │   ├── refresh_token.sh              # Token refresh utility
│   │   ├── cognito_config.json           # Configuration storage
│   │   └── README.md                     # Setup documentation
│   └── iam_roles_setup/                  # IAM roles configuration
│       ├── setup_role.sh                 # Interactive IAM role setup
│       ├── policy_templates.py           # IAM policy definitions
│       ├── config.py                     # Configuration utilities
│       ├── collect_info.py               # Interactive input collection
│       └── README.md                     # Setup documentation
└── .env_example                          # Environment variable template
```

## Quick Reference

📋 **[Deployment Checklist](DEPLOYMENT_CHECKLIST.md)** - Step-by-step checklist to ensure successful deployment

🔧 **[Troubleshooting Guide](DEPLOYMENT_TROUBLESHOOTING.md)** - Solutions to common deployment issues

## Step 1: Set Up Prerequisites

Set up the required IAM roles and Cognito authentication:

### IAM Execution Role

```bash
cd 1_pre_req_setup/iam_roles_setup
./setup_role.sh
```

This interactive script will:
- Check your AWS credentials
- Collect required information (regions, repository name, agent name)
- Create an IAM role with least-privilege permissions for Bedrock AgentCore
- Save the role ARN for later use

### Cognito Authentication

```bash
cd ../cognito_auth
./setup_cognito.sh
```

This interactive script will:
- Create a Cognito User Pool and App Client
- Set up a test user with credentials
- Generate an initial authentication token
- Save all configuration for easy access

## Step 2: Configure Environment Variables

The agent uses environment variables for configuration. Create a `.env` file based on the example:

```bash
# Copy example file and edit with your values
cp .env_example .env
nano .env
```

Required environment variables:
```
# MCP Server Configuration
MCP_SERVER_URL="your-gateway-mcp-url"
MCP_ACCESS_TOKEN="your-access-token"

# Model configuration
MODEL_NAME="us.anthropic.claude-3-7-sonnet-20250219-v1:0"

# Optional: Gateway info file path (for refreshing tokens)
GATEWAY_INFO_FILE="../cloud_mcp_server/gateway_info.json"
```

You can retrieve your access token and MCP URL from the gateway_info.json file generated during gateway setup:

```bash
# Extract values from gateway_info.json (if available)
MCP_URL=$(jq -r '.gateway.mcp_url' ../cloud_mcp_server/gateway_info.json)
ACCESS_TOKEN=$(jq -r '.auth.access_token' ../cloud_mcp_server/gateway_info.json)

# Update .env file with extracted values
sed -i "s|MCP_SERVER_URL=.*|MCP_SERVER_URL=\"$MCP_URL\"|g" .env
sed -i "s|MCP_ACCESS_TOKEN=.*|MCP_ACCESS_TOKEN=\"$ACCESS_TOKEN\"|g" .env
```

## Step 3: Set Up AgentCore Identity (Optional but Recommended)

Configure AgentCore Identity for secure credential management:

```bash
# Run the automated identity setup
./setup_identity.sh
```

This will:
- Create a **Workload Identity** for the agent (Phase 2: Inbound authentication)
- Create an **API Key Credential Provider** for secure credential storage (Phase 1: Outbound)
- Save configuration to `identity_config.json`
- Optionally update your `.env` file with identity values

**What you need**:
- `AWS_REGION` set in `.env`
- `GATEWAY_INFO_FILE` path pointing to `../cloud_mcp_server/gateway_info.json`
- `API_KEY` (optional) - Insurance API key for secure storage

**What gets created**:
- Workload Identity: `insurance-agent-workload`
- API Key Provider: `InsuranceAPIKeyProvider` (if API_KEY is set)
- Environment variables: `WORKLOAD_IDENTITY_ARN`, `WORKLOAD_IDENTITY_ID`

For more details, see:
- Quick guide: [IDENTITY_QUICK_START.md](IDENTITY_QUICK_START.md)
- Full documentation: [IDENTITY_INTEGRATION.md](IDENTITY_INTEGRATION.md)

**Skip this step if**: You want to use basic authentication without Identity features.

## Step 4: Configure Your Agent

Configure the agent with your execution role (using the ARN from Step 1):

```bash
# Get your role ARN from the setup output or AWS console
ROLE_ARN=$(aws iam get-role --role-name BedrockAgentCoreExecutionRole --query 'Role.Arn' --output text)

# Configure the agent
agentcore configure -e "agentcore_strands_insurance_agent.py" \
  --name insurance_agent_strands \
  -er $ROLE_ARN
```

This creates:
- `.bedrock_agentcore.yaml` - Configuration file
- `Dockerfile` - Container build instructions (if not already present)
- `.dockerignore` - Files to exclude from build

## Step 5: Local Testing

Test your agent locally before cloud deployment:

```bash
# Load environment variables from .env file
source .env

# Launch locally with environment variables
agentcore launch -l \
  -env MCP_SERVER_URL=$MCP_SERVER_URL \
  -env MCP_ACCESS_TOKEN=$MCP_ACCESS_TOKEN
```

This will:
- Build a Docker image
- Run the container locally on port 8080
- Start the agent server

Test locally:
```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"user_input": "I need a quote for auto insurance"}'
```

## Step 6: Deploy to Cloud

Deploy your agent to AWS:

```bash
# Load environment variables from .env file
source .env

# Verify environment variables are loaded
echo "Checking environment variables..."
echo "MCP_SERVER_URL: $MCP_SERVER_URL"
echo "AWS_REGION: $AWS_REGION"
echo "MODEL_NAME: $MODEL_NAME"

# Deploy to AWS Bedrock AgentCore
# IMPORTANT: All -env flags are REQUIRED for the agent to function
# The agent code expects these environment variables at runtime

# Full deployment with Identity (recommended):
agentcore launch \
  -env MCP_SERVER_URL=$MCP_SERVER_URL \
  -env MCP_ACCESS_TOKEN=$MCP_ACCESS_TOKEN \
  -env MODEL_NAME=$MODEL_NAME \
  -env AWS_REGION=$AWS_REGION \
  -env WORKLOAD_IDENTITY_ARN=$WORKLOAD_IDENTITY_ARN \
  -env WORKLOAD_IDENTITY_ID=$WORKLOAD_IDENTITY_ID \
  -env API_KEY_PROVIDER_NAME=$API_KEY_PROVIDER_NAME

# Basic deployment without Identity:
# agentcore launch \
#   -env MCP_SERVER_URL=$MCP_SERVER_URL \
#   -env MCP_ACCESS_TOKEN=$MCP_ACCESS_TOKEN \
#   -env MODEL_NAME=$MODEL_NAME \
#   -env AWS_REGION=$AWS_REGION
```

**Important Notes:**
- The `-env` flags pass environment variables to the agent runtime
- Without these variables, the agent will fail with "client initialization failed"
- After deployment, verify variables were set: `cat .bedrock_agentcore.yaml | grep -A 20 environment`
- If you see no `environment:` section, redeploy with the `-env` flags

This will:
- Build and push Docker image to ECR
- Create Bedrock AgentCore runtime
- Deploy agent to the cloud
- Return agent ARN for invocation

## Step 7: Invoke Your Agent

Set your bearer token and invoke the deployed agent:

```bash
# Get your Cognito bearer token
cd 1_pre_req_setup/cognito_auth

# Refresh token if needed
./refresh_token.sh

# Export token
export BEARER_TOKEN=$(jq -r '.bearer_token' cognito_config.json)

# Go back to project root
cd ../../

# Invoke agent
agentcore invoke '{"user_input": "Can you help me get a quote for auto insurance?"}' --bearer-token $BEARER_TOKEN
```

## Agent Code Structure

The `agentcore_strands_insurance_agent.py` follows this pattern:

```python
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    user_input = payload.get("user_input", "I need a quote for auto insurance")
    
    # Connect to Gateway MCP with authentication
    gateway_client = MCPClient(lambda: streamablehttp_client(
        gateway_url, 
        headers={"Authorization": f"Bearer {access_token}"}
    ))
    
    with gateway_client:
        tools = gateway_client.list_tools_sync()
        agent = Agent(
            model="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            tools=tools,
            system_prompt="You are an insurance agent assistant..."
        )
        response = agent(user_input)
        return {"result": str(response)}
```

## Dependencies

Main dependencies from `requirements.txt`:
```
mcp>=0.1.0
strands-agents>=0.1.8
bedrock_agentcore
boto3
botocore
typing-extensions
python-dateutil
python-dotenv>=1.0.0
```

## Troubleshooting

### Common Deployment Issues

- **424 Failed Dependency**: Check agent logs in CloudWatch
- **Token expired**: Run `./1_pre_req_setup/cognito_auth/refresh_token.sh` and update your `.env` file
- **Permission denied**: Verify execution role has Bedrock model access
- **Local testing fails**: Ensure Docker is running
- **Authentication errors**: Check that MCP_ACCESS_TOKEN in your .env file is valid and not expired
- **IAM role errors**: Make sure the IAM role has all required permissions specified in `iam_roles_setup/README.md`
- **Cognito authentication issues**: Check the documentation in `cognito_auth/README.md` for troubleshooting

### ECR Permission Errors

If you see: `Access denied while validating ECR URI... requires permissions for ecr:GetAuthorizationToken, ecr:BatchGetImage, and ecr:GetDownloadUrlForLayer`

**Solution**: Update your IAM role with ECR permissions:

```bash
# Get your account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Update the IAM role policy
cat > /tmp/ecr-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRImageAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ],
      "Resource": [
        "arn:aws:ecr:*:${ACCOUNT_ID}:repository/bedrock-agentcore-*"
      ]
    },
    {
      "Sid": "ECRTokenAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name BedrockAgentCoreExecutionRole \
  --policy-name ECRAccessPolicy \
  --policy-document file:///tmp/ecr-policy.json
```

**Note**: If you re-run the IAM setup script (`./1_pre_req_setup/iam_roles_setup/setup_role.sh`), it will automatically include these permissions.

### Memory Not Working

If memory features aren't working (no conversation history):

**Solution**: Add memory permissions to your IAM role:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

cat > /tmp/memory-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "MemoryAccess",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:CreateMemory",
        "bedrock-agentcore:GetMemory",
        "bedrock-agentcore:UpdateMemory",
        "bedrock-agentcore:DeleteMemory",
        "bedrock-agentcore:ListMemories",
        "bedrock-agentcore:CreateEvent",
        "bedrock-agentcore:RetrieveMemories"
      ],
      "Resource": [
        "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:memory/*"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name BedrockAgentCoreExecutionRole \
  --policy-name MemoryAccessPolicy \
  --policy-document file:///tmp/memory-policy.json
```

**Note**: Re-running the IAM setup script will automatically include memory permissions.

### Docker Build Errors

If CodeBuild fails with "Dockerfile not found":
- Check that `.dockerignore` is not excluding the `Dockerfile`
- The Dockerfile should be in the root of your agent directory
- Re-run `agentcore configure` if needed

### Client Initialization Failed

If you see: `I'm sorry, I encountered an error: the client initialization failed`

**Cause**: Environment variables were not passed to the agent runtime.

**Solution**: Redeploy with all required environment variables:

```bash
source .env

agentcore launch \
  -env MCP_SERVER_URL=$MCP_SERVER_URL \
  -env MCP_ACCESS_TOKEN=$MCP_ACCESS_TOKEN \
  -env MODEL_NAME=$MODEL_NAME \
  -env AWS_REGION=$AWS_REGION \
  -env WORKLOAD_IDENTITY_ARN=$WORKLOAD_IDENTITY_ARN \
  -env WORKLOAD_IDENTITY_ID=$WORKLOAD_IDENTITY_ID
```

**Verify**: Check that environment variables are in the config:
```bash
cat .bedrock_agentcore.yaml | grep -A 20 environment
```

You should see an `environment:` section with all your variables.

## Monitoring and Observability

The agent now includes **AgentCore Observability** for comprehensive monitoring:

### Automatic Instrumentation
- **Session Tracking**: Each invocation is tracked with a unique session ID
- **Distributed Tracing**: OpenTelemetry automatically traces agent execution
- **CloudWatch Integration**: Traces and metrics sent to CloudWatch automatically

### Viewing Observability Data

1. **GenAI Observability Dashboard**:
   - Open CloudWatch Console → GenAI Observability
   - View the **Bedrock AgentCore** tab
   - See agents, sessions, and traces

2. **CloudWatch Logs**:
   - Location: `/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>/runtime-logs`
   - View structured OTEL logs

3. **Transaction Search**:
   - CloudWatch → Transaction Search
   - Filter by service name or session ID
   - View detailed execution graphs

### Session Tracking
Pass `session_id` in your payload to correlate multiple invocations:
```bash
agentcore invoke --bearer-token $BEARER_TOKEN '{
  "user_input": "I need a quote",
  "session_id": "customer-session-123",
  "actor_id": "customer-456"
}'
```

## Memory Features

The agent includes **AgentCore Memory** for conversation persistence and customer preferences:

### Memory Strategy
- **User Preference Strategy**: Automatically learns customer preferences
- **Namespace**: `/insurance/customers/{actor_id}` - organized by customer
- **Auto-extraction**: Learns coverage needs, vehicle preferences, interaction patterns

### How It Works
1. **Automatic Context**: Previous conversations are retrieved and added to prompts
2. **Preference Learning**: Customer preferences are extracted and stored automatically
3. **Cross-Session**: Memory persists across multiple sessions for the same customer

### Using Memory
Simply include `actor_id` (customer identifier) in your payload:
```bash
agentcore invoke --bearer-token $BEARER_TOKEN '{
  "user_input": "What coverage did I ask about last time?",
  "actor_id": "customer-456"
}'
```

### Memory Configuration
- **Auto-creation**: Memory resource created automatically on first run
- **Manual configuration**: Set `MEMORY_ID` in `.env` to use existing memory resource
- **Region**: Configure via `AWS_REGION` in `.env` (default: us-west-2)

### Viewing Memory Data
```python
from bedrock_agentcore.memory import MemoryClient

client = MemoryClient(region_name="us-west-2")
memories = client.retrieve_memories(
    memory_id="your-memory-id",
    namespace="/insurance/customers/customer-456",
    query="What are the customer's preferences?"
)
```

## Next Steps

- Set up token refresh automation
- Configure session management
- Integrate with additional insurance APIs
- Enhance error handling and logging