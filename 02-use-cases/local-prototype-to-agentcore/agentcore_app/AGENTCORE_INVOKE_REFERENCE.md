# AgentCore Invoke Command Reference

## Correct Syntax

### ✅ Recommended (Payload First)
```bash
agentcore invoke '{"user_input": "your question"}' --bearer-token $BEARER_TOKEN
```

### ✅ Alternative (With Separator)
```bash
agentcore invoke --bearer-token $BEARER_TOKEN -- '{"user_input": "your question"}'
```

### ❌ Wrong (Missing Separator)
```bash
# This will fail with "Missing argument 'PAYLOAD'"
agentcore invoke --bearer-token $BEARER_TOKEN '{"user_input": "your question"}'
```

## Common Examples

### Basic Invocation
```bash
agentcore invoke '{"user_input": "Can you help me get a quote for auto insurance?"}'
```

### With Bearer Token (OAuth)
```bash
export BEARER_TOKEN=$(jq -r '.bearer_token' 1_pre_req_setup/cognito_auth/cognito_config.json)
agentcore invoke '{"user_input": "test"}' --bearer-token $BEARER_TOKEN
```

### With Actor ID and Session ID
```bash
agentcore invoke '{"user_input": "test", "actor_id": "user123", "session_id": "abc-123"}'
```

### With Session ID Only
```bash
agentcore invoke '{"user_input": "test"}' --session-id abc-123
```

## Full Command Options

```bash
agentcore invoke [OPTIONS] PAYLOAD

Options:
  --agent, -a TEXT          Agent name
  --session-id, -s TEXT     Session ID
  --bearer-token, -bt TEXT  Bearer token for OAuth authentication
  --local, -l               Send request to a running local container
  --user-id, -u TEXT        User ID for authorization flows
```

## JSON Payload Format

### Required Fields
```json
{
  "user_input": "your question here"
}
```

### Optional Fields
```json
{
  "user_input": "your question here",
  "actor_id": "user123",           // For memory tracking
  "session_id": "abc-123"           // For conversation continuity
}
```

## Shell Quoting Rules

### Single Quotes (Recommended)
```bash
# Use single quotes to prevent shell expansion
agentcore invoke '{"user_input": "test"}'
```

### Double Quotes (Requires Escaping)
```bash
# If using double quotes, escape inner quotes
agentcore invoke "{\"user_input\": \"test\"}"
```

### Environment Variables in JSON
```bash
# Use double quotes and escape to include variables
agentcore invoke "{\"user_input\": \"test\", \"actor_id\": \"$USER\"}"
```

## Testing Commands

### Quick Test
```bash
agentcore invoke '{"user_input": "hello"}'
```

### Full Test with Authentication
```bash
# Get bearer token
export BEARER_TOKEN=$(jq -r '.bearer_token' 1_pre_req_setup/cognito_auth/cognito_config.json)

# Invoke with token
agentcore invoke '{"user_input": "Can you help me get a quote?"}' --bearer-token $BEARER_TOKEN
```

### Test with Specific Session
```bash
agentcore invoke '{"user_input": "test", "actor_id": "test-user", "session_id": "test-session-1"}'
```

## Troubleshooting

### Error: "Missing argument 'PAYLOAD'"
**Cause**: Options placed after payload without separator
**Fix**: Put payload first, or use `--` separator

```bash
# Wrong
agentcore invoke --bearer-token $TOKEN '{"user_input": "test"}'

# Right
agentcore invoke '{"user_input": "test"}' --bearer-token $TOKEN
```

### Error: "Invalid JSON"
**Cause**: Shell expanded variables or special characters
**Fix**: Use single quotes or escape properly

```bash
# Wrong (shell expands $USER)
agentcore invoke '{"user_input": "hello $USER"}'

# Right
agentcore invoke '{"user_input": "hello"}'
```

### Error: "Unauthorized"
**Cause**: Missing or expired bearer token
**Fix**: Refresh token and export

```bash
cd 1_pre_req_setup/cognito_auth
./refresh_token.sh
export BEARER_TOKEN=$(jq -r '.bearer_token' cognito_config.json)
```

## Quick Reference Card

```bash
# Basic
agentcore invoke '{"user_input": "test"}'

# With auth
agentcore invoke '{"user_input": "test"}' --bearer-token $BEARER_TOKEN

# With session
agentcore invoke '{"user_input": "test"}' --session-id abc-123

# Full example
agentcore invoke '{"user_input": "Can you help me?", "actor_id": "user123"}' --bearer-token $BEARER_TOKEN
```

## See Also

- [README.md](README.md) - Main documentation
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Deployment instructions
- [TROUBLESHOOTING_SUMMARY.md](TROUBLESHOOTING_SUMMARY.md) - Common issues
