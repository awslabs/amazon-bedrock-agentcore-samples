# Okta Setup Guide

This guide walks through the Okta configuration needed before deploying the
MCP server. You will need **Okta admin** access to complete these steps.

## Step 1 — Choose or Create a Custom Authorization Server

AgentCore validates JWTs against an OIDC discovery endpoint. You need a
**Custom Authorization Server** (not the default Org Authorization Server)
because it lets you define audiences and custom claims.

1. In Okta Admin Console, go to **Security > API > Authorization Servers**.
2. Use an existing Custom Authorization Server or click **Add Authorization Server**.
3. Set a meaningful **Audience** value, e.g. `api://your-mcp-name`.
4. Note the **Issuer URI** — it looks like:
   `https://<your-okta-domain>/oauth2/<auth-server-id>`

The OIDC discovery URL is this issuer with `/.well-known/openid-configuration`
appended.

## Step 2 — Create a Native Application

AgentCore acts as a public OAuth client using Authorization Code + PKCE (no
client secret required).

1. Go to **Applications > Create App Integration**.
2. Choose **OIDC — OpenID Connect**, then **Native Application**.
3. Under **Grant type**, ensure **Authorization Code** is selected.
4. Set the **Sign-in redirect URI** to:
   ```
   http://localhost:8090/callback
   ```
5. Under **Assignments**, assign the users or groups that should have access.
6. Note the **Client ID** from the application's General tab.

## Step 3 — Add `client_id` Custom Claim

AgentCore's `customJWTAuthorizer` validates the `client_id` claim in the
access token. By default, Okta includes `cid` but not `client_id`. You must
add a custom claim so AgentCore can match the `allowedClients` list.

> This is a one-time setup per Authorization Server.

1. Go to **Security > API > Authorization Servers > [your server] > Claims**.
2. Click **Add Claim**.
3. Configure:
   - **Name:** `client_id`
   - **Include in token type:** Access Token (Always)
   - **Value type:** Expression
   - **Value:** `app.clientId`
   - **Include in:** Any scope
4. Save.

## Step 4 — Collect Values

After completing the steps above, you should have these values:

| Value | Example | Env Var |
|-------|---------|---------|
| Okta domain | `dev-12345678.okta.com` | `OKTA_DOMAIN` |
| Auth Server ID | `aus1234567890abcdef` | `OKTA_AUTH_SERVER_ID` |
| Client ID | `0oa1234567890abcdef` | `OKTA_CLIENT_ID` |
| Audience | `api://your-mcp-name` | `OKTA_AUDIENCE` |

The discovery URL is derived automatically:
```
https://${OKTA_DOMAIN}/oauth2/${OKTA_AUTH_SERVER_ID}/.well-known/openid-configuration
```

## Verification

After deploying the MCP server, run the invoke step to verify end-to-end:

```bash
python okta_mcp_runtime.py --invoke
```

This will open your browser for Okta sign-in, exchange the authorization code
for an access token, decode the JWT (verify `client_id` and `aud` claims are
present), and call the MCP server.
