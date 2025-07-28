# Amazon Bedrock AgentCore Samples

Welcome to the Amazon Bedrock AgentCore Samples repository!

> [!CAUTION]
> The examples provided in this repository are for experimental and educational purposes only. They demonstrate concepts and techniques but are not intended for direct use in production environments. Make sure to have Amazon Bedrock Guardrails in place to protect against [prompt injection](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-injection.html).

**Amazon Bedrock AgentCore** is a complete set of capabilities to deploy and operate agents securely, at scale using any agentic framework and any LLM model.
With it, developers can accelerate AI agents into production quickly, accelerating the business value timelines.

Amazon Bedrock AgentCore provides tools and capabilities to make agents more effective and capable, purpose-built infrastructure to securely scale agents, and controls to operate trustworthy agents.

Amazon Bedrock AgentCore capabilities are composable and work with popular open-source frameworks and any model, so you don’t have to choose between open-source flexibility and enterprise-grade security and reliability.

This collection provides examples and tutorials to help you understand, implement, and integrate Amazon Bedrock AgentCore capabilities into your applications.

## 📁 Repository Structure

### 📚 [`01-tutorials/`](./01-tutorials/)

#### Interactive Learning & Foundation**

This folder contains notebook-based tutorials that teach you the fundamentals of Amazon Bedrock AgentCore capabilities through hands-on examples.

The structure is divided by AgentCore component:

* **Runtime**: Amazon Bedrock AgentCore Runtime is a secure, serverless runtime capability that empowers organizations to deploy and scale both AI agents and tools, regardless of framework, protocol, or model choice—enabling rapid prototyping, seamless scaling, and accelerated time to market
* **Gateway**: AI agents need tools to perform real-world tasks—from searching databases to sending messages. Amazon Bedrock AgentCore Gateway automatically converts APIs, Lambda functions, and existing services into MCP-compatible tools so developers can quickly make these essential capabilities available to agents without managing integrations.
* **Memory**: Amazon Bedrock AgentCore Memory makes it easy for developer to build rich, personalized agent experiences with fully-manged memory infrastructure and the ability to customize memory for your needs.
* **Identity**: Amazon Bedrock AgentCore Identity provides seamless agent identity and access management across AWS services and third-party applications such as Slack and Zoom while supporting any standard identity providers such as Okta, Entra, and Amazon Cognito.
* **Tools**: Amazon Bedrock AgentCore provides two built-in tools to simplify your agentic AI application development: Amazon Bedrock AgentCore **Code Interpreter** tool enables AI agents to write and execute code securely, enhancing their accuracy and expanding their ability to solve complex end-to-end tasks. Amazon Bedrock AgentCore **Browser Tool** is an enterprise-grade capability that enables AI agents to navigate websites, complete multi-step forms, and perform complex web-based tasks with human-like precision within a fully managed, secure sandbox environment with low latency
* **Observability**: Amazon Bedrock AgentCore Observability helps developers trace, debug, and monitor agent performance through unified operational dashboards. With support for OpenTelemetry compatible telemetry and detailed visualizations of each step of the agent workflow, Amazon Bedrock AgentCore Observability enables developers to easily gain visibility into agent behavior and maintain quality standards at scale.

The **end-to-end example** folder provide a simple example of how to combine the different capabilities
on a use case.

The examples provided as perfect for beginners and those looking to understand the underlying concepts before building AI Agents applications.

### 💡 [`02-use-cases/`](./02-use-cases/)

#### End-to-end Applications**

Explore practical use case implementations that demonstrate how to apply Amazon Bedrock AgentCore capabilities to solve real business problems.

Each use case includes complete implementation focused on the AgentCore components with detailed explanations.

### 🔌 [`03-integrations/`](./03-integrations/)

#### Framework & Protocol Integration**

Learn how to integrate Amazon Bedrock AgentCore capabilities with popular Agentic frameworks such as Strands Agents, LangChain and CrewAI.

Set agent-to-agent communication with A2A and different multi-agent collaboration patterns. Integrate agentic interfaces and learn how to use Amazon Bedrock AgentCore with different entry points.

