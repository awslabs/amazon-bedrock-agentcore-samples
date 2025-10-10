# Third-Party Observability Integration

This section demonstrates how to integrate Amazon Bedrock AgentCore Runtime hosted agents with  third-party observability platforms. Learn to leverage specialized monitoring tools while maintaining the benefits of AgentCore Runtime.

## Available Integrations

The publish folder contains:
- A Jupyter notebook demonstrating AgentCore runtime with various observability solutions
- A requirements.txt file listing necessary dependencies

## Getting Started

1. Choose your observability platform
2. Create an account on the respective platform
3. Obtain API keys and configuration details
4. Install requirements: `pip install -r requirements.txt`
5. Configure environment variables in the notebook
6. Deploy your agent to AgentCore Runtime
7. Run the notebook to see integrated observability


## Framework Support

Amazon Bedrock AgentCore supports any agentic framework and model of your choice:
- CrewAI
- LangGraph
- LlamaIndex
- Strands Agents

### Strands Agents
[Strands](https://strandsagents.com/latest/) provides built-in telemetry support, making it ideal for demonstrating third-party integrations.

## Configuration Requirements

Each platform requires specific configuration:

### Braintrust
- API key from Braintrust dashboard
- Project configuration

### Langfuse
- Public and secret keys
- Project configuration

## Cleanup

After completing examples:
1. Delete AgentCore Runtime deployments
2. Remove ECR repositories
3. Clean up platform-specific resources
4. Revoke API keys if no longer needed

## Additional Resources

- [Braintrust Documentation](https://www.braintrust.dev/docs)
- [Langfuse Documentation](https://langfuse.com/docs)
- [AgentCore Runtime Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/userguide/runtime.html)

# Third-Party Observability for Amazon Bedrock AgentCore Agents

This repository contains examples of using agents hosted on Amazon Bedrock AgentCore Runtime with third-party observability tools like Braintrust, Langfuse, and others. These examples demonstrate OpenTelemetry integration for monitoring agent performance, tracing LLM interactions, and debugging workflows.

