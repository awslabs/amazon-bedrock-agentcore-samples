# Agent Deployment - Strands Agent Infrastructure Deployment with AgentCore

Deploy the Strands Agent Data Analyst Assistant for Video Game Sales using **[AWS Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)**'s fully managed service for scalable agent applications with **Runtime** and **Memory** capabilities.

## Overview

This tutorial guides you through deploying a video game sales data analyst agent using Amazon Bedrock AgentCore's managed infrastructure, includes the following modular services:

- **[Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)**: Provides the managed execution environment with invocation endpoints (`/invocations`) and health monitoring (`/ping`) for your agent instances
- **[Amazon Bedrock AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html)**: A fully managed service that gives AI agents the ability to remember, learn, and evolve through interactions by capturing events, transforming them into memories, and retrieving relevant context when needed

Don't forget to review the **[Amazon Bedrock AgentCore documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)**.

> [!IMPORTANT]
> This sample application is meant for demo purposes and is not production ready. Please make sure to validate the code with your organizations security best practices.
>
> Remember to clean up resources after testing to avoid unnecessary costs by following the clean-up steps provided.

## Environment Setup and Requirements

Before you begin, ensure you have:

* **[Back-End Deployment - Data Source and Configuration Management Deployment with CDK](../cdk-agentcore-strands-data-analyst-assistant)**
* **[Docker](https://www.docker.com)**
* **Required Packages**:
  * Install the Amazon Bedrock AgentCore CLI:
    ```bash
    pip install bedrock-agentcore
    ```
  * Install all project dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Create Short-Term AgentCore Memory

Before deploying your agent, you need to create a **[short-term memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/short-term-memory.html)** store that will help your agent maintain conversation context:

1. Create a memory store with a 7-day default expiry period:

```bash
python3 resources/memory_manager.py create DataAnalystAssistantMemory ${MEMORY_ID_SSM_PARAMETER}
```

2. List all available memory stores to validate that your memory store was created successfully:

```bash
python3 resources/memory_manager.py list
```

This memory store enables your agent to remember previous interactions within the same session, providing a more coherent and contextual conversation experience.


## Local Testing

Before deploying to AWS, you can test the Data Analyst Agent locally to verify functionality:

1. Start the local agent server:

```bash
python3 app.py
```

This launches a local server on port 8080 that simulates the AgentCore runtime environment:
- Processes natural language queries about video game sales data
- Uses AgentCore Memory (Short-Term Memory) to maintain conversation context
- Maintains conversation history through the `last_k_turns` parameter

2. Test the agent with example queries using curl:

```bash
curl -X POST http://localhost:8080/invocations \
 -H "Content-Type: application/json" \
 -d '{"prompt": "Hello world!", "session_id": "b2e9c4f7-3a1d-8e5b-6c2f-9d4e7a8b5c3f", "last_k_turns": 20}'
 ```

```bash
curl -X POST http://localhost:8080/invocations \
 -H "Content-Type: application/json" \
 -d '{"prompt": "what is the structure of your data available?!", "session_id": "b2e9c4f7-3a1d-8e5b-6c2f-9d4e7a8b5c3f", "last_k_turns": 20}'
```

```bash
curl -X POST http://localhost:8080/invocations \
 -H "Content-Type: application/json" \
 -d '{"prompt": "Which developers tend to get the best reviews?", "session_id": "b2e9c4f7-3a1d-8e5b-6c2f-9d4e7a8b5c3f", "last_k_turns": 20}'
```

```bash
curl -X POST http://localhost:8080/invocations \
 -H "Content-Type: application/json" \
 -d '{"prompt": "Give me a summary of our conversation", "session_id": "b2e9c4f7-3a1d-8e5b-6c2f-9d4e7a8b5c3f", "last_k_turns": 20}'
```


## Deploy the Strands Agent with Amazon Bedrock AgentCore

Deploy your agent to AWS with these simple steps:

1. Configure the agent deployment accepting default values when prompted:

```bash
agentcore configure --entrypoint app.py --name agentcoredataanalystassistant -er $AGENT_CORE_ROLE_EXECUTION
```

2. Launch the agent infrastructure:

```bash
agentcore launch
```

## Testing the Deployed Agent

Test your deployed agent with these example queries:

```bash
agentcore invoke '{"prompt": "Hello world!", "session_id": "c5b8f1e4-9a2d-4c7f-8e1b-5a9c3f6d2e8a", "last_k_turns": 20}'
```

```bash
agentcore invoke '{"prompt": "what is the structure of your data available?!", "session_id": "c5b8f1e4-9a2d-4c7f-8e1b-5a9c3f6d2e8a", "last_k_turns": 20}'
```

```bash
agentcore invoke '{"prompt": "Which developers tend to get the best reviews?", "session_id": "c5b8f1e4-9a2d-4c7f-8e1b-5a9c3f6d2e8a", "last_k_turns": 20}'
```

```bash
agentcore invoke '{"prompt": "Give me a summary of our conversation", "session_id": "c5b8f1e4-9a2d-4c7f-8e1b-5a9c3f6d2e8a", "last_k_turns": 20}'
```

**Expected Behavior**: The agent responds as "Gus," a video game sales data analyst assistant who provides information about the video_games_sales_units database (64,016 game titles from 1971-2024), analyzes developer review scores, and maintains conversation context across interactions.

## Next Step

You can now proceed to the **[Front-End Implementation - Integrating AgentCore with a Ready-to-Use Data Analyst Assistant Application](../amplify-video-games-sales-assistant-agentcore-strands/))**.

## Cleaning-up Resources (Optional)

To avoid unnecessary charges, delete the AgentCore run environment from the AWS Console.

## Thank You

## License

This project is licensed under the Apache-2.0 License.