# Okta OpenID Connect PKCE Setup Guide

---
## 📋 Navigation
**🏠 [README](../README.md)** | **📖 [Setup Guide](../docs/SETUP.md)** | **🏗️ [Architecture](../docs/ARCHITECTURE-FLOW.md)** | **🔧 [Scripts](../scripts/README.md)** | **🤖 [Client](../client/README.md)** | **⚙️ [Config](../configs/README.md)** | **🔐 [Okta Setup](OKTA-OPENID-PKCE-SETUP.md)**
---

## Overview

This guide sets up Okta PKCE authentication for Bedrock AgentCore Gateway using the existing `iframe-oauth-flow.html` - a complete, self-contained PKCE application.

## Prerequisites

- Okta Developer Account (free at [developer.okta.com](https://developer.okta.com))
- Access to Bedrock AgentCore Gateway (beta access required)
- nginx installed locally

## Okta Setup

### Create an OIDC Application

1. Log in to your Okta Developer Console
2. Navigate to **Applications** → **Applications** → **Create App Integration**
3. Configure:
   ```
   App name: bedrock-agentcore-gateway-client
   Grant types: ✅ Authorization Code, ✅ Refresh Token
   Sign-in redirect URIs: http://localhost:8080/okta-auth/
   Allowed grant types: ✅ Authorization Code
   Client authentication: ✅ Use PKCE (for public clients)
   ```
4. Save the application

### Configure API Scopes

- **Security** → **API** → **Authorization Servers** → **default**
- Ensure scopes exist: `openid`, `profile`, `email`
- Add custom scopes if needed: `bedrock-agentcore:read`, `bedrock-agentcore:write`

## Local Setup

### Configure Local nginx

```bash
# Navigate to the project directory
cd /path/to/project

# Start with provided configuration
sudo nginx -c $(pwd)/okta-auth/nginx/okta-local.conf
```

### Configure OAuth Parameters

1. Open `iframe-oauth-flow.html` in a text editor
2. Update the configuration section (around line 50):
   ```javascript
   const config = {
     clientId: 'YOUR_CLIENT_ID',
     redirectUri: 'http://localhost:8080/okta-auth/',
     authorizationEndpoint: 'https://dev-12345678.okta.com/oauth2/default/v1/authorize',
     tokenEndpoint: 'https://dev-12345678.okta.com/oauth2/default/v1/token',
     scope: 'openid profile email',
   };
   ```
3. Replace with your values:
   - **Client ID**: From your Okta application
   - **Okta Domain**: Your Okta domain (e.g., `dev-12345678.okta.com`)
   - **Auth Server ID**: `default`

*Note: The iframe file handles all PKCE logic, token management, and Bedrock AgentCore Gateway integration automatically.*

## Test the Setup

1. Open a browser and navigate to: http://localhost:8080/okta-auth/
2. Click "Login with Okta"
3. Complete the Okta authentication flow
4. You should see the access token displayed on the page
5. Copy this token for use with the client application

## Using the Token

```bash
# Copy the token to the client's token file
echo "YOUR_ACCESS_TOKEN" > ../client/token.txt

# Run the client with the token
cd ../client
python aws_operations_agent_mcp.py
```

## Troubleshooting

### Common Issues

1. **CORS Errors**:
   - Ensure your Okta application has the correct redirect URI
   - Check that nginx is running with the provided configuration

2. **Invalid Client Error**:
   - Verify your Client ID is correct
   - Ensure PKCE is enabled for the application

3. **Token Not Working**:
   - Check token expiration (default is 1 hour)
   - Verify scopes match what's required by the gateway

### Debugging

```bash
# Check nginx configuration
nginx -t -c /path/to/okta-local.conf

# View nginx logs
tail -f /usr/local/var/log/nginx/error.log

# Test token with curl
curl -H "Authorization: Bearer YOUR_TOKEN" https://your-gateway-url/mcp
```

## Advanced Configuration

The `iframe-oauth-flow.html` file is a complete PKCE implementation that includes:

- Code challenge and verifier generation
- Authorization code flow
- Token exchange and refresh
- Complete PKCE implementation (lines 330+)
- Token display and management
- Bedrock AgentCore Gateway integration
- All necessary HTML, CSS, and JavaScript

You can customize this file for your specific needs or use it as a reference for implementing PKCE in your own applications.

---
