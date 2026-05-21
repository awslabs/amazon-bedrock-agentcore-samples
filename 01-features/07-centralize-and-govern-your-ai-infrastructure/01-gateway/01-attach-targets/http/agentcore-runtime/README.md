# Attach AgentCore runtime as HTTP Target

You can add an Amazon Bedrock AgentCore runtime agent as a gateway target. The gateway sends traffic directly to the runtime agent without aggregation or protocol translation. Unlike MCP targets that combine tool capabilities into a unified virtual MCP server, the AgentCore runtime target forwards requests and responses between clients and the runtime agent without modification.

![architecture](./images/architecture.png)

Adding an AgentCore runtime target to your gateway is useful when you want to:

1. Provide centralized access management for your runtime agents through a single gateway endpoint.

2. Use the gateway’s built-in authentication and observability for your runtime agents.

3. Route requests to specific runtime agents using path-based routing when multiple targets are attached to a gateway.

4. Optimize your agent’s performance by using [Amazon Bedrock AgentCore optimization](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/optimization.html) to generate recommendations from agent traces, A/B test changes with live traffic through the gateway, and deploy winning configurations. For more information, see AgentCore optimization.

## Target configuration

```bash
{
    "http": {
        "agentcoreRuntime": {
            "arn": "arn:aws:bedrock-agentcore:us-west-2:111122223333:runtime/RUNTIME_ID",
            "qualifier": "DEFAULT"
        }
    }
}
```

## Invoking an AgentCore runtime target

To invoke an AgentCore runtime target through the gateway, send a POST request to the target’s invocation URL. The URL format is:

```bash
https://{gatewayId}.gateway.bedrock-agentcore.{region}.amazonaws.com/{targetName}/invocations
```

## Documentation

- [AgentCore gateway Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
- [AgentCore runtime Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)
