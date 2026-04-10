# Registry URL Synchronization

Auto-populate registry records by pointing to an MCP server or A2A agent URL. The registry connects to the endpoint, fetches metadata (tools, server info, agent card), and populates the record — no manual entry needed.

![image](image/image.png)

## Use Cases

| Use Case | Description |
|---|---|
| **Catalog existing MCP servers** | Point to a running MCP server and the registry imports all tools, descriptions, and schemas automatically |
| **Register A2A agents** | Provide an agent card URL and the registry extracts capabilities, skills, and metadata |
| **Keep records in sync** | Re-trigger sync to refresh records when the upstream server adds or changes tools |
| **Onboard OAuth-protected servers** | Sync from gateways that require Cognito or custom OAuth tokens |
| **Onboard IAM-protected servers** | Sync from gateways that use AWS SigV4 authentication |

## Supported Auth Modes

| Mode | When to Use | Credential Config |
|---|---|---|
| **No auth** | Public MCP servers, public A2A agent cards | None needed |
| **OAuth (CLIENT_CREDENTIALS)** | Cognito-protected or custom OAuth gateways | OAuth2 credential provider ARN + scopes |
| **IAM (SigV4)** | IAM-auth AgentCore gateways | IAM role ARN with `sts:AssumeRole` trust |

## Quick Start

### 1. Create a registry record with URL sync

```python
import boto3

cp = boto3.client("bedrock-agentcore-control", region_name="us-west-2")

# Public MCP server — no auth
cp.create_registry_record(
    registryId="<REGISTRY_ID>",
    name="my_mcp_server",
    descriptorType="MCP",
    synchronizationType="URL",
    synchronizationConfiguration={
        "fromUrl": {"url": "https://knowledge-mcp.global.api.aws"}
    },
)
```

The record transitions: `CREATING` → `DRAFT` (success) or `CREATE_FAILED` (error).

### 2. Check the result

```python
record = cp.get_registry_record(registryId="<REGISTRY_ID>", recordId="<RECORD_ID>")
print(f"Status: {record['status']}")
print(f"Name: {record['name']}")  # Auto-populated from server info
```

### 3. Re-sync an existing record

```python
cp.update_registry_record(
    registryId="<REGISTRY_ID>",
    recordId="<RECORD_ID>",
    synchronizationConfiguration={
        "optionalValue": {"fromUrl": {"url": "https://knowledge-mcp.global.api.aws"}}
    },
    triggerSynchronization=True,
)
```

## Examples

### Public MCP Server

```python
cp.create_registry_record(
    registryId=REGISTRY_ID,
    name="aws_docs_mcp",
    descriptorType="MCP",
    synchronizationType="URL",
    synchronizationConfiguration={
        "fromUrl": {"url": "https://knowledge-mcp.global.api.aws"}
    },
)
# Result: 6 tools auto-populated, name updated to "AWSDocumentationMCPProdGateway"
```

### A2A Agent Card

```python
cp.create_registry_record(
    registryId=REGISTRY_ID,
    name="willform_agent",
    descriptorType="A2A",
    synchronizationType="URL",
    synchronizationConfiguration={
        "fromUrl": {"url": "https://agent.willform.ai/.well-known/agent-card.json"}
    },
)
# Result: Agent card descriptor auto-populated, name updated to "Willform Agent"
```

### OAuth-Protected MCP Gateway

```python
cp.create_registry_record(
    registryId=REGISTRY_ID,
    name="protected_mcp",
    descriptorType="MCP",
    synchronizationType="URL",
    synchronizationConfiguration={
        "fromUrl": {
            "url": "<GATEWAY_MCP_URL>",
            "credentialProviderConfigurations": [{
                "credentialProviderType": "OAUTH",
                "credentialProvider": {
                    "oauthCredentialProvider": {
                        "providerArn": "<OAUTH_PROVIDER_ARN>",
                        "grantType": "CLIENT_CREDENTIALS",
                        "scopes": ["mcp-gateway/invoke"],
                    }
                }
            }]
        }
    },
)
```

### IAM-Protected MCP Gateway

