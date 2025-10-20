# AgentCore Gateway Flow Documentation

## Overview

The monitoring agent uses AWS Bedrock AgentCore Gateway to provide secure access to MCP (Model Context Protocol) tools. The gateway handles authentication, authorization, and routing of tool requests.

## Architecture Components

### 1. Configuration-Driven Setup
- All gateway configuration is managed through `config.yaml`
- The `inbound_auth` section controls authentication mechanism
- Supports both new user pool creation and existing user pool usage

### 2. Cognito Authentication Setup

#### User Pool Management
The system uses AWS Cognito for OAuth 2.0 authentication:

```yaml
inbound_auth:
  type: "cognito"
  cognito:
    create_user_pool: true|false  # Controls whether to create new or use existing
    user_pool_name: "gateway"
    resource_server_id: "monitoring_agent"
    resource_server_name: "agentcore-gateway"
    client_name: "agentcore-client"
    scopes:
      - ScopeName: "gateway:read"
        ScopeDescription: "Read access"
      - ScopeName: "gateway:write"
        ScopeDescription: "Write access"
```

#### Flow Logic
1. **If `create_user_pool: true`**: Uses `get_or_create_user_pool()` from utils to create/find user pool
2. **If `create_user_pool: false`**: Extracts pool ID from existing `discovery_url` in config

### 3. IAM Role Creation
- Uses `create_agentcore_gateway_role_s3_smithy()` from utils
- Creates role with comprehensive permissions for:
  - Bedrock AgentCore services
  - Bedrock model access
  - IAM PassRole
  - Secrets Manager
  - Lambda execution
  - S3 access

### 4. Gateway Creation Process

#### Step-by-Step Flow

1. **Credential Check**
   - Checks for existing credentials in `mcp_credentials.json`
   - Validates token freshness and gateway existence

2. **IAM Role Setup**
   ```python
   role_name = f"{gateway_name}Role"
   agentcore_gateway_iam_role = create_agentcore_gateway_role_s3_smithy(role_name)
   role_arn = agentcore_gateway_iam_role['Role']['Arn']
   ```

3. **Cognito Configuration**
   - Initializes Cognito client
   - Creates/gets user pool based on config
   - Sets up resource server with scopes
   - Creates M2M client for token generation

4. **Gateway Creation/Retrieval**
   - Checks for existing gateway by name
   - Creates new gateway if needed with:
     - JWT authorization configuration
     - MCP protocol type
     - Role ARN for execution

5. **Target Configuration**
   - Creates gateway targets from config
   - Supports Lambda, OpenAPI, and Smithy targets

6. **Token Generation**
   - Uses `get_token()` function with proper scopes
   - Scope format: `{resource_server_id}/gateway:read {resource_server_id}/gateway:write`

### 5. Token Management

#### Access Token Lifecycle
- Initial token generation during setup
- Automatic refresh on authentication failures
- Credential caching in `mcp_credentials.json`

#### Refresh Mechanism
```python
def _refresh_access_token() -> str:
    # Extracts pool info from config
    # Gets client secret from Cognito
    # Generates new token with proper scopes
    # Returns fresh access token
```

### 6. MCP Client Integration

#### Streamable HTTP Transport
- Creates HTTP client with Bearer token authentication
- Automatic token refresh on 401 errors
- Connection retry logic

#### Tool Access
- Lists tools from MCP gateway
- Provides tools to Strands Agent framework
- Handles authentication for each tool call

## Security Features

### 1. JWT-Based Authentication
- Custom JWT authorizer in AgentCore Gateway
- Client credentials OAuth 2.0 flow
- Scoped access control (read/write)

### 2. IAM Role Isolation
- Dedicated execution role per gateway
- Principle of least privilege
- Cross-account access controls

### 3. Token Management
- Short-lived access tokens
- Automatic refresh mechanisms
- Secure credential storage

## Error Handling

### 1. Token Expiry
- Automatic detection of expired tokens
- Silent refresh and retry
- Fallback to credential regeneration

### 2. Gateway Conflicts
- Handles existing gateway detection
- Reuses existing resources when appropriate
- Pagination support for gateway listing

### 3. Configuration Validation
- Required parameter checking
- Discovery URL parsing and validation
- Scope format verification

## Configuration Reference

### Required Config Sections

```yaml
agent_information:
  monitoring_agent_model_info:
    gateway_config:
      name: "monitoringagentgw2039"
      bucket_name: "your-s3-bucket"
      inbound_auth:
        type: "cognito"
        cognito:
          create_user_pool: true
          user_pool_name: "gateway"
          resource_server_id: "monitoring_agent"
          resource_server_name: "agentcore-gateway"
          client_name: "agentcore-client"
          scopes:
            - ScopeName: "gateway:read"
              ScopeDescription: "Read access"
            - ScopeName: "gateway:write"
              ScopeDescription: "Write access"
      auth_info:
        discovery_url: "https://cognito-idp.region.amazonaws.com/pool-id/.well-known/openid-configuration"
        client_id: "cognito-client-id"
      credentials:
        create_new_access_token: true
```

## Utility Functions Used

From `utils.py`:
- `get_or_create_user_pool()`: User pool management
- `get_or_create_resource_server()`: OAuth resource server setup
- `get_or_create_m2m_client()`: Machine-to-machine client creation
- `get_token()`: OAuth token generation
- `create_agentcore_gateway_role_s3_smithy()`: IAM role creation

## Benefits of This Architecture

1. **Configuration-Driven**: All settings managed in single YAML file
2. **Reusable Components**: Shared utility functions across agents
3. **Secure by Default**: OAuth 2.0 with JWT tokens and scoped access
4. **Self-Healing**: Automatic token refresh and error recovery
5. **Scalable**: Supports multiple gateways and targets
6. **Maintainable**: Clear separation of concerns and modular design

## Usage

The refactored system automatically handles all gateway setup based on configuration:

```python
# Agent initialization automatically:
# 1. Reads config.yaml
# 2. Sets up/reuses Cognito resources
# 3. Creates/finds gateway
# 4. Generates access tokens
# 5. Provides authenticated MCP client

agent = Agent(
    system_prompt=MONITORING_AGENT_SYSTEM_PROMPT,
    model=bedrock_model,
    hooks=hooks,
    tools=gateway_tools  # Automatically authenticated
)
```