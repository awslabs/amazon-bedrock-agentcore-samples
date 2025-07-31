# Okta OpenID Connect PKCE Setup Guide

Complete guide for setting up Okta OAuth2 authentication with the AWS Support Agent AgentCore system.

## Overview

This guide configures Okta OAuth2 authentication for the AgentCore system, supporting both user authentication (PKCE flow) and machine-to-machine authentication (client credentials flow).

## Prerequisites

- **Okta Developer Account** (free at [developer.okta.com](https://developer.okta.com))
- **AWS Account** with Bedrock AgentCore access
- **nginx** installed locally (for testing)
- **Python 3.11+** for running the system

## Okta Application Setup

### 1. Create OIDC Application

1. **Log in to Okta Developer Console**
2. **Navigate to**: Applications → Applications → Create App Integration
3. **Select**: OIDC - OpenID Connect → Single-Page Application (SPA)
4. **Configure Application**:
   ```
   App name: aws-support-agent-client
   Grant types: ✅ Authorization Code, ✅ Refresh Token
   Sign-in redirect URIs: 
     - http://localhost:8080/callback
     - http://localhost:8080/okta-auth/
   Sign-out redirect URIs: http://localhost:8080/
   Controlled access: Allow everyone in your organization to access
   ```
5. **Save** the application and note the **Client ID**

### 2. Configure API Scopes

1. **Navigate to**: Security → API → Authorization Servers → default
2. **Verify scopes exist**:
   - `openid` - Required for OpenID Connect
   - `profile` - User profile information  
   - `email` - User email address
3. **Add custom scope**:
   - **Name**: `api`
   - **Description**: API access for AgentCore
   - **Include in public metadata**: ✅

### 3. Create Machine-to-Machine Application

For AgentCore workload authentication:

1. **Create new app**: OIDC - OpenID Connect → Web Application
2. **Configure**:
   ```
   App name: aws-support-agent-m2m
   Grant types: ✅ Client Credentials
   Client authentication: ✅ Client secret
   ```
3. **Save** and note the **Client ID** and **Client Secret**

## Project Configuration

### 1. Update Static Configuration

Edit `config/static-config.yaml`:

```yaml
# Okta OAuth2 Configuration
okta:
  domain: "your-domain.okta.com"  # Replace with your Okta domain
  
  # OAuth2 authorization server configuration
  authorization_server: "default"
  
  # Client configuration for client credentials flow (app-to-app)
  client_credentials:
    client_id: "YOUR_M2M_CLIENT_ID"      # From M2M app
    client_secret: "${OKTA_CLIENT_SECRET}"  # Set via environment variable
    scope: "api"
  
  # Client configuration for user authentication (PKCE flow)
  user_auth:
    client_id: "YOUR_SPA_CLIENT_ID"      # From SPA app
    audience: "YOUR_SPA_CLIENT_ID"       # Same as client_id
    redirect_uri: "http://localhost:8080/callback"
    scope: "openid profile email"
  
  # JWT token configuration
  jwt:
    audience: "YOUR_SPA_CLIENT_ID"       # Your SPA client ID
    issuer: "https://your-domain.okta.com/oauth2/default"
    discovery_url: "https://your-domain.okta.com/oauth2/default/.well-known/openid-configuration"
    cache_duration: 300
    refresh_threshold: 60

# AgentCore JWT Authorizer Configuration
agentcore:
  jwt_authorizer:
    discovery_url: "https://your-domain.okta.com/oauth2/default/.well-known/openid-configuration"
    allowed_audience: 
      - "YOUR_SPA_CLIENT_ID"
```

### 2. Set Environment Variables

```bash
# Set the Okta client secret
export OKTA_CLIENT_SECRET="your_m2m_client_secret"

# Optional: Set AWS profile if different from default
export AWS_PROFILE="your-aws-profile"
```

## Local Testing Setup

### 1. Configure nginx (Optional)

For local PKCE testing, you need to add the server block to your nginx configuration:

```bash
# Navigate to your project directory
cd /path/to/your/AgentCore/project

# Step 1: Update paths in the nginx config file
# Replace placeholder paths with your actual project path
sed -i '' "s|/path/to/your/AgentCore|$(pwd)|g" okta-auth/nginx/okta-local.conf

# Verify the paths were updated correctly
cat okta-auth/nginx/okta-local.conf | grep "root\|alias"

# Step 2: IMPORTANT - okta-local.conf contains only a server block, not a complete nginx.conf
# You must integrate this server block into your existing nginx configuration.

# Manual Integration Steps:
# 1. Find your nginx.conf location:
#    - macOS (Homebrew): /usr/local/etc/nginx/nginx.conf
#    - Linux: /etc/nginx/nginx.conf
#    - Docker: /etc/nginx/nginx.conf

# 2. Make a backup of your current nginx.conf
sudo cp /usr/local/etc/nginx/nginx.conf /usr/local/etc/nginx/nginx.conf.backup  # macOS
# sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup                    # Linux

# 3. Open your main nginx.conf file for editing:
sudo nano /usr/local/etc/nginx/nginx.conf  # macOS
# sudo nano /etc/nginx/nginx.conf          # Linux

# 4. Find the http {} block in nginx.conf
# 5. Copy the entire server block content from okta-auth/nginx/okta-local.conf
# 6. Paste it inside the existing http {} block (before the closing })
# 7. Save and close the file

# NOTE: The setup-local-nginx.sh script is not functional as it attempts to use
# okta-local.conf as a complete nginx configuration, which will fail.

# Step 3: Test and reload nginx
# Test nginx configuration for syntax errors
sudo nginx -t

# If test passes, reload nginx configuration
sudo nginx -s reload

# Verify nginx is running and listening on port 8080
curl http://localhost:8080/health
# Should return: healthy
```

### 2. Test OAuth Flow

Use the provided HTML test page:

1. **Update configuration** in `okta-auth/iframe-oauth-flow.html`:
   ```javascript
   const config = {
     clientId: 'YOUR_SPA_CLIENT_ID',
     redirectUri: 'http://localhost:8080/okta-auth/',
     authorizationEndpoint: 'https://your-domain.okta.com/oauth2/default/v1/authorize',
     tokenEndpoint: 'https://your-domain.okta.com/oauth2/default/v1/token',
     scope: 'openid profile email',
   };
   ```

2. **Open browser**: http://localhost:8080/okta-auth/
3. **Click "Login with Okta"** and complete authentication
4. **Copy the access token** for testing

## Deploy and Test the System

### 1. Deploy Infrastructure

```bash
# Deploy the AgentCore system
cd agentcore-runtime/deployment
./01-prerequisites.sh
./02-create-memory.sh
./03-setup-oauth-provider.sh  # This uses your Okta config
./04-deploy-mcp-tool-lambda.sh
./05-create-gateway-targets.sh
./06-deploy-diy.sh
./07-deploy-sdk.sh
```

### 2. Test Authentication

```bash
# Test OAuth provider setup
cd agentcore-runtime/runtime-ops-scripts
python oauth_test.py test-config

# Expected output:
# ✅ M2M token obtained successfully
# ✅ OAuth2 token obtained successfully
```

### 3. Test End-to-End

```bash
# Use the chat client
cd chatbot-client/src
python client.py --interactive

# Or test directly with curl (using token from step 2)
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "prompt": "List my S3 buckets",
    "session_id": "test-session",
    "actor_id": "user"
  }'
```

## Authentication Flow

### User Authentication (PKCE)
1. **User** → Okta login → JWT token
2. **Chat Client** → AgentCore Runtime (with JWT)
3. **Runtime validates** JWT against Okta discovery endpoint
4. **Runtime processes** user request

### Machine-to-Machine (M2M)
1. **Runtime** → AgentCore Identity → Workload token
2. **Workload token** → OAuth provider → M2M token  
3. **M2M token** → AgentCore Gateway → Tools access
4. **Tools** → AWS services → Results

## Troubleshooting

### Common Issues

**1. Invalid Client Error**
```bash
# Check your client IDs in static-config.yaml
grep -A 10 "client_credentials:" config/static-config.yaml
grep -A 10 "user_auth:" config/static-config.yaml
```

**2. Token Validation Failures**
```bash
# Verify Okta discovery endpoint
curl https://your-domain.okta.com/oauth2/default/.well-known/openid-configuration

# Test token validation
python agentcore-runtime/runtime-ops-scripts/oauth_test.py test-config
```

**3. M2M Authentication Fails**
```bash
# Check environment variable
echo $OKTA_CLIENT_SECRET

# Test M2M flow specifically
python agentcore-runtime/runtime-ops-scripts/oauth_test.py workload-token bac-diy
```

**4. Gateway Connection Issues**
```bash
# Check if gateway and targets are deployed
cd agentcore-runtime/gateway-ops-scripts
python list-gateways.py
python list-targets.py
```

### Debug Commands

```bash
# Check deployed OAuth provider
cd agentcore-runtime/runtime-ops-scripts
python credentials_manager.py list

# View runtime logs
cd agentcore-runtime/runtime-ops-scripts  
python runtime_manager.py list
python logs_manager.py get <runtime-id>

# Test configuration validation
cd /path/to/your/AgentCore/project
python -c "from shared.config_manager import AgentCoreConfigManager; AgentCoreConfigManager().validate()"
```

### Log Analysis

**AgentCore Runtime logs** (look for):
- `✅ OAuth initialized with provider`
- `✅ M2M token obtained successfully`
- `✅ MCP client ready`

**Common error patterns**:
- `❌ OAuth provider not found` → Check deployment step 03
- `❌ Invalid client credentials` → Check client secret environment variable
- `❌ Token validation failed` → Check JWT configuration in static-config.yaml

## Security Best Practices

1. **Never commit secrets** - Always use environment variables for client secrets
2. **Use HTTPS in production** - Update redirect URIs for production deployment
3. **Rotate tokens regularly** - Configure appropriate token lifetimes in Okta
4. **Validate token audiences** - Ensure JWT audience validation is strict
5. **Monitor authentication** - Review Okta system logs regularly

## Production Deployment

For production, update:

1. **Redirect URIs** to your production domain
2. **Environment variables** in your deployment pipeline
3. **Network security** to restrict access appropriately
4. **Token lifetimes** based on your security requirements

---

For additional help, refer to:
- [Okta Developer Documentation](https://developer.okta.com/docs/)
- [AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Project README](../README.md) for complete system setup
