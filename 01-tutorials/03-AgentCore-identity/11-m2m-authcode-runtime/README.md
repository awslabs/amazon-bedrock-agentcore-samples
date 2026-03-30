# AgentCore Identity: M2M and Auth Code Flows with Runtime (Cognito)

## Overview

This sample demonstrates two outbound OAuth2 flows in a single **AgentCore Runtime** agent:

| Flow | Grant Type | Use Case |
|:-----|:-----------|:---------|
| **M2M** (machine-to-machine) | `client_credentials` | Agent calls internal/downstream APIs as itself — no user interaction |
| **Auth Code** (3LO) | `authorization_code` | Agent accesses user-owned resources (Google Calendar) — requires one-time user consent |

**Inbound Auth**: The runtime endpoint is protected by a Cognito JWT. Both flows require the caller to present a valid bearer token.

### Architecture

```
Caller
  │  Authorization: Bearer <Cognito JWT>
  ▼
AgentCore Runtime  ──validates JWT──▶  Cognito User Pool
  │
  ├─── M2M Tool ──@requires_access_token(auth_flow="M2M")──▶
  │              AgentCore Identity (client credentials)    ──▶  Internal API
  │
  └─── 3LO Tool ──@requires_access_token(auth_flow="USER_FEDERATION")──▶
                 AgentCore Identity (auth code)             ──▶  Google Calendar API
                         │
                         │ (first call only: returns consent URL)
                         ▼
                     User's browser ──consents──▶ Google ──callback──▶ localhost:9090
```

### Tutorial Details

| Information         | Details                                                              |
|:--------------------|:---------------------------------------------------------------------|
| Tutorial type       | CLI walkthrough                                                      |
| Agent type          | Single                                                               |
| Agentic Framework   | Strands Agents                                                       |
| LLM model           | Anthropic Claude Haiku 4.5                                           |
| Inbound Auth        | Amazon Cognito (CUSTOM_JWT)                                          |
| Outbound Auth (M2M) | OAuth2 client credentials — `@requires_access_token(auth_flow="M2M")` |
| Outbound Auth (3LO) | OAuth2 auth code — `@requires_access_token(auth_flow="USER_FEDERATION")` |
| Example complexity  | Medium                                                               |
| CLI tool            | `agentcore` (npm: `@aws/agentcore`)                                  |

---

## Prerequisites

