# Authentication and Authorization Setup

This document covers the setup requirements for IAM permissions and identity provider (IDP) configuration needed for AgentCore Gateway.

## IAM Permissions Setup

### Core Gateway Permissions

Policy required for invoking CRUDL operations on Gateway Target or Gateway, InvokeTool API, and ListTool:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:*",
                "iam:PassRole"
            ],
            "Resource": "*"
        }
    ]
}
```

### S3 Schema Access

Policy required for creating target with API schema in S3 (attach to the same caller identity as above policy):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": "*"
        }
    ]
}
```

### Lambda Target Permissions

If Lambda is a Gateway target type, the execution role should have permission to invoke lambda:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": "lambda:InvokeFunction",
            "Resource": "arn:aws:lambda:us-west-2:<account-with-lambda>:function:TestLambda"
        }
    ]
}
```

### Smithy Target Permissions

If the Gateway Target is of Smithy Target type:
- Execution role must include any AWS permissions for the tools/APIs you wish to invoke
- Example: Adding a gateway target for S3 → add relevant S3 permissions to the role

### Trust Policy for AgentCore Service

You need to trust the AgentCore service's beta account to assume the role:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "bedrock-agentcore.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        },
    ]
}
```

### Cross-Account Lambda Access

If the Lambda is in another account, configure a resource-based policy (RBP) on the lambda function:

```json
{
    "Version": "2012-10-17",
    "Id": "default",
    "Statement": [
        {
            "Sid": "cross-account-access",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::<gateway-account>:role/AgentCoreBetaLambdaExecuteRole"
            },
            "Action": "lambda:InvokeFunction",
            "Resource": "arn:aws:lambda:us-west-2:<account-with-lambda>:function:TestLambda"
        }
    ]
}
```

## Identity Provider Configuration

### Important: Cognito vs Auth0/Okta Authentication Differences

**Critical Distinction for AgentCore Gateway Configuration:**

| Provider | JWT Claim Used | Gateway Configuration | Token Contains |
|----------|---------------|---------------------|----------------|
| **Amazon Cognito** | `client_id` | `allowedClients: ["client-id"]` | ❌ No `aud` claim |
| **Auth0** | `aud` | `allowedAudience: ["audience"]` | ✅ Has `aud` claim |
| **Okta** | `aud` | `allowedAudience: ["audience"]` | ✅ Has `aud` claim |

**Why this matters:**
- Cognito client credentials tokens do NOT include an `aud` (audience) claim
- AgentCore Gateway with `allowedAudience` will reject Cognito tokens (401 error)
- For Cognito, you MUST use `allowedClients` with your app client ID
- For Auth0/Okta, you MUST use `allowedAudience` with your API identifier

**Command Line Usage:**
```bash
# For Cognito
python main.py "MyGateway" --allowed-clients "your-client-id" ...

# For Auth0/Okta  
python main.py "MyGateway" --allowed-audience "your-audience" ...
```

### 1. Amazon Cognito Setup

#### Create User Pool

Create a machine-to-machine user pool:

```bash
# Create user pool
aws cognito-idp create-user-pool \
    --region us-west-2 \
    --pool-name "test-agentcore-user-pool"

# List user pools to get the pool ID
aws cognito-idp list-user-pools \
    --region us-west-2 \
    --max-results 60
```

#### Discovery URL Format

```
https://cognito-idp.us-west-2.amazonaws.com/<UserPoolId>/.well-known/openid-configuration
```

#### Create Resource Server

```bash
aws cognito-idp create-resource-server \
    --region us-west-2 \
    --user-pool-id <UserPoolId> \
    --identifier "test-agentcore-server" \
    --name "TestAgentCoreServer" \
    --scopes '[{"ScopeName":"read","ScopeDescription":"Read access"}, {"ScopeName":"write","ScopeDescription":"Write access"}]'
```

#### Create Client

```bash
aws cognito-idp create-user-pool-client \
    --region us-west-2 \
    --user-pool-id <UserPoolId> \
    --client-name "test-agentcore-client" \
    --generate-secret \
    --allowed-o-auth-flows client_credentials \
    --allowed-o-auth-scopes "test-agentcore-server/read" "test-agentcore-server/write" \
    --allowed-o-auth-flows-user-pool-client \
    --supported-identity-providers "COGNITO"
```

#### Get Access Token

```bash
curl --http1.1 -X POST https://<UserPoolIdWithoutUnderscore>.auth.us-west-2.amazoncognito.com/oauth2/token \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "grant_type=client_credentials&client_id=<ClientId>&client_secret=<ClientSecret>"
```

**Note**: Remove any underscore from the UserPoolId in the URL (e.g., `us-west-2_gmSGKKGr9` becomes `us-west-2gmSGKKGr9`)

#### Sample Cognito Token Claims

