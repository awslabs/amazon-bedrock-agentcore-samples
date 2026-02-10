# Getting Started with Your AI Assistant

Welcome to your new AI assistant powered by Amazon Bedrock AgentCore! This document will help you understand how to interact with your assistant effectively.

## What is this AI Assistant?

Your AI assistant is built using Amazon Bedrock AgentCore with Claude Sonnet 4 and has access to a knowledge base that contains relevant information to help answer your questions. The assistant uses:

- **Claude Sonnet 4**: Anthropic's latest foundation model for natural language understanding
- **OpenSearch Serverless**: Vector database for semantic search
- **Titan Embed Text v2**: Amazon's embedding model (1024 dimensions, 100+ languages)
- **AgentCore Memory**: Persistent memory for conversation context

## How to Use the Assistant

### Basic Interaction
- Type your questions in natural language
- The assistant automatically searches its knowledge base for relevant information
- Responses are generated based on the most relevant content found
- The assistant maintains context across your conversation

### Best Practices
1. **Be specific**: Ask clear, specific questions for better results
2. **Provide context**: Give background information when needed
3. **Ask follow-up questions**: Build on previous responses for deeper understanding
4. **Trust the search**: The assistant proactively searches the knowledge base for factual questions

### Example Questions
- "What is Amazon Bedrock?"
- "Tell me about the Phoenix Rising project"
- "What embedding model does this system use?"
- "What are the best practices for using knowledge bases?"

## Features

### Knowledge Base Integration
Your assistant has access to a comprehensive knowledge base that includes:
- Technical documentation
- Best practices guides
- Troubleshooting information
- Configuration examples

The knowledge base uses semantic search powered by OpenSearch Serverless, meaning it understands the meaning of your questions rather than just matching keywords.

### Conversation Memory
The assistant maintains context within a conversation session through AgentCore Memory:
- **Short-term Memory (STM)**: Remembers your current conversation
- **Long-term Memory (LTM)**: Extracts and stores important facts and preferences
- Follow-up questions work naturally
- Clarifications build on previous responses

## Customization

You can customize your assistant by:
1. Adding new documents to the knowledge base S3 bucket
2. Modifying the agent's instructions in `infrastructure/agent/src/agent.py`
3. Adding new tools in `infrastructure/agent/src/tools/`
4. Updating the web interface in `web-console/`
5. Configuring memory strategies in the AgentCore Memory stack

## Support

If you need help:
1. Check the documentation in the `docs/` directory
2. Review the troubleshooting guide at `docs/TROUBLESHOOTING.md`
3. Check CloudWatch logs for detailed error information
4. Contact your system administrator

## Next Steps

1. Try asking some questions to test the assistant
2. Upload your own documents to the knowledge base
3. Customize the assistant for your specific use case
4. Explore advanced features like custom tools and memory strategies

Remember: The assistant's knowledge is based on the documents in its knowledge base. For the most accurate and up-to-date information, ensure your knowledge base contains current and relevant content.
