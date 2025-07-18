# Bedrock AgentCore Gateway AWS Operations Agent Client

---
## 📋 Navigation
**🏠 [README](../README.md)** | **📖 [Setup Guide](../docs/SETUP.md)** | **🏗️ [Architecture](../docs/ARCHITECTURE-FLOW.md)** | **🔧 [Scripts](../scripts/README.md)** | **🤖 [Client](README.md)** | **⚙️ [Config](../configs/README.md)** | **🔐 [Okta Setup](../okta-auth/OKTA-OPENID-PKCE-SETUP.md)**
---

This directory contains the AWS Operations Agent client that connects to your Bedrock AgentCore Gateway production setup.

## Structure

```
client/
├── README.md                # This file
├── requirements.txt         # Python dependencies
├── run_client.sh            # Convenience script
├── src/
│   ├── auth.py              # AWS authentication
│   ├── cli_interface.py     # Command-line interface
│   ├── commands.py          # Client commands
│   ├── config.py            # Client configuration
│   ├── conversation.py      # Conversation management
│   ├── lambda_client.py     # Lambda API client
│   ├── main.py              # Entry point
│   ├── mcp_tools.py         # MCP tools manager
│   └── save_token.py        # Token management
└── token.txt                # Okta token (create this file)
```

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create token file:
   ```bash
   # Option 1: Use save_token.py script
   python src/save_token.py
   
   # Option 2: Create token file manually
   echo "YOUR_OKTA_ACCESS_TOKEN" > token.txt
   ```

3. Run the client:
   ```bash
   # Option 1: Use convenience script
   ./run_client.sh
   
   # Option 2: Run directly
   python src/main.py
   ```

## Usage

```
AWS Operational Support Agent - Natural language AWS operations

Commands:
  /help                 Show this help message
  /clear                Clear current conversation
  /tools                List available MCP tools
  /quit                 Exit the application
  /token <token>        Set Okta token
  /token-file <path>    Load Okta token from file
```

## Command-line Arguments

- `--url` - Lambda Function URL (default: from config)
- `--region` - AWS region (default: us-east-1)
- `--profile` - AWS profile (default: demo1)
- `--token` - Okta token for Bedrock AgentCore Gateway authentication
- `--token-file` - Path to file containing Okta token

## Configuration

Your client is configured to work with:
- **Bedrock AgentCore Gateway**: `https://example-gateway-abc123def456.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp`
- **Target**: `EXAMPLE123` with 20 AWS service tools
- **Lambda**: `example-operations-agent` function

## Example Commands

```
> What time is it? Use the get_time tool.
> List my S3 buckets
> Show me EC2 instances in us-east-1
> What Lambda functions do I have?
> How many CloudFormation stacks are in FAILED state?
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**:
   - Check that your Okta token is valid and not expired
   - Verify AWS credentials with `aws sts get-caller-identity --profile demo1`

2. **Connection Issues**:
   - Verify Lambda Function URL is correct
   - Check network connectivity

3. **Tool Execution Errors**:
   - Verify target is properly configured
   - Check Lambda logs for detailed error messages

### Debug Commands

```bash
# Check token file
cat token.txt | head -c 20

# Test Lambda Function URL directly
curl -X POST https://<function-url>/chat \
  --header "Content-Type: application/json" \
  --data '{"message":"Hello"}'
```

---