```json
{
    "sub": "<>",
    "token_use": "access",
    "scope": "default-m2m-resource-server-<>/read",
    "auth_time": 1749679004,
    "iss": "https://cognito-idp.us-west-2.amazonaws.com/us-west-<>",
    "exp": 1749682604,
    "iat": 1749679004,
    "version": 2,
    "jti": "<>",
    "client_id": "<>"
}
```

#### Cognito Authorizer Configuration

```json
{
    "authorizerConfiguration": {
        "customJWTAuthorizer": {
            "allowedClients": ["<ClientId>"],
            "discoveryUrl": "https://cognito-idp.us-west-2.amazonaws.com/<UserPoolId>/.well-known/openid-configuration"
        }
    }
}
```

### 2. Auth0 Setup

#### Setup Steps

1. **Create an API** (1:1 mapping to a resource server)
2. **Create an Application** (Acts as client to the resource server)
3. **Configure the API Identifier** in API > Settings (added to audience claim)
4. **Configure scopes** in API > Scopes section

#### Discovery URL Format

```
https://<your-domain>/.well-known/openid-configuration
```

#### Get Access Token

```bash
curl --request POST \
    --url https://dev-<your-domain>.us.auth0.com/oauth/token \
    --header 'content-type: application/json' \
    --data '{
        "client_id":"YOUR_CLIENT_ID",
        "client_secret":"YOUR_CLIENT_SECRET",
        "audience":"gateway123",
        "grant_type":"client_credentials",
        "scope": "invoke:gateway"
    }'
```

#### Sample Auth0 Token Claims

```json
{
    "iss": "https://dev-<>.us.auth0.com/",
    "sub": "<>",
    "aud": "gateway123",
    "iat": 1749741913,
    "exp": 1749828313,
    "scope": "invoke:gateway read:gateway",
    "jti": "<>",
    "client_id": "<>",
    "permissions": [
        "invoke:gateway",
        "read:gateway"
    ]
}
```

#### Auth0 Authorizer Configuration

```json
{
    "authorizerConfiguration": {
        "customJWTAuthorizer": {
            "allowedAudience": ["gateway123"],
            "discoveryUrl": "https://dev-<your-domain>.us.auth0.com/.well-known/openid-configuration"
        }
    }
}
```

### 3. Okta Setup

#### Setup Steps

1. **Create Application** with Client credentials grant type
   - Follow [Okta documentation](https://developer.okta.com/docs/guides/implement-grant-type/clientcreds/main/)
   - Sign up for free trial if needed

2. **Configure Application**
   - Go to Admin → Applications → Create a client with secret
   - Disable "Require Demonstrating Proof of Possession (DPoP) header in token requests"

3. **Configure Authorization Server**
   - Go to Admin → Security → API
   - Use default Authorization Server
   - Add additional scopes (e.g., "InvokeGateway")
   - Optionally add Access policies and claims

4. **Get Configuration**
   - Obtain Metadata URI for default Authorization Server (Discovery URI)
   - Get ClientID/Secret for JWT Authorizer configuration

## Token Validation

Use [jwt.io](https://jwt.io/) to decode and validate bearer tokens during debugging.

## Environment Variables

After setting up your identity provider, configure these environment variables in your `.env` file:

```bash
# For Cognito
COGNITO_DOMAIN=https://yourdomain.auth.us-west-2.amazoncognito.com
COGNITO_CLIENT_ID=your-client-id
COGNITO_CLIENT_SECRET=your-client-secret

# For Auth0
COGNITO_DOMAIN=https://dev-yourdomain.us.auth0.com
COGNITO_CLIENT_ID=your-client-id
COGNITO_CLIENT_SECRET=your-client-secret
```

## Troubleshooting

### Common 401 "Invalid Bearer token" Error

**Problem:** Gateway returns HTTP 401 with `"Invalid Bearer token"` message.

**Root Cause:** Mismatch between token claims and gateway configuration.

**Solution Steps:**

1. **Decode your JWT token** using [jwt.io](https://jwt.io/) to inspect claims
2. **Check your token claims:**
   - Cognito tokens: Look for `client_id` claim (no `aud` claim)
   - Auth0/Okta tokens: Look for `aud` claim
3. **Verify gateway configuration matches your token:**
   ```bash
   # If your token has client_id but no aud claim (Cognito)
   python main.py "Gateway" --allowed-clients "your-client-id" ...
   
   # If your token has aud claim (Auth0/Okta)
   python main.py "Gateway" --allowed-audience "your-audience" ...
   ```
4. **Common fixes:**
   - **Cognito users:** Use `--allowed-clients` not `--allowed-audience`
   - **Auth0 users:** Use `--allowed-audience` not `--allowed-clients`
   - **Check client ID:** Must match exactly (case-sensitive)
   - **Check audience:** Must match your API identifier exactly

### Other Common Issues

- If token endpoint doesn't work, check the discovery URL in your browser to find the correct `token_endpoint`
- Ensure audience values match between token request and gateway configuration
- Verify scopes are properly configured in your IDP
- Check that the discovery URL is accessible and returns valid OpenID configuration
- For Cognito: Ensure your app client has `client_credentials` grant type enabled