# Amazon Bedrock AgentCore Guide

## What is Amazon Bedrock?

Amazon Bedrock is a fully managed service that offers a choice of high-performing foundation models (FMs) from leading AI companies like AI21 Labs, Anthropic, Cohere, Meta, Mistral AI, Stability AI, and Amazon via a single API, along with a broad set of capabilities you need to build generative AI applications with security, privacy, and responsible AI.

## Bedrock AgentCore

Amazon Bedrock AgentCore is the next-generation platform for deploying production-ready AI agents. It provides:

- **Containerized Runtime**: Deploy agents as containers with automatic scaling
- **Framework Agnostic**: Use any agent framework (Strands, LangChain, etc.)
- **Built-in Memory**: Short-term and long-term memory with extraction strategies
- **Session Isolation**: Each user gets isolated agent sessions
- **Native Authentication**: Integrates directly with Amazon Cognito

### AgentCore vs Classic Bedrock Agents

| Feature | AgentCore | Classic Bedrock Agents |
|---------|-----------|----------------------|
| Deployment | Containerized | Managed service |
| Framework | Any (Strands, LangChain, etc.) | Bedrock-specific |
| Memory | Built-in STM + LTM | Session attributes only |
| Scaling | Automatic | Managed |
| Customization | Full control | Limited |

## AgentCore Components

### AgentCore Runtime
The Runtime hosts your containerized AI agent:
- Auto-scales based on demand
- Provides session isolation per user
- Supports any Python agent framework
- Integrates with Cognito for authentication

### AgentCore Memory
Persistent memory with extraction strategies:
- **Short-term Memory (STM)**: Conversation context within sessions
- **Long-term Memory (LTM)**: Facts, preferences, and summaries
- **Extraction Strategies**: Semantic, user preference, summarization, episodic

## Knowledge Bases

Knowledge bases in Amazon Bedrock allow agents to access and retrieve information from your documents using RAG (Retrieval Augmented Generation). Key features include:

- **Vector Storage**: Documents are converted to embeddings for semantic search
- **OpenSearch Serverless**: Managed vector database with automatic scaling
- **Embedding Models**: Amazon Titan Embed Text v2 (1024 dimensions, 100+ languages)
- **Multiple Formats**: Support for PDF, TXT, MD, HTML, DOC, and DOCX files
- **Real-time Updates**: Sync new documents automatically
- **Secure Access**: Integration with AWS IAM for access control

## Best Practices

### Agent Configuration
- Write clear, specific instructions in your system prompt
- Define the agent's role and capabilities explicitly
- Configure memory strategies based on your use case
- Set appropriate session timeouts and lifecycle policies

### Knowledge Base Optimization
- Use descriptive filenames for your documents
- Organize content with clear headings and structure
- Keep documents focused on specific topics
- Update content regularly to maintain accuracy
- Use chunking strategies appropriate for your content

### Security Considerations
- Use IAM roles with least privilege access
- Enable encryption for data at rest and in transit (KMS)
- Configure Cognito authentication for user access
- Monitor agent usage through CloudWatch
- Implement proper error handling in your applications

## Common Use Cases

1. **Enterprise Knowledge Management**: Internal chatbot with long-term memory
2. **Customer Support**: AI-powered service with conversation history
3. **Documentation Assistant**: Interactive search for technical docs
4. **Compliance and Policy**: Q&A system with audit trails
5. **Personal Assistant**: Context-aware assistant that learns preferences

## Getting Started with AgentCore

1. Create an AgentCore Runtime with your containerized agent
2. Configure AgentCore Memory with extraction strategies
3. Set up a Knowledge Base with OpenSearch Serverless
4. Upload your documents to the S3 data source
5. Deploy API Gateway with Cognito authentication
6. Test the agent through the web interface or API

## Foundation Models

AgentCore supports all Bedrock foundation models:

- **Claude Sonnet 4** (Anthropic) - Best balance of capability and speed
- **Claude 3.5 Sonnet** (Anthropic) - Previous generation
- **Claude 3 Haiku** (Anthropic) - Fast and cost-effective
- **Titan Text** (Amazon) - Enterprise text generation
- **Llama 3** (Meta) - Open-source alternative

For more detailed information, refer to the [AWS Bedrock AgentCore documentation](https://docs.aws.amazon.com/bedrock-agentcore/).
