# Amazon Bedrock AgentCore gateway Targets

![arch](../images/architecture.png)

Targets define the tools that your AgentCore gateway will host. AgentCore gateway supports two categories of targets:

- **MCP targets**: operate in aggregation mode. AgentCore gateway acts as an MCP server whose capabilities combine those of all its MCP targets into a single unified virtual MCP server.

- **HTTP targets**: AgentCore gateway sends traffic directly to HTTP targets without aggregation or protocol translation. You define tools using an OpenAPI or Smithy schema so that agents can discover and invoke them.

You can attach different AgentCore identity Credential Providers to different targets, which lets you securely control outbound authentication on a per-target basis.

## Tutorials

| Section       | Description                                                          |
| :------------ | :------------------------------------------------------------------- |
| [http](http/) | Attach targets in HTTP mode                                                  |
| [mcp](mcp/)   | Attach targets in MCP mode |

## Documentation

- [AgentCore gateway Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
