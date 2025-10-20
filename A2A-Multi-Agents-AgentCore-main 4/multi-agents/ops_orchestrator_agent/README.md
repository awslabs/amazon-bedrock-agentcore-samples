# Ops Orchestrator Agent - Complete Setup Guide

This operations orchestrator agent is built using AWS Bedrock AgentCore runtime for searching best practices and providing infrastructure remediation guidance. This guide provides step-by-step instructions for complete setup from secrets management to runtime deployment.

## Prerequisites

Create the `uv` environment as provided in the top level `README.md` file.

Additionally, ensure you have:
- **AWS Account and Credentials**: Ensure AWS credentials are configured
- **Python 3.11+**: Required for all components
- **IAM Permissions**: Admin access or sufficient permissions for:
  - Amazon Bedrock AgentCore
  - AWS Systems Manager Parameter Store
  - Amazon Cognito
  - IAM role creation
- **API Keys**:
  - OpenAI API key (required)
  - Tavily API key (for web search)
  - JIRA API key (optional, for ticket creation)

## Overview

The setup process consists of 3 main steps:
1. **API Keys Management** - Store API keys securely in AWS Systems Manager Parameter Store or use environment variables
2. **Cognito Authentication** - Set up inbound authentication for the agent to be accessed via OAuth 2.0
3. **Agent Runtime** - Deploy and test the ops orchestrator agent as an A2A server on AgentCore Runtime. For more information on A2A server deployment on AgentCore, view this [documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html)

## Step 1: API Keys Management

The ops orchestrator agent requires API keys for OpenAI, Tavily (web search), and optionally JIRA. You can store these keys in **AWS Systems Manager Parameter Store** (recommended) or use environment variables as a fallback.

### Option A: Store API Keys in AWS Systems Manager Parameter Store (Recommended)

Store your API keys securely in SSM Parameter Store using the AWS CLI:

```bash
# Store Tavily API Key
aws ssm put-parameter \
    --name "/ops-orchestrator/tavily-api-key" \
    --value "your-tavily-key-here" \
    --type "SecureString" \
    --region us-west-2

# Store OpenAI API Key
aws ssm put-parameter \
    --name "/ops-orchestrator/openai-api-key" \
    --value "your-openai-key-here" \
    --type "SecureString" \
    --region us-west-2

# Store JIRA API Key (optional)
aws ssm put-parameter \
    --name "/ops-orchestrator/jira-api-key" \
    --value "your-jira-key-here" \
    --type "SecureString" \
    --region us-west-2
```

**Verify the parameters were created successfully:**

```bash
# List all ops-orchestrator parameters
aws ssm get-parameters-by-path \
    --path "/ops-orchestrator" \
    --region us-west-2

# Get a specific parameter (without decryption for verification)
aws ssm get-parameter \
    --name "/ops-orchestrator/tavily-api-key" \
    --region us-west-2
```

**IAM Permissions Required:**

Ensure your IAM role/user has the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:PutParameter"
      ],
      "Resource": "arn:aws:ssm:us-west-2:*:parameter/ops-orchestrator/*"
    }
  ]
}
```

The agent will automatically load these keys from SSM Parameter Store using the configuration in `config.yaml`.

## Step 2: Cognito Authentication Setup

Set up Amazon Cognito for inbound authentication to the ops orchestrator agent. For more information on how AgentCore identity works, view the documentation [here](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html).

### 2.1 Navigate to IdP Setup Directory

```bash
cd idp_setup
```

### 2.2 Run Cognito Setup

Execute the Cognito setup script:

```bash
python setup_cognito.py
```

This will:
- Create a Cognito User Pool
- Set up a resource server with appropriate scopes
- Create M2M (machine-to-machine) client credentials
- Generate a test user for authentication
- Save configuration to `idp_setup/cognito_config.json`

### 2.3 Record Cognito Configuration

The script will output important configuration details:

```
COGNITO SETUP COMPLETE
====================================
Pool ID: us-west-2_XXXXXXXXX
Client ID: XXXXXXXXXXXXXXXXXXXXXXXXXX
Discovery URL: https://cognito-idp.us-west-2.amazonaws.com/us-west-2_XXXXXXXXX/.well-known/jwks.json
Username: testuser
Password: MyPassword123!
M2M Client ID: XXXXXXXXXXXXXXXXXXXXXXXXXX
M2M Client Secret: XXXXXXXXXX...
====================================
```

Save these values - you'll need them for agent configuration.

## Step 3: Agent Runtime Setup

Deploy and test the `ops` orchestrator agent runtime.

### 3.1 Navigate to Main Directory

```bash
cd ..
```

### 3.2 Update Agent Configuration

Update the sections in `config.yaml` with your setup information:

```yaml
agent_information:
  ops_orchestrator_agent_model_info:
    # Model configuration
    model_id: "gpt-4o-2024-08-06"

    # Inference parameters
    inference_parameters:
      temperature: 0.1
      max_tokens: 2048
  # set this to yes and provide the memory created from before
  use_existing_memory: yes
    memory_credentials:
      # fetch this from your AWS console
      id: 