```python
cp.create_registry_record(
    registryId=REGISTRY_ID,
    name="iam_mcp",
    descriptorType="MCP",
    synchronizationType="URL",
    synchronizationConfiguration={
        "fromUrl": {
            "url": "<GATEWAY_MCP_URL>",
            "credentialProviderConfigurations": [{
                "credentialProviderType": "IAM",
                "credentialProvider": {
                    "iamCredentialProvider": {
                        "roleArn": "<IAM_SYNC_ROLE_ARN>",
                        "service": "bedrock-agentcore",
                        "region": "us-west-2",
                    }
                }
            }]
        }
    },
)
```

## Gateway Configuration for URL Sync

When syncing from an AgentCore Gateway, the gateway must support MCP version `2025-03-26`. The registry sync service does not send the `Mcp-Protocol-Version` header, so the gateway defaults to `2025-03-26`.

Set `supportedVersions` to include both versions when creating the gateway:

```python
ac.create_gateway(
    name="my-gateway",
    protocolType="MCP",
    protocolConfiguration={
        "mcp": {"supportedVersions": ["2025-03-26", "2025-11-25"]}
    },
    authorizerType="CUSTOM_JWT",
    authorizerConfiguration={...},
    roleArn="...",
)
```

> **Without this**, sync requests to the gateway fail with: `Unsupported MCP protocol version: 2025-03-26`

## Error Handling

| Status | Meaning | Recovery |
|---|---|---|
| `DRAFT` | Sync succeeded, record ready for review | Submit for approval |
| `CREATE_FAILED` | Initial sync failed | Update with correct URL + `triggerSynchronization=True` |
| `SYNC_FAILED` | Re-sync failed | Check `statusReason`, fix URL or credentials, re-trigger |

Failed records include a `statusReason` field with the error details (e.g., connection timeout, auth failure, invalid response).

## Governance Flow

URL-synced records follow the same approval workflow as manually created records:

```
CREATING → DRAFT → SUBMITTED → APPROVED → (searchable via data plane)
                                    ↓
                              Re-sync → DRAFT (new revision, old stays searchable)
```

## Prerequisites

### 1. Python dependencies

```bash
pip install "boto3>=1.42.87"
```

> With boto3 >= 1.42.87, the Agent Registry APIs are included natively — no custom endpoints or bundled wheels needed.

### 2. IAM Policy

Attach the following policy to the IAM user or role creating/syncing records. Replace `ACCOUNT_ID` and `REGION`.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "RegistryRecordManagement",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:CreateRegistryRecord",
                "bedrock-agentcore:GetRegistryRecord",
                "bedrock-agentcore:UpdateRegistryRecord",
                "bedrock-agentcore:ListRegistryRecords",
                "bedrock-agentcore:DeleteRegistryRecord"
            ],
            "Resource": [
                "arn:aws:bedrock-agentcore:REGION:ACCOUNT_ID:registry/*",
                "arn:aws:bedrock-agentcore:REGION:ACCOUNT_ID:registry/*/record/*"
            ]
        },
        {
            "Sid": "RegistryManagement",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:CreateRegistry",
                "bedrock-agentcore:GetRegistry",
                "bedrock-agentcore:ListRegistries"
            ],
            "Resource": "arn:aws:bedrock-agentcore:REGION:ACCOUNT_ID:*"
        },
        {
            "Sid": "OAuthTokenForSync",
            "Effect": "Allow",
            "Action": "bedrock-agentcore:GetResourceOauth2Token",
            "Resource": "arn:aws:bedrock-agentcore:REGION:ACCOUNT_ID:token-vault/*/oauth2credentialprovider/*"
        },
        {
            "Sid": "IAMPassRoleForSync",
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "arn:aws:iam::ACCOUNT_ID:role/*",
            "Condition": {
                "StringEquals": {
                    "iam:PassedToService": "bedrock-agentcore.amazonaws.com"
                }
            }
        }
    ]
}
```

- `GetResourceOauth2Token` — required only for OAuth-protected URL sync
- `iam:PassRole` — required only for IAM-protected URL sync
- Omit the last two statements if you only sync from public (no-auth) endpoints

### 3. New registry required

Registries created before the URL sync feature was deployed lack the workload identity needed for credential resolution. **Create a new registry** to use OAuth or IAM sync.

## Files in This Folder

| File | Description |
|---|---|
| `url_synchronization.ipynb` | Interactive notebook covering all sync scenarios end-to-end |
| `README.md` | This guide |