## 🚀 Quick Start

| Component | Tutorial | Description |
|-----------|----------|-------------|
| **Runtime** | [AI Agents Hosting](./01-tutorials/01-AgentCore-runtime/01-hosting-agent/) | Host [Strands](https://strandsagents.com/latest/), [LangGraph](https://www.langchain.com/langgraph), and [CrewAi](https://www.crewai.com/) agents with AgentCore Runtime |
| **Runtime** | [MCP Server Hosting](./01-tutorials/01-AgentCore-runtime/02-hosting-MCP-server/hosting_mcp_server.ipynb) | Host [MCP](https://modelcontextprotocol.io/overview) servers with AgentCore Runtime |
| **Gateway** | [Lambda to MCP Tools](./01-tutorials/02-AgentCore-gateway/01-transform-lambda-into-mcp-tools/01-gateway-target-lambda.ipynb) | Transform Lambda functions into [MCP](https://modelcontextprotocol.io/overview) tools |
| **Gateway** | [OpenAPI to MCP (API Key)](./01-tutorials/02-AgentCore-gateway/02-transform-apis-into-mcp-tools/02-transform-openapi-into-mcp-tools/01-openapis-into-mcp-api-key.ipynb) | Transform OpenAPI specs into [MCP](https://modelcontextprotocol.io/overview) tools with API key auth |
| **Gateway** | [OpenAPI to MCP (OAuth)](./01-tutorials/02-AgentCore-gateway/02-transform-apis-into-mcp-tools/02-transform-openapi-into-mcp-tools/02-openapis-into-mcp-oauth-enterpris-apis.ipynb) | Transform OpenAPI specs into [MCP](https://modelcontextprotocol.io/overview) tools with OAuth |
| **Gateway** | [Smithy APIs to MCP](./01-tutorials/02-AgentCore-gateway/02-transform-apis-into-mcp-tools/03-transform-smithyapis-into-mcp-tools/01-s3-smithy-into-mcp-iam.ipynb) | Transform Smithy APIs into [MCP](https://modelcontextprotocol.io/overview) tools |
| **Identity** | [Create agent and tool identities with AgentCore Identity](./01-tutorials/03-AgentCore-identity/03-Inbound%20Auth%20example/inbound_auth_runtime_with_strands_and_bedrock_models.ipynb) | Configure secure authentication, authorization, and credential management capabilities that enable agents and tools to access AWS resources and third-party services on behalf of users |
| **Memory** | [Short-term Memory](./01-tutorials/04-AgentCore-memory/01-short-term-memory/) | Add Short-term memory to you AI agents |
| **Memory** | [Long-term Memory](./01-tutorials/04-AgentCore-memory/02-long-term-memory/) | Add Long-term memory to you AI agents |
| **Tools** | [AgentCore Built-in tools](./01-tutorials/05-AgentCore-tools/) | Use Amazon Bedrock AgentCore built-in tools to interact with your applications |
| **Observability** | [Observability for AgentCore Runtime](./01-tutorials/06-AgentCore-observability/01-Agentcore-runtime-hosted/runtime_with_strands_and_bedrock_models.ipynb) | Observability for AgentCore Runtime hosted agents |
| **Observability** | [Observability for Open Source Agents](./01-tutorials/06-AgentCore-observability/02-Agent-not-hosted-on-runtime/) | Observability for [Strands](https://strandsagents.com/latest/), [LangGraph](https://www.langchain.com/langgraph), and [CrewAi](https://www.crewai.com/) agents |

## 📋 Prerequisites

* Python 3.10 or higher
* AWS account
* Docker or Finch installed and running
* Jupyter Notebook (for tutorials)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on:

* Adding new samples
* Improving existing examples
* Reporting issues
* Suggesting enhancements

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

* **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/awslabs/amazon-bedrock-agentcore-samples/issues)
* **Documentation**: Check individual folder READMEs for specific guidance

## 🔄 Updates

This repository is actively maintained and updated with new capabilities and examples. Watch the repository to stay updated with the latest additions.
