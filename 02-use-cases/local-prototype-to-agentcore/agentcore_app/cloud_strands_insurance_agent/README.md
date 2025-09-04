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

## Step 3: Configure Your Agent

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

## Step 4: Local Testing

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

## Step 5: Deploy to Cloud

Deploy your agent to AWS:

```bash
# Load environment variables from .env file
source .env

# Deploy to AWS Bedrock AgentCore
agentcore launch \
  -env MCP_SERVER_URL=$MCP_SERVER_URL \
  -env MCP_ACCESS_TOKEN=$MCP_ACCESS_TOKEN
```

This will:
- Build and push Docker image to ECR
- Create Bedrock AgentCore runtime
- Deploy agent to the cloud
- Return agent ARN for invocation

## Step 6: Invoke Your Agent

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
agentcore invoke --bearer-token $BEARER_TOKEN '{"user_input": "Can you help me get a quote for auto insurance?"}'
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

- **424 Failed Dependency**: Check agent logs in CloudWatch
- **Token expired**: Run `./1_pre_req_setup/cognito_auth/refresh_token.sh` and update your `.env` file
- **Permission denied**: Verify execution role has Bedrock model access
- **Local testing fails**: Ensure Docker is running
- **Authentication errors**: Check that MCP_ACCESS_TOKEN in your .env file is valid and not expired
- **IAM role errors**: Make sure the IAM role has all required permissions specified in `iam_roles_setup/README.md`
- **Cognito authentication issues**: Check the documentation in `cognito_auth/README.md` for troubleshooting

## Monitoring and Observability

- Monitor agent performance in CloudWatch
- View traces in AWS X-Ray
- Check agent logs for detailed error information

## Next Steps

- Set up token refresh automation
- Configure session management
- Integrate with additional insurance APIs
- Enhance error handling and logging