- **Node.js** 20.x or later
- **Python** 3.10+
- **uv** ([install](https://docs.astral.sh/uv/getting-started/installation/))
- **AWS credentials** configured
- **AgentCore CLI** installed:

```bash
npm install -g @aws/agentcore
```

- **Amazon Bedrock model access**: Enable `claude-haiku-4-5` in the Bedrock console
- **For M2M**: An OAuth2 authorization server that supports `client_credentials` grant
- **For 3LO**: A Google Cloud project with Calendar API enabled (see Step 4)

---

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 2: Set Up Cognito (Inbound Auth)

```bash
python setup_cognito.py
```

Creates a Cognito User Pool and test user. Saves `cognito_config.json`.

Note the values printed for Step 6:
```
--discovery-url    https://cognito-idp.<region>.amazonaws.com/<pool_id>/.well-known/openid-configuration
--allowed-clients  <client_id>
```

---

## Step 3: Set Up M2M Credential Provider

### Option A — CLI (recommended)

```bash
agentcore add credential \
  --name M2MProvider \
  --type oauth \
  --discovery-url https://YOUR_AUTH_SERVER/.well-known/openid-configuration \
  --client-id YOUR_M2M_CLIENT_ID \
  --client-secret YOUR_M2M_CLIENT_SECRET \
  --scopes api:read,api:write
```

### Option B — Script

Create a `.env` file:

```bash
M2M_CLIENT_ID=your-client-id
M2M_CLIENT_SECRET=your-client-secret
M2M_DISCOVERY_URL=https://your-auth-server/.well-known/openid-configuration
```

Then run:

```bash
python setup_oauth_providers.py
```

---

## Step 4: Set Up Google OAuth2 Provider (3LO / Auth Code)

### 4a. Configure Google Cloud

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project (or select existing)
2. Enable **Google Calendar API** (APIs & Services > Library > Google Calendar API > Enable)
3. Configure OAuth Consent Screen (APIs & Services > OAuth consent screen):
   - App name, support email, developer contact
   - Under **Scopes**: add `https://www.googleapis.com/auth/calendar.readonly`
   - Under **Test users**: add your Gmail address
4. Create OAuth 2.0 credentials (APIs & Services > Credentials > Create Credentials > OAuth client ID):
   - Application type: **Web application**
   - Note the **Client ID** and **Client Secret**

### 4b. Create the Google 3LO Credential Provider

Add to your `.env` file:

```bash
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

Run the setup script:

```bash
python setup_oauth_providers.py
```

The script prints:
```
IMPORTANT: Register this callback URL in Google Cloud Console:
  Callback URL: https://agentcore.amazonaws.com/identities/.../callback
```

### 4c. Register the Callback URL

1. Go to Google Cloud Console > Credentials > your OAuth 2.0 Client ID
2. Under **Authorised redirect URIs**, add the callback URL printed above
3. Click **Save**

---

## Step 5: Create the AgentCore Project

```bash
agentcore create --name M2MAuthDemo --defaults --no-agent
cd M2MAuthDemo
```

---

## Step 6: Add the Agent

```bash
agentcore add agent \
  --name MyAgent \
  --type byo \
  --code-location ../app/MyAgent \
  --entrypoint main.py \
  --language Python \
  --framework Strands \
  --model-provider Bedrock \
  --authorizer-type CUSTOM_JWT \
  --discovery-url YOUR_COGNITO_DISCOVERY_URL \
  --allowed-clients YOUR_COGNITO_CLIENT_ID
```

Replace `YOUR_COGNITO_DISCOVERY_URL` and `YOUR_COGNITO_CLIENT_ID` with the values printed by `setup_cognito.py` in Step 2.

---

## Step 7: Deploy

```bash
agentcore deploy -y
```

---

## Step 8: Post-Deploy Configuration

The CLI now applies JWT auth at deploy time. Run this post-deploy script to attach the required IAM permissions, KMS access for the token vault, and register callback URLs for 3LO flows:

```bash
cd ..
python configure_inbound_auth.py
```

Wait ~30 seconds for changes to propagate.

---

## Step 9: Test M2M Flow

```bash
cd ..
python invoke.py --flow m2m
```

Expected output:

```
=== M2M Flow Test ===
The agent will call an internal API using client credentials (no user consent needed).

Agent response:
The internal API at /api/v1/status returned: {"status": "ok", ...}
```

The M2M token is fetched silently using client credentials — no browser interaction required.

---

## Step 10: Test Auth Code (3LO) Flow

```bash
python invoke.py --flow authcode
```

**First invocation** — consent URL returned:

```
=== Auth Code (3LO) Flow Test ===
Starting OAuth2 callback server...

Agent response:
User authorization required. Please visit this URL and grant access:
https://accounts.google.com/o/oauth2/auth?...

After authorizing, invoke the agent again to retrieve your calendar events.

Waiting for you to complete the Google consent flow...
After authorizing in your browser, press Enter to re-invoke the agent.
```

1. Click the URL (or copy/paste into a browser)
2. Log in with Google and grant Calendar access
3. The callback server at `localhost:9090` handles the redirect and calls `CompleteResourceTokenAuth`
4. Press **Enter** to re-invoke

**Second invocation** — calendar events retrieved:

```
Agent response:
Calendar events for 2025-03-20:
  - 09:00: Standup
  - 14:00: Design Review
  - 16:30: 1:1 with Manager
```

---

## Step 11: Cleanup

```bash
cd M2MAuthDemo
agentcore remove agent --name MyAgent --force
agentcore remove credential --name M2MProvider --force
agentcore remove credential --name Google3LOProvider --force
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

| Concept | Details |
|:--------|:--------|
| **M2M (client credentials)** | `auth_flow="M2M"` — AgentCore Identity calls the token endpoint directly with client ID + secret. No user involved. Token is cached per agent instance. |
| **Auth Code / 3LO** | `auth_flow="USER_FEDERATION"` — First call returns a consent URL via `on_auth_url` callback. After consent, AgentCore Identity stores tokens and refreshes automatically. |
| **Session binding** | `oauth2_callback_server.py` verifies the OAuth callback came from the same user who invoked the agent, preventing CSRF/session fixation attacks. |
| **Token storage** | All tokens are stored in AgentCore Identity (backed by Secrets Manager). The agent code only receives tokens in-memory via decorators. |

## Next Steps

- [Runtime Inbound + Outbound Auth](../09-runtime-inbound-outbound-auth/) — simpler API key outbound example
- [Gateway Inbound + Outbound Auth](../10-gateway-inbound-outbound-auth/) — gateway-level auth
- Replace Cognito with [EntraID](../08-IDP-examples/EntraID/) or [Okta](../08-IDP-examples/Okta/)
