# A2A Host Orchestrator Agent

This is a simplified A2A (Agent-to-Agent) host client that orchestrates communication between specialized agents running on Amazon Bedrock AgentCore runtimes.

## Overview

The host agent serves as an orchestrator that:

1. **Fetches IDP Configuration**: Retrieves Cognito OAuth configuration from AWS SSM Parameter Store
2. **Discovers Remote Agents**: Fetches agent capabilities from Bedrock AgentCore runtimes via agent cards
3. **Routes Requests**: Intelligently routes user queries to appropriate specialist agents
4. **Coordinates Tasks**: Manages multi-agent collaboration for incident response and operations

## Architecture

### Components

- **Host Agent** (`host_agent.py`): Single-file implementation containing:
  - Google ADK orchestrator for routing requests
  - SSM Parameter Store integration for IDP configuration
  - OAuth token management
  - A2A communication with remote agents
- **Configuration** (`config.yaml`): Simplified agent runtime configuration

### Available Specialist Agents

1. **Monitoring_Agent**: Monitors AWS logs/metrics/dashboards, manages CloudWatch alarms, creates Jira tickets
2. **OpsRemediation_Agent**: Searches for remediation strategies and provides AWS troubleshooting guidance

## Prerequisites

1. **Google AI API Key** - Required for Google Gemini model access
   - Get your API key from: https://aistudio.google.com/app/apikey
   - Copy `.env.template` to `.env` and add your API key:
     ```bash
     cp .env.template .env
     # Edit .env and add your GOOGLE_API_KEY
     ```

## Setup

### 1. Store IDP Configuration in SSM Parameter Store

For each agent, store the Cognito IDP configuration in SSM Parameter Store as a secure string:

```bash
# Upload monitoring agent IDP config
aws ssm put-parameter \
  --name "/a2a/agents/monitoring/idp-config" \
  --type "SecureString" \
  --value '{
    "user_pool_id": "",
    "client_id": "",
    "client_secret": "",
    "domain": "",
    "discovery_url": "https://cognito-idp.us-west-2.amazonaws.com//.well-known/openid-configuration",
    "resource_server_identifier": "monitoring-agentcore-gateway-id",
    "scopes": ["gateway:read", "gateway:write"]
  }' \
  --region us-west-2 \
  --overwrite

# Upload ops remediation agent IDP config
aws ssm put-parameter \
  --name "/a2a/agents/ops-remediation/idp-config" \
  --type "SecureString" \
  --value '{
    "user_pool_id": "",
    "client_id": "",
    "client_secret": "",
    "domain": "",
    "discovery_url": "https://cognito-idp.us-west-2.amazonaws.com//.well-known/openid-configuration",
    "resource_server_identifier": "operations-agentcore-gateway-id",
    "scopes": ["gateway:read", "gateway:write"]
  }' \
  --region us-west-2 \
  --overwrite
```

### 2. Configure Agents in config.yaml

Edit `config.yaml` to configure your runtime agents:

```yaml
# Host Orchestrator Configuration
model:
  id: gemini-2.0-flash
  name: Host_Orchestrator_Agent
  temperature: 0.1
  max_tokens: 2048

# Remote agents - IDP config fetched from SSM Parameter Store
agents:
  - name: Monitoring_Agent
    description: "Monitors AWS logs/metrics/dashboards, performs log analysis, manages CloudWatch alarms, and creates Jira tickets"
    runtime_arn: <provide the runtime arn>
    region: us-west-2
    ssm_idp_config_path: /a2a/agents/monitoring/idp-config

  - name: OpsRemediation_Agent
    description: "Searches for remediation strategies using web search and provides solutions for AWS-related issues"
    runtime_arn: <provide the runtime arn>
    region: us-west-2
    ssm_idp_config_path: /a2a/agents/ops-remediation/idp-config
```

### 3. Verify IAM Permissions

Ensure your IAM role/user has the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter"
      ],
      "Resource": "arn:aws:ssm:*:*:parameter/a2a/agents/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cognito-idp:*"
      ],
      "Resource": "*"
    }
  ]
}
```

## Usage

### CLI Interface

Run the host agent in CLI mode:

```bash
# From the multi-agents directory
cd multi-agents
python -m host
```

The agent will:
1. Discover available remote agents
2. Fetch IDP configuration from SSM for each agent
3. Obtain OAuth bearer tokens
4. Display agent capabilities
5. Accept user queries in an interactive loop

Example session:
```
You: Check CloudWatch metrics for errors in the last 24 hours

Orchestrator: I'll check the metrics for you...
[Contacting Monitoring_Agent...]
Found 3 errors in CloudWatch logs for service X...
```

### Google ADK Web Interface

For a web interface, use ADK:

```bash
cd multi-agents/host
adk web
```

This will start the Google ADK web interface where you can interact with the orchestrator.

### Programmatic Usage

```python
import asyncio
from host.host_agent import HostAgent

async def main():
    # Create and initialize host agent
    host_agent = await HostAgent.create()

    # Stream responses
    async for event in host_agent.stream(
        "Check CloudWatch for errors",
        session_id="my-session-123"
    ):
        if event.get("is_task_complete"):
            print(event.get("content"))

    # Cleanup
    await host_agent.close()

asyncio.run(main())
```

## A2A Protocol

The host agent implements the A2A protocol for agent-to-agent communication:

### Agent Discovery

Agents are discovered by fetching agent cards from:
```
https://{agent-id}.runtime.bedrock-agentcore.{region}.amazonaws.com/.well-known/agent-card.json
```

### Message Format

Messages use JSON-RPC 2.0 format:

```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"type": "text", "text": "Your task here"}],
      "messageId": "uuid",
      "contextId": "uuid"
    }
  }
}
```

### Authentication

- Uses OAuth 2.0 client credentials flow
- Bearer tokens obtained from AWS Cognito
- IDP configuration retrieved from SSM Parameter Store
- Tokens cached and refreshed automatically

## Security

### Security Benefits of SSM Parameter Store

1. **Centralized Secret Management**: IDP credentials stored securely in SSM
2. **Encryption at Rest**: All parameters stored as SecureString are encrypted
3. **Access Control**: IAM policies control who can read parameters
4. **Audit Trail**: CloudTrail logs all parameter access
5. **No Hardcoded Secrets**: Configuration file contains only SSM paths

### Authentication Flow

1. Host agent fetches IDP config from SSM Parameter Store (encrypted)
2. Client authenticates with Cognito using retrieved credentials
3. Receives bearer token with scoped permissions
4. Token included in Authorization header for runtime requests
5. Tokens automatically refreshed as needed

### Security Features

- **Transport Security**: All communications use HTTPS
- **Token-Based Authorization**: Fine-grained access control via OAuth scopes
- **Identity Isolation**: Each agent has its own identity context
- **Encrypted Configuration**: Cognito secrets stored encrypted in SSM

## Development

### Adding New Agents

1. Deploy agent to Bedrock AgentCore

2. Store IDP configuration in SSM:
```bash
aws ssm put-parameter \
  --name "/a2a/agents/my-agent/idp-config" \
  --type "SecureString" \
  --value '{"user_pool_id": "...", "client_id": "...", ...}' \
  --region us-west-2
```

3. Add agent configuration to `config.yaml`:
```yaml
agents:
  - name: MyNewAgent
    description: "Agent description"
    runtime_arn: arn:aws:bedrock-agentcore:region:account:runtime/agent-id
    region: us-west-2
    ssm_idp_config_path: /a2a/agents/my-agent/idp-config
```