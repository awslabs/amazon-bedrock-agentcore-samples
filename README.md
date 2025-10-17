<div align="center">
  <div>
    <a href="https://aws.amazon.com/bedrock/agentcore/">
      <img width="150" height="150" alt="image" src="https://github.com/user-attachments/assets/b8b9456d-c9e2-45e1-ac5b-760f21f1ac18" />
   </a>
  </div>

  <h1>
      Amazon Bedrock AgentCore Samples
  </h1>

  <h2>
    Deploy and operate AI agents securely at scale - using any framework and model
  </h2>

  <div align="center">
    <a href="https://github.com/awslabs/amazon-bedrock-agentcore-samples/graphs/commit-activity"><img alt="GitHub commit activity" src="https://img.shields.io/github/commit-activity/m/awslabs/amazon-bedrock-agentcore-samples"/></a>
    <a href="https://github.com/awslabs/amazon-bedrock-agentcore-samples/issues"><img alt="GitHub open issues" src="https://img.shields.io/github/issues/awslabs/amazon-bedrock-agentcore-samples"/></a>
    <a href="https://github.com/awslabs/amazon-bedrock-agentcore-samples/pulls"><img alt="GitHub open pull requests" src="https://img.shields.io/github/issues-pr/awslabs/amazon-bedrock-agentcore-samples"/></a>
    <a href="https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/awslabs/amazon-bedrock-agentcore-samples"/></a>
  </div>
  
  <p>
    <a href="https://docs.aws.amazon.com/bedrock-agentcore/">Documentation</a>
    ◆ <a href="https://github.com/aws/bedrock-agentcore-sdk-python">Python SDK</a>
    ◆ <a href="https://github.com/aws/bedrock-agentcore-starter-toolkit">Starter Toolkit </a>
    ◆ <a href="https://discord.gg/bedrockagentcore-preview">Discord</a>
  </p>
</div>

Welcome to the Amazon Bedrock AgentCore Samples repository! 

