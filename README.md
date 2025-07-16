# Amazon Bedrock AgentCore Samples

Welcome to the Amazon Bedrock AgentCore Samples repository! 

> [!CAUTION]
> The examples provided in this repository are for experimental and educational purposes only. They demonstrate concepts and techniques but are not intended for direct use in production environments. Make sure to have Amazon Bedrock Guardrails in place to protect against [prompt injection](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-injection.html). 

**Amazon Bedrock AgentCore** is a complete set of capabilities to deploy and operate agents securely, at scale using any agentic framework and any LLM model. 
With it, developers can accelerate AI agents into production quickly, accelerating the business value timelines. 

Amazon Bedrock AgentCore provides tools and capabilities to make agents more effective and capable, purpose-built infrastructure to securely scale agents, and 
controls to operate trustworthy agents. 

Amazon Bedrock AgentCore capabilities are composable and work with popular open-source frameworks and any model, so you don’t have to choose between 
open-source flexibility and enterprise-grade security and reliability.

This collection provides examples and tutorials to help you understand, implement, and integrate Amazon Bedrock AgentCore capabilities into your applications.

## 📁 Repository Structure

### 📚 [`01-tutorials/`](./01-tutorials/)
**Interactive Learning & Foundation**

This folder contains notebook-based tutorials that teach you the fundamentals of Amazon Bedrock AgentCore capabilities through hands-on examples.

The structure is divided by AgentCore component:
* **Runtime**: Amazon Bedrock AgentCore Runtime is a secure, serverless runtime capability that empowers organizations to deploy and scale both AI agents and tools, regardless of framework, protocol, or model choice—enabling rapid prototyping, seamless scaling, and accelerated time to market
* **Gateway**: AI agents need tools to perform real-world tasks—from searching databases to sending messages. Amazon Bedrock AgentCore Gateway automatically converts APIs, Lambda functions, and existing services into MCP-compatible tools so developers can quickly make these essential capabilities available to agents without managing integrations. 
* **Memory**: Amazon Bedrock AgentCore Memory makes it easy for developer to build rich, personalized agent experiences with fully-manged memory infrastructure and the ability to customize memory for your needs.
* **Identity**: Amazon Bedrock AgentCore Identity provides seamless agent identity and access management across AWS services and third-party applications such as Slack and Zoom while supporting any standard identity providers such as Okta, Entra, and Amazon Cognito.
* **AgentCore tools**: Amazon Bedrock AgentCore provides two built-in tools to simplify your agentic AI application development: Amazon Bedrock AgentCore **Code Interpreter** tool enables AI agents to write and execute code securely, enhancing their accuracy and expanding their ability to solve complex end-to-end tasks. Amazon Bedrock AgentCore **Browser Tool** is an enterprise-grade capability that enables AI agents to navigate websites, complete multi-step forms, and perform complex web-based tasks with human-like precision within a fully managed, secure sandbox environment with low latency


The **end-to-end example** folder provide a simple example of how to combine the different capabilities
on a use case.

The examples provided as perfect for beginners and those looking to understand the underlying concepts before building AI Agents applications.

### 💡 [`02-use-cases/`](./02-use-cases/)
**End-to-end Applications**

Explore practical use case implementations that demonstrate how to apply Amazon Bedrock AgentCore capabilities to solve real business problems.

Each use case includes complete implementation focused on the AgentCore components with detailed explanations.

### 🔌 [`03-integrations/`](./03-integrations/)
**Framework & Protocol Integration**

Learn how to integrate Amazon Bedrock AgentCore capabilities with popular Agentic frameworks such as Strands Agents, LangChain and CrewAI.

Set agent-to-agent communication with A2A and different multi-agent collaboration patterns. Integrate agentic interfaces and learn how to use 
Amazon Bedrock AgentCore with different entry points.

## 🚀 Quick Start

1. **Clone the repository**

   ```bash
   git clone https://github.com/awslabs/amazon-bedrock-agentcore-samples.git
   ```

2. **Set up your environment**

   ```bash
   pip install bedrock_agentcore
   ```

3. **Start with tutorials**
   ```bash
   cd 01-tutorials
   jupyter notebook
   ```

## 📋 Prerequisites

- Python 3.10 or higher
- AWS account
- Jupyter Notebook (for tutorials)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on:

- Adding new samples
- Improving existing examples
- Reporting issues
- Suggesting enhancements

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/awslabs/amazon-bedrock-agentcore-samples/issues)
- **Documentation**: Check individual folder READMEs for specific guidance

## 🔄 Updates

This repository is actively maintained and updated with new capabilities and examples. Watch the repository to stay updated with the latest additions.
