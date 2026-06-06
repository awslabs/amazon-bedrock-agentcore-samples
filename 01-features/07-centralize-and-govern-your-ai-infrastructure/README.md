# AI Governance Layer

## AgentCore CLI

Add a gateway to a runtime project with the AgentCore CLI:

```bash
npm install -g @aws/agentcore

# Add a gateway interactively
agentcore add gateway

# Add a gateway target (Lambda, MCP server, OpenAPI, or Smithy)
agentcore add gateway-target --type lambda-function-arn --gateway mygateway --lambda-arn $LAMBDA_ARN

# Deploy all resources
agentcore deploy
```

See [`01-gateway/README.md`](01-gateway/README.md) for the full CLI reference.

## Documentation

- [AgentCore gateway Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
- [AgentCore policy Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html)
- [AWS Agent registry Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/registry.html)
