# OAuth-Protected MCP Server Targets

## Overview

This tutorial demonstrates how to connect AgentCore Gateway to OAuth-protected MCP servers (like GitHub and Atlassian) using Authorization Code Grant (3LO). It covers both inbound authentication (how users/agents authenticate to the gateway) and outbound authentication (how the gateway accesses upstream providers on behalf of users).

Two authentication methods are provided:

| Method | Notebook | Client Secret Required | Best For |
|--------|----------|----------------------|----------|
| **PKCE** | `01-pkce-github.ipynb` | No | MCP clients, IDE integration, CLI testing |
| **Agent-Mediated** | `02-agent-mediated-github.ipynb` | Yes | Production agents, SPA backends |

Both methods produce a Cognito access token that the gateway validates via `allowedClients`. The gateway then handles the outbound 3LO flow (user consent, token caching, automatic refresh) transparently.

## How It Works

### Inbound Auth (User → Gateway)

The gateway uses `CUSTOM_JWT` authorizer with `allowedClients` to validate the `client_id` claim in Cognito access tokens. This works with both PKCE (public client) and agent-mediated (confidential client) flows.

### Outbound Auth (Gateway → GitHub/Atlassian)

When a tool is called, the gateway checks the token vault for a cached 3LO token for the user (`sub` claim). If none exists, it returns an elicitation URL (error code `-32042`). The user consents in a browser, and `complete-resource-token-auth` binds the 3LO token to their identity. Subsequent calls use the cached token automatically.

## Prerequisites

- Python 3.10+
- AWS credentials with permissions for `bedrock-agentcore`, `bedrock-agentcore-control`, `cognito-idp`
- GitHub OAuth App ([create one](https://github.com/settings/developers))
- `boto3`, `jq` installed

### GitHub OAuth App Setup

1. Go to https://github.com/settings/developers → OAuth Apps → New OAuth App
2. Fill in:
   - Application name: `AgentCore Gateway GitHub MCP`
   - Homepage URL: `https://github.com`
   - Authorization callback URL: placeholder (updated by the notebook)
3. Save the **Client ID** and **Client Secret**

## Tutorial Details

| Information | Details |
|:---|:---|
| Tutorial type | Interactive |
| Agent type | MCP Client / Agent |
| AgentCore components | AgentCore Gateway, AgentCore Identity |
| LLM model | N/A |
| Tutorial components | AgentCore Gateway with GitHub MCP Server target (3LO) |
| Tutorial vertical | Cross-vertical |
| Example complexity | Medium |
| SDK used | boto3 |
| Credential Provider | Type: OAuth2 - GitHub Provider |

## Files

| File | Description |
|------|-------------|
| `01-pkce-github.ipynb` | PKCE flow — browser login, no client secret |
| `02-agent-mediated-github.ipynb` | Agent-mediated flow — AgentCore Identity federated token |
| `oauth2_callback_server.py` | Callback server for 3LO session binding |
| `requirements.txt` | Python dependencies |

## Using Other Providers

The same pattern works with any OIDC provider (Okta, Auth0, Microsoft Entra) and any OAuth-protected MCP server. The key differences are:

| Provider | Client ID claim | Gateway config |
|----------|----------------|----------------|
| Cognito | `client_id` | `allowedClients` |
| Okta | `cid` | `customClaims` |
| Microsoft Entra | `azp` | `customClaims` |
| Auth0 | `azp` | `customClaims` |
