# HTTP Targets

> [!NOTE]
> AgentCore runtime targets for gateway are in public preview. Features and APIs may change before general availability.

![arch](../../images/architecture.png)

For HTTP targets, the gateway sends traffic directly to the target without aggregation or protocol translation. Unlike MCP targets, HTTP targets do not support capability synchronization or semantic tool search. Clients address each target individually through path-based routing.

![architecture](../../images/proxy.png)

You can attach different AgentCore identity Credential Providers to each HTTP target to securely manage outbound authentication on a per-target basis. You can also configure Token passthrough, in which gateway validates the inbound token and passes it through to the runtime target without modification. This is useful when the runtime handles its own authorization.

## Tutorials

| Section                                 | Description                                            |
| :-------------------------------------- | :----------------------------------------------------- |
| [agentcore-runtime](agentcore-runtime/) | Attach an AgentCore runtime endpoint as an HTTP target |

## Documentation

- [AgentCore gateway Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
- [HTTP targets](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-targets-http.html)
