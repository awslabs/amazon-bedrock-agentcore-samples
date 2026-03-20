# CIMD (Client ID Metadata Document) OAuth Flow Documentation

## Table of Contents

1. [Overview](#overview)
2. [What is CIMD?](#what-is-cimd)
3. [Architecture Overview](#architecture-overview)
4. [The Two OAuth Flows](#the-two-oauth-flows)
5. [Detailed Flow Diagrams](#detailed-flow-diagrams)
6. [Technical Implementation](#technical-implementation)
7. [Key Components](#key-components)
8. [Token Management](#token-management)
9. [Troubleshooting](#troubleshooting)

---

## Overview

This document explains the **CIMD (Client ID Metadata Document) OAuth flow** used in the VS Code + AgentCore Gateway integration. This implementation enables **dynamic client registration** using a serverless architecture on AWS, supporting both **inbound authentication** (VS Code → AgentCore Gateway) and **outbound authentication** (AgentCore Gateway → Atlassian Confluence).

**Key Innovation**: Instead of using a pre-registered client_id string, CIMD uses a **URL as the client_id** that points to a JSON document describing the OAuth client configuration. This enables dynamic, self-describing OAuth clients.

---

## What is CIMD?

### Traditional OAuth 2.0

In traditional OAuth 2.0, the client_id is a **static string** that must be pre-registered with the authorization server:

```json
{
  "client_id": "abc123xyz",
  "redirect_uri": "http://localhost:8080/callback"
}
```

The authorization server maintains a registry of these client_ids and their associated configurations.

### CIMD (Client ID Metadata Document)

With CIMD, the client_id is a **URL** that points to a JSON document containing the client's metadata:

```json
{
  "client_id": "https://example.com/.well-known/client-metadata.json"
}
```

When the authorization server receives this URL as a client_id, it:

1. **Fetches** the JSON document from the URL
2. **Parses** the client configuration (redirect URIs, grant types, etc.)
3. **Dynamically registers** or validates the client
4. **Proceeds** with the OAuth flow

### CIMD Metadata Document Structure

A CIMD document (referenced by the client_id URL) contains:

```json
{
  "redirect_uris": [
    "http://localhost:8080/callback",
    "https://my-app.example.com/callback"
  ],
  "grant_types": ["authorization_code", "refresh_token"],
  "response_types": ["code"],
  "client_name": "My OAuth Client",
  "token_endpoint_auth_method": "none"
}
```

### Benefits of CIMD

| Aspect                    | Traditional OAuth                | CIMD                         |
| ------------------------- | -------------------------------- | ---------------------------- |
| **Client Registration**   | Manual pre-registration required | Automatic via URL resolution |
| **Configuration Updates** | Must update auth server          | Update JSON at URL           |
| **Portability**           | Client_id tied to auth server    | Client_id is self-contained  |
| **Deployment**            | Complex multi-step setup         | Deploy and use immediately   |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           VS Code with Copilot                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  CIMD Client                                                        │ │
│  │  client_id = "https://api-gw.amazonaws.com/.well-known/..."       │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ MCP over HTTP
                               │ OAuth with CIMD
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        AWS API Gateway + Lambda                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  MCP Proxy Lambda (mcp_proxy_lambda.py)                          │  │
│  │  • OAuth metadata server (.well-known endpoints)                 │  │
│  │  • CIMD resolution (fetch + parse client metadata)               │  │
│  │  • Dynamic Cognito client creation                               │  │
│  │  • Token proxying                                                 │  │
│  │  • MCP request forwarding                                         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Callback Lambda (callback_lambda.py)                            │  │
│  │  • 3LO OAuth callback handling                                    │  │
│  │  • CompleteResourceTokenAuth API calls                           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────┬──────────────────────────────────────┬─────────────────┘
               │                                       │
               │ Inbound Auth                          │ 3LO Callback
               ▼                                       ▼
┌─────────────────────────┐              ┌──────────────────────────────┐
│  Amazon Cognito         │              │  AgentCore Identity          │
│  User Pool              │              │  CompleteResourceTokenAuth   │
│  • JWT token issuance   │              └──────────────────────────────┘
│  • Dynamic clients      │
└─────────────────────────┘
               │
               │ JWT Token
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Amazon Bedrock AgentCore Gateway                     │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  • MCP server implementation                                      │  │
│  │  • JWT authentication                                             │  │
│  │  • 3LO elicitation (-32042 error)                                │  │
│  │  • Token caching and refresh                                      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ OAuth 2.0 3LO
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Atlassian Confluence                             │
│  • OAuth 2.0 Authorization Server                                        │
│  • Resource API (REST API v2)                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## The Two OAuth Flows

This architecture implements **two distinct OAuth flows** serving different purposes:

### 1. Inbound Authentication (VS Code → AgentCore Gateway)

**Purpose**: Authenticate VS Code user to access AgentCore Gateway

**OAuth Provider**: Amazon Cognito

**Flow Type**: Authorization Code Grant with CIMD

**Key Steps**:

1. VS Code uses CIMD client_id (URL to metadata document)
2. MCP Proxy Lambda resolves CIMD URL and fetches metadata
3. Lambda creates/finds Cognito user pool client dynamically
4. User authenticates via Cognito (username/password)
5. Cognito issues JWT access token
6. VS Code includes JWT in all MCP requests

### 2. Outbound Authentication (AgentCore Gateway → Confluence)

**Purpose**: AgentCore Gateway accesses Confluence API on behalf of user

**OAuth Provider**: Atlassian (Confluence)

**Flow Type**: Three-Legged OAuth (3LO) - Authorization Code Grant

**Key Steps**:

1. AgentCore Gateway detects missing Confluence token
2. Returns `-32042` elicitation error with authorization URL
3. User grants consent in browser
4. Atlassian redirects to Callback Lambda with authorization code
5. Callback Lambda calls `CompleteResourceTokenAuth`
6. AgentCore caches tokens and auto-refreshes

| Aspect             | Inbound Auth         | Outbound Auth (3LO)           |
| ------------------ | -------------------- | ----------------------------- |
| **Direction**      | VS Code → Gateway    | Gateway → Confluence          |
| **OAuth Provider** | Cognito              | Atlassian                     |
| **CIMD Used**      | ✅ Yes               | ❌ No                         |
| **When**           | MCP connection setup | First Confluence tool call    |
| **Token Type**     | JWT (short-lived)    | Access + Refresh (long-lived) |
| **Managed By**     | MCP Proxy Lambda     | AgentCore Identity            |

---

## Detailed Flow Diagrams

### Flow 1: Initial Connection with CIMD Resolution

```
┌──────────┐         ┌─────────────┐         ┌─────────┐         ┌─────────────┐
│ VS Code  │         │ MCP Proxy   │         │ Cognito │         │   AgentCore │
│          │         │   Lambda    │         │         │         │   Gateway   │
└────┬─────┘         └──────┬──────┘         └────┬────┘         └──────┬──────┘
     │                      │                     │                     │
     │ 1. Initialize MCP    │                     │                     │
     │─────────────────────>│                     │                     │
     │                      │                     │                     │
     │ 2. GET /.well-known/oauth-authorization-server                   │
     │─────────────────────>│                     │                     │
     │                      │                     │                     │
     │ 3. Metadata response │                     │                     │
     │<─────────────────────│                     │                     │
     │ {authorization_endpoint, token_endpoint, ...}                    │
     │                      │                     │                     │
     │ 4. GET /authorize    │                     │                     │
     │    client_id=https://api.../metadata.json  │                     │
     │─────────────────────>│                     │                     │
     │                      │                     │                     │
     │                      │ 5. FETCH CIMD      │                     │
     │                      │    GET https://api.../metadata.json       │
     │                      │    (fetches client metadata)              │
     │                      │                     │                     │
     │                      │ 6. Parse metadata  │                     │
     │                      │    {redirect_uris, grant_types, ...}      │
     │                      │                     │                     │
     │                      │ 7. Create/find Cognito client             │
     │                      │────────────────────>│                     │
     │                      │    CreateUserPoolClient                   │
     │                      │    CallbackURLs from CIMD                 │
     │                      │                     │                     │
     │                      │ 8. Cognito client_id                      │
     │                      │<────────────────────│                     │
     │                      │                     │                     │
     │ 9. 302 Redirect to Cognito /authorize     │                     │
     │<─────────────────────│    (with Cognito client_id)               │
     │                      │    (state encodes original redirect_uri)  │
     │                      │                     │                     │
     │ 10. User authenticates                     │                     │
     │──────────────────────────────────────────>│                     │
     │                      │                     │                     │
     │ 11. 302 Redirect to /callback with code    │                     │
     │<──────────────────────────────────────────│                     │
     │                      │                     │                     │
     │ 12. GET /callback    │                     │                     │
     │    code=xxx          │                     │                     │
     │─────────────────────>│                     │                     │
     │                      │                     │                     │
     │                      │ 13. Decode state   │                     │
     │                      │     Extract original redirect_uri         │
     │                      │                     │                     │
     │ 14. 302 Redirect to VS Code callback       │                     │
     │<─────────────────────│                     │                     │
     │                      │                     │                     │
     │ 15. POST /token      │                     │                     │
     │    code=xxx          │                     │                     │
     │─────────────────────>│                     │                     │
     │                      │                     │                     │
     │                      │ 16. POST /oauth2/token                    │
     │                      │────────────────────>│                     │
     │                      │                     │                     │
     │                      │ 17. JWT token      │                     │
     │                      │<────────────────────│                     │
     │                      │                     │                     │
     │ 18. JWT token        │                     │                     │
     │<─────────────────────│                     │                     │
     │                      │                     │                     │
     │ 19. POST /mcp        │                     │                     │
     │    Authorization: Bearer JWT               │                     │
     │─────────────────────>│                     │                     │
     │                      │                     │                     │
     │                      │ 20. Forward to AgentCore Gateway          │
     │                      │    Authorization: Bearer JWT              │
     │                      │─────────────────────────────────────────>│
     │                      │                     │                     │
     │ 21. MCP response     │                     │                     │
     │<──────────────────────────────────────────────────────────────────│
     │                      │                     │                     │
```

### Flow 2: 3LO Elicitation and Completion

```
┌──────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌──────────┐
│ VS Code  │   │ MCP Proxy   │   │  AgentCore  │   │  Callback   │   │Atlassian │
│          │   │   Lambda    │   │   Gateway   │   │   Lambda    │   │          │
└────┬─────┘   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘   └────┬─────┘
     │                │                  │                  │               │
     │ 1. Call Confluence tool (first time)                 │               │
     │────────────────>│                  │                  │               │
     │  Authorization: Bearer JWT         │                  │               │
     │                │                  │                  │               │
     │                │ 2. Forward request                  │               │
     │                │─────────────────>│                  │               │
     │                │                  │                  │               │
     │                │                  │ 3. No Confluence token           │
     │                │                  │    Generate 3LO URL              │
     │                │                  │                  │               │
     │                │ 4. -32042 Elicitation               │               │
     │                │<─────────────────│                  │               │
     │                │ {                │                  │               │
     │                │   "error": {     │                  │               │
     │                │     "code": -32042,                 │               │
     │                │     "data": {    │                  │               │
     │                │       "elicitations": [{            │               │
     │                │         "mode": "url",              │               │
     │                │         "url": "https://bedrock...",│               │
     │                │         "elicitationId": "..."      │               │
     │                │       }]         │                  │               │
     │                │     }            │                  │               │
     │                │   }              │                  │               │
     │                │ }                │                  │               │
     │                │                  │                  │               │
     │                │ 5. Store JWT for 3LO               │               │
     │                │─────────────────────────────────────>│               │
     │                │  POST /userIdentifier/token         │               │
     │                │                  │                  │               │
     │ 6. Elicitation response           │                  │               │
     │<────────────────│                  │                  │               │
     │                │                  │                  │               │
     │ 7. User opens URL in browser      │                  │               │
     │────────────────────────────────────────────────────────────────────>│
     │                │                  │                  │               │
     │ 8. User grants consent on Atlassian                  │               │
     │<────────────────────────────────────────────────────────────────────│
     │                │                  │                  │               │
     │ 9. 302 Redirect to Callback Lambda                   │               │
     │   GET /oauth2/callback?code=xxx&session_id=...       │               │
     │──────────────────────────────────────────────────────>│               │
     │                │                  │                  │               │
     │                │                  │ 10. CompleteResourceTokenAuth    │
     │                │                  │<─────────────────│               │
     │                │                  │  sessionUri=session_id           │
     │                │                  │  userIdentifier={userToken: JWT} │
     │                │                  │                  │               │
     │                │                  │ 11. Store tokens │               │
     │                │                  │  (access + refresh)              │
     │                │                  │                  │               │
     │ 12. Success HTML page             │                  │               │
     │<──────────────────────────────────────────────────────│               │
     │   "You can close this window"     │                  │               │
     │                │                  │                  │               │
     │ 13. Retry tool call              │                  │               │
     │────────────────>│                  │                  │               │
     │                │                  │                  │               │
     │                │ 14. Forward request                 │               │
     │                │─────────────────>│                  │               │
     │                │                  │                  │               │
     │                │                  │ 15. Use cached token             │
     │                │                  │────────────────────────────────>│
     │                │                  │                  │               │
     │                │                  │ 16. Confluence data              │
     │                │                  │<────────────────────────────────│
     │                │                  │                  │               │
     │ 17. Tool response                 │                  │               │
     │<────────────────────────────────────│                  │               │
     │                │                  │                  │               │
```

---

## Technical Implementation

### CIMD Resolution in MCP Proxy Lambda

The CIMD resolution happens in [mcp_proxy_lambda.py:149-191](lambda/mcp_proxy_lambda.py#L149-L191):

```python
def handle_authorize(event):
    """Redirect /authorize to Cognito with callback interception."""
    params = event.get("queryStringParameters", {}) or {}

    # Extract client_id (which is a URL in CIMD)
    client_id = params["client_id"]

    # Base64 encode the URL to use as Cognito client name
    encoded_client_id = base64.b64encode(bytes(client_id)).decode("ascii")

    # Check if we already have a Cognito client for this CIMD URL
    cognito_client_id = {
        c["ClientName"]: c["ClientId"]
        for c in get_user_pool_clients()
    }.get(encoded_client_id, None)

    if not cognito_client_id:
        # CIMD RESOLUTION: Fetch the metadata document
        cimd_manifest = requests.get(client_id).json()

        # Create a new Cognito client dynamically
        resp = cognito.create_user_pool_client(
            UserPoolId=USER_POOL_ID,
            ClientName=encoded_client_id,
            CallbackURLs=cimd_manifest["redirect_uris"] + [f"{api_url}/callback"],
            AllowedOAuthFlows=["code"],
            AllowedOAuthScopes=[...],
            SupportedIdentityProviders=["COGNITO"],
        )
        cognito_client_id = resp["UserPoolClient"]["ClientId"]

    # Replace CIMD URL with actual Cognito client_id
    params["client_id"] = cognito_client_id

    # Continue with standard OAuth flow...
```

**Key Points**:

1. **CIMD URL as client_id**: The client provides a URL instead of a string
2. **Metadata fetch**: Lambda performs HTTP GET on the URL to retrieve configuration
3. **Dynamic registration**: Creates Cognito client on-the-fly with CIMD metadata
4. **Caching**: Uses base64-encoded URL as client name to avoid duplicate registrations
5. **Callback URL merging**: Combines CIMD redirect_uris with Lambda callback URL

### State Parameter Encoding

To handle stateless Lambda functions, the original redirect_uri is encoded in the state parameter:

```python
# Encode original redirect_uri and state together
original_redirect_uri = params.get("redirect_uri", "")
original_state = params.get("state", "")

compound_state = {
    "state": original_state,
    "redirect_uri": urllib.parse.unquote(original_redirect_uri),
}
encoded_state = base64.urlsafe_b64encode(
    json.dumps(compound_state).encode()
).decode()

params["state"] = encoded_state
```

### 3LO Token Storage

When a 3LO elicitation occurs, the JWT token must be stored for later use:

```python
def is_elicitation(data):
    """Check if response is a 3LO elicitation."""
    error = data.get("error", {})
    return isinstance(error, dict) and error.get("code") == -32042

# In proxy_to_gateway:
if is_elicitation(data) and CALLBACK_LAMBDA_URL:
    store_token_for_3lo(req.headers.get("Authorization", ""))
```

The token is stored in Callback Lambda and used when calling `CompleteResourceTokenAuth`:

```python
def handle_oauth_callback(event):
    """Handle 3LO OAuth callback."""
    params = event.get("queryStringParameters", {})
    session_id = params.get("session_id", "")

    # Retrieve stored JWT
    user_token = USER_TOKEN.get("value")

    # Complete the 3LO flow
    agentcore_client = boto3.client("bedrock-agentcore", region_name=REGION)
    agentcore_client.complete_resource_token_auth(
        sessionUri=session_id,
        userIdentifier={"userToken": user_token}
    )
```

---

## Key Components

### 1. MCP Proxy Lambda ([mcp_proxy_lambda.py](lambda/mcp_proxy_lambda.py))

**Responsibilities**:

- Serve OAuth metadata endpoints (RFC 8414)
- Resolve CIMD URLs and create Cognito clients dynamically
- Handle authorization redirects with state encoding
- Proxy token requests to Cognito
- Forward MCP requests to AgentCore Gateway
- Detect 3LO elicitations and store JWT tokens

**Environment Variables**:

```python
GATEWAY_URL           # AgentCore Gateway MCP endpoint
COGNITO_DOMAIN        # Cognito OAuth domain
CLIENT_ID             # Cognito app client ID
CLIENT_SECRET         # Cognito app client secret
CALLBACK_LAMBDA_URL   # Callback Lambda URL for 3LO
USER_POOL_ID          # Cognito User Pool ID
REDIRECT_URL          # OAuth callback URL
```

### 2. Callback Lambda ([callback_lambda.py](lambda/callback_lambda.py))

**Responsibilities**:

- Receive OAuth callbacks from Atlassian
- Store JWT tokens for 3LO session binding
- Call `CompleteResourceTokenAuth` API
- Return success HTML page to user

**API Endpoints**:

- `POST /userIdentifier/token` - Store JWT for upcoming 3LO
- `GET /oauth2/callback` - Handle Atlassian OAuth callback

### 3. Amazon Cognito User Pool

**Configuration**:

- App clients created dynamically based on CIMD
- OAuth 2.0 flows: `authorization_code`
- Scopes: `openid`, `profile`, `email`, custom scopes
- Callback URLs: From CIMD manifest + Lambda callback URL

### 4. Amazon Bedrock AgentCore Gateway

**Capabilities**:

- MCP server implementation
- JWT authentication (inbound)
- 3LO OAuth support (outbound)
- Token caching and auto-refresh
- Elicitation response generation

**3LO Elicitation Format**:

```json
{
  "error": {
    "code": -32042,
    "message": "This request requires more information.",
    "data": {
      "elicitations": [
        {
          "mode": "url",
          "elicitationId": "abc-123",
          "url": "https://bedrock-agentcore.../oauth2/authorize?...",
          "message": "Please login to this URL for authorization."
        }
      ]
    }
  }
}
```

---

## Token Management

### Inbound Tokens (Cognito JWT)

**Lifetime**: Short-lived (typically 1 hour)

**Refresh**: VS Code client handles refresh token flow automatically

**Storage**: Managed by VS Code OAuth client

**Scope**: Access to AgentCore Gateway MCP endpoint

### Outbound Tokens (Atlassian 3LO)

**Lifetime**:

- Access token: ~1 hour
- Refresh token: ~90 days (with `offline_access` scope)

**Refresh**: Automatic by AgentCore Identity service

**Storage**: Cached by AgentCore Identity service (encrypted)

**Scope**: User-delegated access to Confluence API

**Re-consent Required When**:

- User revokes access in Atlassian settings
- Refresh token expires from inactivity (90 days unused)
- App's requested scopes change
- Credential provider is deleted/recreated

**Key Configuration**:

```python
# In notebook: Enable refresh tokens
oauth_config = {
    "OAuthFlowType": "CODE",
    "AuthorizationUrl": "https://auth.atlassian.com/authorize",
    "TokenUrl": "https://auth.atlassian.com/oauth/token",
    "ClientId": atlassian_client_id,
    "ClientSecret": atlassian_client_secret,
    "Scope": [
        "read:page:confluence",
        "read:space:confluence",
        "offline_access"  # ← Enables refresh tokens
    ]
}
```

---

## Troubleshooting

### CIMD Resolution Failures

**Error**: `Unable to fetch client metadata from URL`

**Causes**:

- CIMD URL is not accessible from Lambda (check VPC/security groups)
- CIMD document is malformed JSON
- URL returns non-200 status code

**Solutions**:

1. Verify URL is publicly accessible: `curl https://your-cimd-url`
2. Validate JSON structure matches OAuth 2.0 Dynamic Client Registration spec
3. Check Lambda CloudWatch logs for detailed error messages
4. Ensure Lambda has internet access (NAT Gateway if in VPC)

### Duplicate Cognito Clients

**Issue**: Multiple clients created for same CIMD URL

**Cause**: Client name collision or race condition

**Solution**: The implementation uses base64-encoded URL as client name to prevent duplicates. Check if client names in Cognito match expected encoding.

### State Parameter Errors

**Error**: `Invalid state parameter` or `Missing redirect_uri in state`

**Causes**:

- URL encoding issues (spaces become `+` or `%20`)
- Base64 padding missing
- State parameter too long

**Solutions**:

1. Check state decoding logic handles URL encoding properly
2. Verify base64 padding is added when needed
3. Increase Lambda payload size limits if state is truncated

### 3LO Token Binding Failures

**Error**: `No user token stored` when completing 3LO

**Causes**:

- JWT not stored before user grants consent
- Lambda instances not sharing memory (different invocations)
- Token expired in in-memory storage

**Solutions**:

1. Verify `store_token_for_3lo` is called on elicitation
2. Implement persistent storage (DynamoDB) for production:

   ```python
   # Replace in-memory dict with DynamoDB
   dynamodb = boto3.resource('dynamodb')
   table = dynamodb.Table('oauth-tokens')

   def store_token_for_3lo(auth_header):
       token = auth_header.removeprefix("Bearer ")
       table.put_item(Item={'session_id': 'current', 'token': token, 'ttl': int(time.time()) + 300})
   ```

### MCP Protocol Version Errors

**Error**: `Cannot initiate authorization code grant flow`

**Cause**: Missing `MCP-Protocol-Version: 2025-11-25` header

**Solution**: Update VS Code `mcp.json`:

```json
{
  "servers": {
    "agentcore": {
      "type": "http",
      "url": "https://...",
      "headers": {
        "MCP-Protocol-Version": "2025-11-25"
      }
    }
  }
}
```

### Callback URL Mismatches

**Error**: `redirect_uri_mismatch` from Cognito or Atlassian

**Causes**:

- Callback URL not registered in OAuth provider
- CIMD redirect_uris don't include Lambda callback URL
- URL scheme mismatch (http vs https)

**Solutions**:

1. For Cognito: Ensure Lambda callback URL is added to CIMD redirect_uris list
2. For Atlassian: Add AgentCore callback URL in Atlassian OAuth app settings
3. Verify exact URL match including trailing slashes

---

## Security Considerations

### CIMD URL Validation

**Risk**: Malicious client_id URLs could cause SSRF attacks

**Mitigations**:

1. Validate URL scheme (only allow https://)
2. Implement URL allowlist or domain restrictions
3. Set timeout on metadata fetch (currently 30s)
4. Validate JSON structure before parsing

Example validation:

```python
def validate_cimd_url(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https':
        raise ValueError("CIMD URL must use HTTPS")
    if parsed.hostname in ['localhost', '127.0.0.1']:
        raise ValueError("CIMD URL cannot be localhost")
    if not parsed.hostname.endswith('.example.com'):  # Domain allowlist
        raise ValueError("CIMD URL must be from trusted domain")
    return True
```

### Token Storage

**Current Implementation**: In-memory dictionary (not production-ready)

**Production Recommendations**:

1. Use DynamoDB with TTL for temporary token storage
2. Encrypt tokens at rest using KMS
3. Implement token rotation
4. Use ElastiCache for high-throughput scenarios

### JWT Validation

The MCP Proxy Lambda currently trusts Cognito-issued JWTs. For additional security:

1. Verify JWT signature using Cognito public keys
2. Validate issuer, audience, expiration
3. Implement rate limiting per user

---

## Comparison: CIMD vs Traditional OAuth

### Setup Complexity

**Traditional OAuth**:

```
1. Manually register client in auth server console
2. Copy client_id and client_secret
3. Configure redirect_uris in auth server
4. Hard-code client_id in application
5. Deploy application
```

**With CIMD**:

```
1. Deploy application with CIMD metadata endpoint
2. Use CIMD URL as client_id
3. OAuth proxy handles registration automatically
```

### Configuration Updates

**Traditional OAuth**:

- Add new redirect URI → Must update auth server manually
- Change scopes → Must update auth server manually
- Deploy to new environment → Must create new client registration

**With CIMD**:

- Add new redirect URI → Update CIMD JSON, redeploy
- Change scopes → Update CIMD JSON, redeploy
- Deploy to new environment → Just deploy (CIMD URL stays same)

### Multi-Tenancy

**Traditional OAuth**: Each tenant needs separate client_id registration

**With CIMD**: Single implementation, CIMD URL includes tenant context:

```
https://tenant1.example.com/.well-known/oauth-client
https://tenant2.example.com/.well-known/oauth-client
```

---

## References

- [OAuth 2.0 RFC 6749](https://datatracker.ietf.org/doc/html/rfc6749)
- [OAuth 2.0 Authorization Server Metadata (RFC 8414)](https://datatracker.ietf.org/doc/html/rfc8414)
- [OAuth 2.0 Dynamic Client Registration Protocol (RFC 7591)](https://datatracker.ietf.org/doc/html/rfc7591)
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25)
- [VS Code MCP Documentation](https://code.visualstudio.com/docs/copilot/customization/mcp-servers)
- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
- [Atlassian OAuth 2.0 (3LO)](https://developer.atlassian.com/cloud/confluence/oauth-2-3lo-apps/)

---

## Appendix: CIMD Metadata Example

Example CIMD document served at `https://api-gateway-url/.well-known/oauth-client`:

```json
{
  "client_id": "https://api-gateway-url/.well-known/oauth-client",
  "client_name": "VS Code Copilot MCP Client",
  "redirect_uris": [
    "vscode://github.copilot/oauth/callback",
    "http://127.0.0.1:3000/callback",
    "https://api-gateway-url/callback"
  ],
  "grant_types": ["authorization_code", "refresh_token"],
  "response_types": ["code"],
  "token_endpoint_auth_method": "none",
  "application_type": "native",
  "contacts": ["admin@example.com"]
}
```

This document is dynamically generated by the MCP Proxy Lambda but could also be a static file served by API Gateway or S3.