# Fetch this information from the cognito_config.json file and the console
# This would be retrieved from SSM or Identity provider in prod
idp_setup:
  user_pool_id:
  domain:
  discovery_url:
  client_secret:
  client_id:
  resource_server_identifier:
  scopes:
    -
    -

# This is information about the cloudwatch related tools that will be used
# in the agent
cloudwatch_agent_resources:
  # This information will be used to export all of the OTEL data to cloudwatch
  # for AgentCore observability to be enabled
  log_group_name: "" # provide this else it will be created
  log_stream_name: "" # provide this else it will be created
```

## Running the Ops Orchestrator Agent as an A2A Server

Strands Agents supports the Agent-to-Agent (A2A) protocol, enabling seamless communication between AI agents across different platforms and implementations.

The Agent-to-Agent protocol is an open standard that defines how AI agents can discover, communicate, and collaborate with each other.

### Option 1: Local Testing

Test the agent locally in interactive mode:

```bash
cd ..
python ops_remediation_agent.py
```

This will:
- Create an ops orchestrator strands agent with web search and JIRA capabilities
- Wrap the agent to provide A2A protocol compatibility
- Dynamically construct the correct URL based on the deployment context using the agentcore `runtime` URL
- A2A servers run on port `9000` by default in AgentCore runtime

#### Test the A2A Server Locally

Once you run the command above, the A2A server for the ops orchestrator agent should be set up as follows:

```bash
🚀 Starting Ops Remediation Agent A2A Server on 127.0.0.1:9000
✅ A2A Server configured
📍 Server URL: http://127.0.0.1:9000
🏥 Health check: http://127.0.0.1:9000/health
🏓 Ping: http://127.0.0.1:9000/ping
INFO:     Started server process [52068]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:9000 (Press CTRL+C to quit)
```

Open another terminal and run the following command to send a request to the agent:

```bash
curl -X POST http://0.0.0.0:9000 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "req-001",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [
          {
            "kind": "text",
            "text": "Search for best practices for managing EC2 instance utilization"
          }
        ],
        "messageId": "d0673ab9-796d-4270-9435-451912020cd1"
      }
    }
  }' | jq .
```

This will search for best practices and provide recommendations.

#### Test the Agent Card Retrieval

Run the following command to retrieve the agent card of the server:

```bash
curl http://localhost:9000/.well-known/agent-card.json | jq .
```

Output:

```json
{
  "capabilities": {
    "streaming": true
  },
  "defaultInputModes": [
    "text"
  ],
  "defaultOutputModes": [
    "text"
  ],
  "description": "An operations orchestrator agent that searches for best practices, creates JIRA tickets, and provides infrastructure remediation guidance",
  "name": "ops_orchestrator_agent",
  "preferredTransport": "JSONRPC",
  "protocolVersion": "0.3.0",
  "skills": [
    {
      "description": "Search the web for AWS best practices and documentation",
      "id": "web_search",
      "name": "web_search",
      "tags": []
    },
    {
      "description": "Create JIRA tickets for infrastructure issues",
      "id": "create_jira_ticket",
      "name": "create_jira_ticket",
      "tags": []
    }
  ],
  "url": "http://127.0.0.1:9000/",
  "version": "1.0.0"
}
```

### Option 2: Deploy Your A2A Server to Bedrock AgentCore Runtime

To deploy this A2A server on `AgentCore` runtime, follow the steps below:

1. Make sure that the Amazon Bedrock `AgentCore` CLI is installed. The `uv` environment contains the required packages preinstalled. If not, then run the following command:

```bash
uv pip install bedrock-agentcore-starter-toolkit
```

2. **Set up Cognito user pool for authentication**: Use the OAuth information from Step 2. To configure your own IdP information to enable OAuth with the agent running on Runtime, see [Set up Cognito user pool for authentication](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp.html#set-up-cognito-user-pool-for-authentication) in the documentation.

3. **Configure your A2A server for deployment**

After setting up authentication, create the deployment configuration:

```bash
agentcore configure -e ops_remediation_agent.py --protocol A2A
```

5. **Deploy to AWS**

Deploy your agent to `AgentCore` runtime:

```bash
agentcore launch
```

6. **Fetch the agent card using OAuth 2.0**

Run the following script that will generate the access token to invoke the `agent card` URL:

```bash
cd ..
python retrieve_agent_card.py
```

This script will prompt you for:
1. Agent ARN (use the agent arn from the `.bedrock_agentcore.yaml` file)
2. OAuth 2.0 information (Discovery URL, allowed `client IDs`)

Once done, this script will generate the bearer token and invoke the agent running on `AgentCore` Runtime as an A2A server.

Now you should have an agent running as an A2A server on `AgentCore` Runtime that can search for best practices, create JIRA tickets, and provide remediation guidance.

## Next Steps

Navigate to the `A2A` directory to bring all agents together and enable agent-to-agent communication between the monitoring agent and ops orchestrator agent.
