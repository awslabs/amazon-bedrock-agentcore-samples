# 🔌 Amazon Bedrock AgentCore Integrations

Welcome to the integrations section of the Amazon Bedrock AgentCore samples repository!

This folder contains framework and protocol integrations that demonstrate how to connect Amazon Bedrock AgentCore with popular agentic frameworks, identity providers, observability tools, and AWS services.

## 🤖 Agentic Frameworks

* **[ADK](./agentic-frameworks/adk/)**: Agent Development Kit integration with Google Search
* **[AutoGen](./agentic-frameworks/autogen/)**: Multi-agent conversation frameworks
* **[CrewAI](./agentic-frameworks/crewai/)**: Collaborative AI agent orchestration
* **[LangChain](./agentic-frameworks/langchain/)**: Chain-based agent workflows and tool integration
* **[LangGraph](./agentic-frameworks/langgraph/)**: Multi-agent workflows with web search capabilities
* **[LlamaIndex](./agentic-frameworks/llamaindex/)**: Document processing and retrieval-augmented generation
* **[OpenAI Agents](./agentic-frameworks/openai-agents/)**: OpenAI Assistant API integration with handoff patterns
* **[PydanticAI](./agentic-frameworks/pydanticai-agents/)**: Type-safe agent development with Bedrock models
* **[Strands Agents](./agentic-frameworks/strands-agents/)**: Native integration examples with streaming, file system, and OpenAI identity

## ☁️ AWS Services

* **[SageMaker AI](./amazon-sagemakerai/)**: MLflow integration with AgentCore Runtime
* **[Bedrock Agent](./bedrock-agent/)**: Integration between Bedrock Agents and AgentCore Gateway

## 🔐 Identity Providers

* **[EntraID](./IDP-examples/EntraID/)**: Microsoft Entra ID integration with 3LO outbound authentication
* **[Okta](./IDP-examples/Okta/)**: Step-by-step Okta integration for inbound authentication

## ☁️ Nova

* **[Nova Sonic](./nova/nova-sonic/)**: Amazon Nova model integration examples

## 📊 Observability

* **[Dynatrace](./observability/dynatrace/)**: Application performance monitoring integration with travel agent example

## 🎨 UX Examples

* **[Streamlit Chat](./ux-examples/streamlit-chat/)**: Interactive chat interface with AgentCore backend integration

## 🚀 Integration Patterns

These integrations demonstrate:

- **Framework Adaptation**: Adapting existing agent frameworks to work with AgentCore
- **Authentication Flow**: Implementing various identity provider integrations
- **Monitoring Setup**: Connecting observability tools for agent performance tracking
- **UI Integration**: Building user interfaces that connect to AgentCore services
- **Service Composition**: Combining multiple AWS services with AgentCore

## 🎯 Who These Integrations Are For

These integrations are perfect for:

- Migrating existing agent applications to AgentCore
- Implementing enterprise authentication patterns
- Setting up production monitoring and observability
- Building custom user interfaces for agent interactions
- Connecting AgentCore with existing AWS infrastructure

## 🔗 Related Resources

- [Tutorials](../01-tutorials/) - Learn AgentCore fundamentals
- [Use Cases](../02-use-cases/) - End-to-end application examples
- [AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
