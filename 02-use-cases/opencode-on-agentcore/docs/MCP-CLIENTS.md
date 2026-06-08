<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# MCP Clients

This document is the client-configuration guide for connecting to the deployed AgentCore Gateway. It covers the three supported authentication options, per-client config file locations for Kiro, Claude Desktop, and Cursor, and how to obtain a Cognito ID token for token-based auth.

## Endpoint URL

```
https://{gateway-id}.gateway.bedrock-agentcore.{region}.amazonaws.com/mcp
```

Find it in the `OpenCodeGateway` stack outputs (`GatewayUrl`).

## Authentication Options

Three ways to authenticate your MCP client, ranked by recommendation:

### Option A: Auto-refresh wrapper (recommended)

Uses [`scripts/mcp-opencode-client.sh`](../scripts/mcp-opencode-client.sh) to acquire a fresh Cognito JWT on every connection via `aws cognito-idp initiate-auth`, then pipes it through `npx mcp-remote` to proxy the MCP connection. No token is stored on disk.

**Prerequisites:**
- **Node.js** -- required for `npx mcp-remote@latest`
- **AWS CLI** -- used to call `cognito-idp initiate-auth`

**Required environment variables:**

| Variable | Source | Description |
|----------|--------|-------------|
| `COGNITO_CLIENT_ID` | `OpenCodeSecurity` stack output `UserPoolClientId`, or Cognito console under `opencode-user-pool` | Cognito User Pool Client ID |
| `COGNITO_USER` | Admin-provided | Cognito username (email) |
| `COGNITO_PASSWORD` | Admin-provided | Cognito password |
| `AWS_REGION` | Your deployment region | AWS region (e.g., `us-east-1`) |
| `OPENCODE_GATEWAY_URL` | `OpenCodeGateway` stack output `GatewayUrl` | Full Gateway MCP endpoint URL |
| `AWS_PROFILE` *(optional)* | Your `~/.aws/config` | AWS CLI profile; omit to use default credentials |

**Configuration example** (works for Kiro, Claude Desktop, and Cursor):

```json
{
  "opencode": {
    "command": "./scripts/mcp-opencode-client.sh",
    "env": {
      "COGNITO_CLIENT_ID": "<user-pool-client-id>",
      "COGNITO_USER": "user@example.com",
      "COGNITO_PASSWORD": "<password>",
      "OPENCODE_GATEWAY_URL": "https://<gateway-id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp",
      "AWS_REGION": "<region>"
    }
  }
}
```

**Security tradeoff:** No token on disk. The Cognito password is in the config file -- for production use, consider injecting credentials via environment variables or a system keychain instead of hardcoding them.

### Option B: Hardcoded token

Paste a Bearer token directly into the MCP client config. Simple to set up, but requires manual token refresh.

> **Security warning:** Cognito ID tokens expire after **24 hours** and must be manually refreshed. Pasting a token directly into the MCP client config writes it to disk in plaintext. Do not commit it to version control, paste it in screenshots, or share it in support tickets. Prefer **Option A** (auto-refresh wrapper, nothing on disk) or, for higher-assurance environments, a system keychain or secrets manager that injects the token at launch time rather than storing it in a plaintext config file.

**Configuration example:**

```json
{
  "opencode": {
    "url": "https://<gateway-id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp",
    "headers": {
      "Authorization": "Bearer <your-cognito-id-token>"
    }
  }
}
```

See [Obtaining a token](#obtaining-a-token-for-option-b) below for how to get the token value.

**Security tradeoff:** Token is stored in plaintext on disk and expires after 24 hours. Convenient for quick testing; not recommended for daily use.

### Option C: AWS IAM -- admin/operator (SigV4)

> **Note:** This option only works if the Gateway is configured with an IAM authorizer for inbound requests. The default deployment uses a Cognito JWT authorizer, so SigV4-signed requests from `mcp-proxy-for-aws` will be rejected with `401 Unauthorized`. Use Option A or Option B with the default deployment. Option C is documented here for deployments that add IAM inbound auth to the Gateway.

For operators and admins with AWS IAM credentials. Uses `mcp-proxy-for-aws` to handle SigV4 signing automatically -- no Cognito token needed.

**Configuration example:**

```json
{
  "opencode": {
    "command": "uvx",
    "args": [
      "mcp-proxy-for-aws@latest",
      "https://<gateway-id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp"
    ],
    "env": {
      "AWS_PROFILE": "<profile>",
      "AWS_REGION": "<region>"
    }
  }
}
```

**Security tradeoff:** Relies on your local AWS credential chain (profiles, SSO, instance roles). Appropriate for operators who already have AWS IAM access; not intended for end users.

## Client-specific config file locations

| Client | Config file | Notes |
|--------|------------|-------|
| **Kiro** | `.kiro/settings/mcp.json` (workspace) or `~/.kiro/settings/mcp.json` (user-level) | Supports `command` + `env` (Option A/C) and `url` + `headers` (Option B) |
| **Claude Desktop** | `claude_desktop_config.json` -- macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\` | Supports `command` + `env` (Option A/C) and `url` + `headers` (Option B) |
| **Cursor** | `.cursor/mcp.json` or via Settings UI | Supports `command` + `env` (Option A/C) and `url` + `headers` (Option B) |

All three clients support the stdio-based `"command"` + `"env"` pattern (Options A and C) and the direct HTTP `"url"` + `"headers"` pattern (Option B).

## Obtaining a token (for Option B)

If you choose Option B (hardcoded token), you need a Cognito ID token. Two ways to get one:

**Using the helper script:**

```bash
export COGNITO_USER=user@example.com
export COGNITO_PASSWORD='YourPassword123!@#'
export COGNITO_CLIENT_ID=<user-pool-client-id>
export AWS_REGION=us-east-1
./scripts/get-token.sh
```

**Using the AWS CLI directly:**

```bash
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id <user-pool-client-id> \
  --auth-parameters USERNAME=<email>,PASSWORD=<password> \
  --region <region> \
  --query 'AuthenticationResult.IdToken' --output text
```

The User Pool Client ID is in the `OpenCodeSecurity` stack outputs (`UserPoolClientId`), or find it in the Cognito console under the `opencode-user-pool` pool. Retrieve it with:

```bash
aws cloudformation describe-stacks --stack-name OpenCodeSecurity \
  --region <region> \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" --output text
```
