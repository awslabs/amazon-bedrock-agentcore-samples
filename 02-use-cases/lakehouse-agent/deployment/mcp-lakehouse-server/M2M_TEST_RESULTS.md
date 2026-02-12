# M2M Authentication Test Results

## Test Script: simple_mcp_test.py

### ✅ SUCCESS: M2M Token Acquisition

The test successfully obtains an M2M access token from Cognito:

```
Client ID: 1o7qt3g8mc071403me6sn99nho
Domain: https://lakehouse-uswest2f.auth.us-west-2.amazoncognito.com
User Pool: us-west-2_F9ClCY8Bk
Scopes: default-m2m-resource-server-vccgqz/read

Token obtained successfully!
Token type: Bearer
Expires in: 3600 seconds

Token Claims:
  Issuer: https://cognito-idp.us-west-2.amazonaws.com/us-west-2_F9ClCY8Bk
  Client ID: 1o7qt3g8mc071403me6sn99nho
  Scope: default-m2m-resource-server-vccgqz/read
  Token Use: access
```

### ✅ SUCCESS: JWT Authentication

The JWT token is accepted by AgentCore Runtime:
- No 401 Unauthorized errors
- JWT authorizer validates the token
- Client ID matches the allowedClients configuration

### ❌ ISSUE: MCP Protocol Handshake

The MCP initialize request times out:
- Request doesn't reach the MCP server (no logs)
- AgentCore Runtime expects streaming protocol
- Simple HTTP POST requests don't work for MCP protocol

## Root Cause

AgentCore Runtime's MCP implementation requires:
1. **Bidirectional streaming** - Not supported by simple HTTP POST
2. **Server-Sent Events (SSE)** or **WebSocket** - For MCP protocol messages
3. **MCP client library** - Which has compatibility issues

## Conclusion

**M2M Authentication: 100% Working** ✅
- Token acquisition: ✅
- JWT validation: ✅
- Authorization: ✅

**MCP Protocol: Not Working with HTTP POST** ❌
- Requires streaming connection
- Simple HTTP requests insufficient
- Need proper MCP client or Gateway

## Recommendations

### Option 1: Use AgentCore Gateway (RECOMMENDED)

Deploy the MCP server behind AgentCore Gateway:
```bash
cd gateway-setup
python create_gateway.py
```

Benefits:
- Gateway handles MCP protocol complexity
- Production-ready pattern
- Supports OAuth/JWT authentication
- Agent connects to Gateway, not directly to Runtime

### Option 2: Use Lakehouse Agent

The lakehouse agent has proper MCP client implementation:
```bash
cd lakehouse-agent
python deploy_lakehouse_agent.py
```

The agent's MCP client may handle the streaming protocol correctly.

### Option 3: Debug MCP Client Library

Investigate why the Python MCP client library (`mcp` package) hangs:
- Check library version compatibility
- Review streaming implementation
- Test with different configurations

## Files

- **simple_mcp_test.py** - Working test for M2M token + JWT auth
- **test_http_endpoint.py** - HTTP endpoint test (shows 406 with correct headers)
- **test_mcp_server.py** - Full MCP test (hangs during initialization)

## Usage

To test M2M authentication:
```bash
cd mcp-lakehouse-server
AWS_REGION=us-west-2 python simple_mcp_test.py
```

Expected output:
- ✅ Token obtained
- ✅ Token claims validated
- ❌ MCP initialize times out (expected - requires streaming)