Amazon Bedrock AgentCore is both framework-agnostic and model-agnostic, giving you the flexibility to deploy and operate advanced AI agents securely and at scale. Whether you’re building with [Strands Agents](https://strandsagents.com/latest/), [CrewAI](https://www.crewai.com/), [LangGraph](https://www.langchain.com/langgraph), [LlamaIndex](https://www.llamaindex.ai/), or any other framework—and running them on any Large Language Model (LLM)—Amazon Bedrock AgentCore provides the infrastructure to support them. By eliminating the undifferentiated heavy lifting of building and managing specialized agent infrastructure, Amazon Bedrock AgentCore lets you bring your preferred framework and model, and deploy without rewriting code.

This collection provides examples and tutorials to help you understand, implement, and integrate Amazon Bedrock AgentCore capabilities into your applications.

> [!IMPORTANT]
> The examples provided in this repository are for experimental and educational purposes only. They demonstrate concepts and techniques but are not intended for direct use in production environments.

## 🎥 Video

Build your first production-ready AI agent with Amazon Bedrock AgentCore. We’ll take you beyond prototyping and show you how to productionize your first agentic AI application using Amazon Bedrock AgentCore. 

<p align="center">
  <a href="https://www.youtube.com/watch?v=wzIQDPFQx30"><img src="https://markdown-videos-api.jorgenkh.no/youtube/wzIQDPFQx30?width=640&height=360&filetype=jpeg" /></a>
</p>

## 📁 Repository Structure

### 📚 [`01-tutorials/`](./01-tutorials/)
**Interactive Learning & Foundation**

This folder contains notebook-based tutorials that teach you the fundamentals of Amazon Bedrock AgentCore capabilities through hands-on examples.

The structure is divided by AgentCore component:
* **[Runtime](./01-tutorials/01-AgentCore-runtime)**: Amazon Bedrock AgentCore Runtime is a secure, serverless runtime capability that empowers organizations to deploy and scale both AI agents and tools, regardless of framework, protocol, or model choice—enabling rapid prototyping, seamless scaling, and accelerated time to market
* **[Gateway](./01-tutorials/02-AgentCore-gateway)**: AI agents need tools to perform real-world tasks—from searching databases to sending messages. Amazon Bedrock AgentCore Gateway automatically converts APIs, Lambda functions, and existing services into MCP-compatible tools so developers can quickly make these essential capabilities available to agents without managing integrations. 
* **[Memory](./01-tutorials/03-AgentCore-identity)**: Amazon Bedrock AgentCore Memory makes it easy for developer to build rich, personalized agent experiences with fully-manged memory infrastructure and the ability to customize memory for your needs.
* **[Identity](./01-tutorials/04-AgentCore-memory)**: Amazon Bedrock AgentCore Identity provides seamless agent identity and access management across AWS services and third-party applications such as Slack and Zoom while supporting any standard identity providers such as Okta, Entra, and Amazon Cognito.
* **[Tools](./01-tutorials/05-AgentCore-tools)**: Amazon Bedrock AgentCore provides two built-in tools to simplify your agentic AI application development: Amazon Bedrock AgentCore **Code Interpreter** tool enables AI agents to write and execute code securely, enhancing their accuracy and expanding their ability to solve complex end-to-end tasks. Amazon Bedrock AgentCore **Browser Tool** is an enterprise-grade capability that enables AI agents to navigate websites, complete multi-step forms, and perform complex web-based tasks with human-like precision within a fully managed, secure sandbox environment with low latency
* **[Observability](./01-tutorials/06-AgentCore-observability)**: Amazon Bedrock AgentCore Observability helps developers trace, debug, and monitor agent performance through unified operational dashboards. With support for OpenTelemetry compatible telemetry and detailed visualizations of each step of the agent workflow, Amazon Bedrock AgentCore Observability enables developers to easily gain visibility into agent behavior and maintain quality standards at scale.

* **[AgentCore end-to-end](./01-tutorials/07-AgentCore-E2E)**: In this tutorial we will move a customer support agent from prototype to production using Amazon Bedrock AgentCore services.


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

## Running a Notebook

1. Create and activate a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Export/Activate required AWS Credentials for the notebook to run

4. Register your virtual environment as a kernel for Jupyter notebook to use
```bash
python -m ipykernel install --user --name=notebook-venv --display-name="Python (notebook-venv)"
```

You can list your kernels using:
```bash
jupyter kernelspec list
```

5. Run the notebook and ensure the correct kernel is selected
```bash
jupyter notebook path/to/your/notebook.ipynb
```

**Important:** After opening the notebook in Jupyter, make sure to select the correct kernel by going to `Kernel` → `Change kernel` → select "Python (notebook-venv)" to ensure your virtual environment packages are available.


## Quick Start - [Amazon Bedrock AgentCore Runtime](https://github.com/aws/bedrock-agentcore-starter-toolkit/blob/main/documentation/docs/user-guide/runtime/quickstart.md)

### Step 1: Prerequisites

- An [AWS account](https://signin.aws.amazon.com/signin?redirect_uri=https%3A%2F%2Fportal.aws.amazon.com%2Fbilling%2Fsignup%2Fresume&client_id=signup) with credentials configured (`aws configure`)
- [Python 3.10](https://www.python.org/downloads/) or later
- [Docker](https://www.docker.com/) or [Finch](https://runfinch.com/) installed and running - only for local development
- Model Access: Anthropic Claude 4.0 enabled in [Amazon Bedrock console](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-modify.html)
- AWS Permissions:
    - `BedrockAgentCoreFullAccess` managed policy
    - `AmazonBedrockFullAccess` managed policy
    - `Caller permissions`: See detailed policy [here](https://github.com/aws/bedrock-agentcore-starter-toolkit/blob/main/documentation/docs/user-guide/runtime/permissions.md#developercaller-permissions)

### Step 2: Install and Create Your Agent

```bash
# Install both packages
pip install bedrock-agentcore strands-agents bedrock-agentcore-starter-toolkit
```

Create `my_agent.py`:

```python
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent

app = BedrockAgentCoreApp()
agent = Agent()

@app.entrypoint
def invoke(payload):
    """Your AI agent function"""
    user_message = payload.get("prompt", "Hello! How can I help you today?")
    result = agent(user_message)
    return {"result": result.message}

if __name__ == "__main__":
    app.run()
```
Create `requirements.txt`:

```bash
cat > requirements.txt << EOF
bedrock-agentcore
strands-agents
EOF
```
### Step 3: Test Locally

```bash
# Start your agent
python my_agent.py

# Test it (in another terminal)
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello!"}'
```
Success: You should see a response like {"result": "Hello! I'm here to help..."}

### Step 4: Deploy to AWS

```bash
# Configure and deploy (auto-creates all required resources)
agentcore configure -e my_agent.py
agentcore launch

# Test your deployed agent
agentcore invoke '{"prompt": "tell me a joke"}'
```

Congratulations! Your agent is now running on Amazon Bedrock AgentCore Runtime!

Follow quickstart guides for [Gatway](https://github.com/aws/bedrock-agentcore-starter-toolkit/blob/main/documentation/docs/user-guide/gateway/quickstart.md), [Identity](https://github.com/aws/bedrock-agentcore-starter-toolkit/blob/main/documentation/docs/user-guide/identity/quickstart.md), [Memory](https://github.com/aws/bedrock-agentcore-starter-toolkit/blob/main/documentation/docs/user-guide/memory/quickstart.md), [Observability](https://github.com/aws/bedrock-agentcore-starter-toolkit/blob/main/documentation/docs/user-guide/observability/quickstart.md), and [builtin-tools](https://github.com/aws/bedrock-agentcore-starter-toolkit/tree/main/documentation/docs/user-guide/builtin-tools). 

## 🔗 Related Links:

- [Getting started with Amazon Bedrock AgentCore - Workshop](https://catalog.us-east-1.prod.workshops.aws/workshops/850fcd5c-fd1f-48d7-932c-ad9babede979/en-US)
- [Diving Deep into Bedrock AgentCore - Workshop](https://catalog.workshops.aws/agentcore-deep-dive/en-US)
- [Amazon Bedrock AgentCore pricing](https://aws.amazon.com/bedrock/agentcore/pricing/)
- [Amazon Bedrock AgentCore FAQs](https://aws.amazon.com/bedrock/agentcore/faqs/)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on:

- Adding new samples
- Improving existing examples
- Reporting issues
- Suggesting enhancements


## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.


## Contributors

<a href="https://github.com/awslabs/amazon-bedrock-agentcore-samples/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=awslabs/amazon-bedrock-agentcore-samples" />
</a>
