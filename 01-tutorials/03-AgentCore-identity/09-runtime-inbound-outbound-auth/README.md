# AgentCore Identity: Runtime Inbound and Outbound Auth (Cognito)

## Overview

This sample shows how to secure an **AgentCore Runtime** agent with both inbound and outbound authentication using Amazon Cognito as the Identity Provider (IdP).

- **Inbound Auth**: The runtime endpoint is protected by a Cognito JWT. Callers must present a valid bearer token or receive `AccessDeniedException`.
- **Outbound Auth**: The agent retrieves an API key from AgentCore Identity (backed by AWS Secrets Manager) at runtime. The key is never stored in environment variables or agent code.

### Architecture

```
Caller
  │  Authorization: Bearer <Cognito JWT>
  ▼
AgentCore Runtime  ──validates JWT──▶  Cognito User Pool
  │
  │  @requires_api_key("OutboundApiKey")
  ▼
AgentCore Identity  ──fetches secret──▶  AWS Secrets Manager
  │
  ▼
External API (weather service, OpenAI, etc.)
```

### Tutorial Details

| Information         | Details                                               |
|:--------------------|:------------------------------------------------------|
| Tutorial type       | CLI walkthrough                                       |
| Agent type          | Single                                                |
| Agentic Framework   | Strands Agents                                        |
| LLM model           | Anthropic Claude Haiku 4.5                            |
| Inbound Auth        | Amazon Cognito (CUSTOM_JWT)                           |
| Outbound Auth       | AgentCore Identity - API Key credential provider      |
| Example complexity  | Easy                                                  |
| CLI tool            | `agentcore` (npm: `@aws/agentcore`)                   |

---

## Prerequisites

- **Node.js** 20.x or later
- **Python** 3.10+
- **uv** ([install](https://docs.astral.sh/uv/getting-started/installation/))
- **AWS credentials** configured (`aws configure` or environment variables)
- **AgentCore CLI** installed:

```bash
npm install -g @aws/agentcore
```

- **Amazon Bedrock model access**: Enable `claude-haiku-4-5` in the [Bedrock console](https://console.aws.amazon.com/bedrock/home#/models)

---

## Step 1: Install Setup Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 2: Set Up Cognito (Inbound IdP)

```bash
python setup_cognito.py
```

This creates:
- A Cognito User Pool with one test user (`testuser` / `AgentCoreTest1!`)
- An App Client with `USER_PASSWORD_AUTH` enabled
- Saves pool ID, client ID, and discovery URL to `cognito_config.json`

Take note of the two values printed at the end — you will need them in Step 5:

```
discoveryUrl : https://cognito-idp.<region>.amazonaws.com/<pool_id>/.well-known/openid-configuration
allowedClients: ["<client_id>"]
```

---

## Step 3: Create the AgentCore Project

```bash
agentcore create --name RuntimeAuthDemo --defaults --no-agent
cd RuntimeAuthDemo
```

---

## Step 4: Add the Agent (Bring Your Own Code)

```bash
agentcore add agent \
  --name MyAgent \
  --type byo \
  --code-location ../app/MyAgent \
  --entrypoint main.py \
  --language Python \
  --framework Strands \
  --model-provider Bedrock
```

---

## Step 5: Add Outbound Identity Credential

Store the API key that the agent will use to call an external service:

```bash
agentcore add identity \
  --name OutboundApiKey \
  --api-key YOUR_API_KEY_HERE
```

> Replace `YOUR_API_KEY_HERE` with the actual API key for your downstream service (e.g., OpenAI, weather API). The CLI stores it securely in AWS Secrets Manager via AgentCore Identity.

---

## Step 6: Configure Inbound JWT Auth

Open `agentcore/agentcore.json` and add the `authorizationConfiguration` block to your agent spec. Replace the placeholder values with the `discoveryUrl` and `client_id` from Step 2:

```json
{
  "name": "RuntimeAuthDemo",
  "version": 1,
  "agents": [
    {
      "type": "AgentCoreRuntime",
      "name": "MyAgent",
      "build": "CodeZip",
      "entrypoint": "main.py",
      "codeLocation": "app/MyAgent/",
      "runtimeVersion": "PYTHON_3_12",
      "authorizationConfiguration": {
        "authorizationType": "CUSTOM_JWT",
        "customJWTAuthorizer": {
          "discoveryUrl": "YOUR_COGNITO_DISCOVERY_URL",
          "allowedClients": ["YOUR_COGNITO_CLIENT_ID"]
        }
      }
    }
  ],
  "memories": [],
  "credentials": [
    {
      "type": "ApiKeyCredentialProvider",
      "name": "OutboundApiKey"
    }
  ],
  "evaluators": [],
  "onlineEvalConfigs": []
}
```

---

## Step 7: Deploy

```bash
agentcore deploy -y
```

Deployment takes a few minutes. Monitor progress:

```bash
agentcore status
```

---

## Step 8: Test Inbound and Outbound Auth

Go back to the sample root directory and run the invoke script:

```bash
cd ..
python invoke.py "What is the weather in Seattle?"
```

The script runs two tests:

1. **Without bearer token** — expects `AccessDeniedException`
2. **With valid Cognito bearer token** — expects a successful agent response

Expected output:

```
[Test 1] Invoking WITHOUT bearer token (expect AccessDeniedException)...
  Correctly rejected: An error occurred (AccessDeniedException) ...

[Test 2] Invoking WITH valid Cognito bearer token...
  Token obtained (first 20 chars): eyJraWQiOiJxT...

Agent response:
The weather in Seattle is currently Sunny, 72F.
```

---

## Step 9: Cleanup

```bash
cd RuntimeAuthDemo
agentcore remove agent --name MyAgent --force
agentcore remove identity --name OutboundApiKey --force
```

Delete Cognito resources:

```python
import boto3, json

with open("../cognito_config.json") as f:
    config = json.load(f)

boto3.client("cognito-idp", region_name=config["region"]).delete_user_pool(
    UserPoolId=config["pool_id"]
)
print("Cognito User Pool deleted.")
```

---

## Key Concepts

| Concept | How it works in this sample |
|:--------|:---------------------------|
| **Inbound JWT validation** | AgentCore Runtime checks `Authorization: Bearer <token>` against the Cognito JWKS endpoint before executing the agent |
| **Outbound API key** | `@requires_api_key(provider_name="OutboundApiKey")` calls `bedrock-agentcore:GetResourceApiKey` + `secretsmanager:GetSecretValue` at runtime |
| **Zero-secret agent code** | API keys live in Secrets Manager; agent code only sees them in-memory via the decorator |

## Next Steps

- [Gateway Inbound and Outbound Auth](../10-gateway-inbound-outbound-auth/) — protect a Gateway endpoint and add OAuth outbound auth to upstream targets
- [M2M and Auth Code flows](../11-m2m-authcode-runtime/) — client credentials (2LO) and authorization code (3LO) flows
- [EntraID IDP examples](../08-IDP-examples/EntraID/) — replace Cognito with Microsoft Entra ID
