# Connecting GitHub MCP Server to AgentCore gateway

## Overview

[GitHub's MCP server](https://github.com/github/github-mcp-server) exposes repository search, user lookup, workflow management, and more as MCP tools — but it requires OAuth authorization code flow for authentication. AgentCore gateway handles this complexity transparently: admin users authorize once during target creation, and all subsequent tool invocations reuse cached credentials.

This tutorial shows how to attach the GitHub MCP server to AgentCore gateway using:

- **Method 1** (Implicit sync): Admin completes the authorization code flow during target creation. gateway discovers and caches tools automatically.
- **Method 2** (Schema upfront): Admin provides the tool schema directly. No OAuth flow needed during creation — recommended for IaC pipelines.

Both methods enable gateway users to browse the full tool catalog without authenticating. The authorization code flow is only triggered when a user invokes a tool.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed
- Node.js >= 22.7.5
- [AgentCore CLI](https://www.npmjs.com/package/@aws/agentcore): `npm install -g @aws/agentcore`
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured with credentials (`aws configure`)
- [IAM permissions](https://github.com/aws/agentcore-cli/blob/main/docs/PERMISSIONS.md)
- A GitHub OAuth App ([create one here](https://github.com/settings/apps))

## Deployment Steps

> [!IMPORTANT]
> All commands in this tutorial run from the [`gatewaylabproject/`](../../../../../../gatewaylabproject/) directory. Navigate there before proceeding.

### Step 1: Setup GitHub OAuth App

Create a [GitHub OAuth App](https://docs.github.com/en/apps/oauth-apps/using-oauth-apps) and note the Client ID and Client Secret. Export them as environment variables:

```bash
export GITHUB_CLIENT_ID="<your-github-client-id>"
export GITHUB_CLIENT_SECRET="<your-github-client-secret>"
```

### Step 2: Create GitHub Credential Provider

This creates the credential provider and outputs the callback URL you must register with your GitHub OAuth App:

```bash
uv run python scripts/github-auth-code/deploy_credential.py
```

After running, update your GitHub App's **Authorization callback URL** with the URL printed by the script.

### Step 3: Create AgentCore gateway (boto3)

The gateway requires `supportedVersions: ["2025-11-25"]` for URL-mode elicitation (authorization code flow). This is not supported by the AgentCore CLI, so we create it via boto3:

```bash
export COGNITO_STACK_NAME="agentcore-gateway-lab"
uv run python scripts/github-auth-code/deploy_gateway.py
```

The script creates the gateway with Cognito inbound auth, semantic search, and MCP version `2025-11-25`. It outputs the gateway ID and URL (also saved to `.env`).

Capture the gateway URL for the demo:

```bash
export GATEWAY_URL=$(cat scripts/github-auth-code/.env | grep GATEWAY_URL | cut -d= -f2)
echo "gateway URL: $GATEWAY_URL"
```

### Step 4: Create gateway Target

Choose one method:

#### Method 1: Implicit sync (admin authorizes during creation)

**Terminal 1** — create the target (prints User ID and Authorization URL):

```bash
uv run python scripts/github-auth-code/deploy_target_implicit.py
```

![wait](../images/need-auth.png)

**Terminal 2** — start the callback server with the User ID and Authorization URL from above. It opens the URL in your browser and waits for the redirect:

```bash
uv run python scripts/github-auth-code/callback_server.py \
  --user-id "<User ID printed above>" \
  --auth-url "<Authorization URL printed above>"
```

Authorize GitHub in your browser. The callback server completes session binding automatically and exits. The target becomes `READY` with cached tools.

![ready](../images/complete-implicit.png)

#### Method 2: Schema upfront (no admin auth needed)

In this method [GitHub schema](./github.json) is provided.  

```bash
uv run python scripts/github-auth-code/deploy_target_schema.py
```

![upfront](../images/complete-schema.png)

The target becomes immediately `READY`. Users will be prompted to authorize GitHub on their first tool invocation via URL-mode elicitation.

### Step 5: Verify

```bash
agentcore status
```

## Demo

> [!TIP]
> Use the [AgentCore gateway MCP Inspector](../../../../../../05-community/gateway-mcp-inspector/) to explore GitHub tools interactively. The Inspector handles the URL-mode elicitation flow (opens the authorization URL, completes session binding) automatically.

![demo](./images/demo.gif)

### Option 1: Invoke Script

**Terminal 1** — invoke the gateway (lists tools, calls `search_repositories`):

```bash
uv run python scripts/github-auth-code/invoke.py
```


On first tool invocation, the script prints a URL elicitation with an Authorization URL and a session URI.

**Terminal 2** — start the callback server with the Cognito access token (for user-level session binding):

```bash
uv run python scripts/github-auth-code/callback_server.py \
  --user-token "<cognito-access-token>" \
  --auth-url "<Authorization URL from invoke output>"
```

Authorize GitHub in your browser. The callback server completes session binding. Then run `invoke.py` again — the tool call succeeds with cached credentials.

![invoke](../images/invoke.png)

```json
{
  "error": {
    "code": -32042,
    "message": "This request requires more information.",
    "data": {
      "elicitations": [{
        "mode": "url",
        "url": "<authorization-url>",
        "message": "Please login to this URL for authorization."
      }]
    }
  }
}
```

## Cleanup

> [!IMPORTANT]
> Clean up this tutorial before starting another. Leftover resources can cause conflicts with other tutorials.

Delete all resources (targets, gateway, IAM role, credential provider):

```bash
uv run python scripts/github-auth-code/cleanup.py
```

Delete the Cognito stack (if no longer needed by other tutorials):

```bash
aws cloudformation delete-stack --stack-name $COGNITO_STACK_NAME
```

## Documentation

- [AgentCore gateway Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
- [Authorization Code Flow](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-outbound-auth.html)
- [URL Session Binding](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/oauth2-authorization-url-session-binding.html)
