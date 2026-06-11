# Strands Insurance Agent

An interactive agent built with Strands that connects to a local MCP server to provide insurance information and quotes.

![Strands Insurance Agent Demo](images/strands_local_agent_conversation.gif)

## Overview

This project demonstrates how to use Strands Agents with an MCP (Model Context Protocol) server to create an interactive insurance assistant. The agent leverages Claude 3.7 Sonnet via AWS Bedrock and connects to local insurance API tools exposed through an MCP server.

## Prerequisites

- Python 3.10 or higher
- AWS account with Bedrock access to Claude 3.7 Sonnet
- Local MCP server running at http://localhost:8000/mcp
- Insurance API running at http://localhost:8001

## Project Structure

```
strands-insurance-agent/
├── interactive_insurance_agent.py  # Main interactive agent
├── strands_insurance_agent.py      # Non-interactive agent
├── requirements.txt                # Project dependencies
├── strands_local_agent.png         # Screenshot of the agent in action
└── README.md                       # This file
```

## Setup Instructions

### 1. Clone the Repository (if you haven't already)

```bash
git clone <repository-url>
cd local_prototype/strands-insurance-agent
```

### 2. Set Up a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. AWS Credentials Setup

This agent uses AWS Bedrock to access Claude 3.7 Sonnet. Make sure your AWS credentials are properly configured:

1. Install the AWS CLI if you haven't already:
   ```bash
   pip install awscli
   ```

2. Configure credentials using [link](https://strandsagents.com/latest/documentation/docs/user-guide/quickstart/#configuring-credentials)


### 5. Start the Required Services

Before running the agent, make sure these services are running:

1. **Insurance API**:
   ```bash
   cd ../insurance_api
   python -m uvicorn server:app --port 8001
   ```

2. **MCP Server**:
   ```bash
   cd ../native_mcp_server
   python server.py
   ```

## Running the Interactive Agent

Once everything is set up, run the interactive agent:

```bash
python interactive_insurance_agent.py
```

This will start an interactive chat session where you can ask questions about insurance products and get personalized quotes. The agent maintains a local chat history throughout your session, allowing for natural conversation flow and follow-up questions.

### Chat History

The local chat history feature:
- Stores all conversation turns in memory during your session
- Provides context to the model about previous interactions
- Enables the agent to give more relevant and personalized responses
- Helps maintain continuity when discussing specific customers or vehicles
- Is cleared when you exit the program (no persistent storage between sessions)

## Features

The interactive insurance agent includes the following functionality:

1. **Interactive Chat Interface**: 
   - Emoji-enhanced console interface
   - Natural conversation flow
   - Command history with context preservation

2. **Insurance API Integration**:
   - Customer information lookup
   - Vehicle information retrieval
   - Insurance quote generation
   - Vehicle safety ratings

3. **Advanced Features**:
   - Comprehensive logging (console and file-based)
   - Error handling and recovery
   - Response formatting for better readability
   - Tool usage tracking

4. **Local Chat History and Conversation Context**:
   - Maintains an in-memory history of all conversation turns
   - Persists throughout the session for seamless follow-ups
   - Allows the agent to reference previous questions and answers
   - Remembers customer and vehicle details across queries
   - Provides contextual responses based on conversation flow

## Example Queries

Here are some example queries you can try:

- "What information do you have about customer cust-001?"
- "Can you tell me about a 2020 Toyota Camry?"
- "What insurance options are available for a 2020 Toyota Camry for customer ID cust-001?"
- "What are the safety ratings for a Honda Civic?"
- "Get me a quote for a 2022 Ford F-150 for customer cust-002."

### Conversation Examples Using Chat History

The agent remembers previous context, so you can have natural conversations like:

```
You: What information do you have about customer cust-001?
Agent: [Returns information about John Smith]

You: What kind of car does he have?
Agent: [Uses previous context to know you're asking about John Smith]

You: Can you give me a quote for him for a 2023 Toyota RAV4?
Agent: [Combines the customer information with the new vehicle request]
```

This contextual awareness makes interactions more natural and efficient.

## Architecture

The Strands Insurance Agent acts as a bridge between:

1. **User** (via console interface)
2. **Strands Agent** (using Claude 3.7 Sonnet)
3. **MCP Server** (providing insurance tools)
4. **Insurance API** (providing the actual data)

When you ask a question:
1. The agent formats and sends it to Claude 3.7 via Strands
2. Claude decides which tools to use based on your question
3. The agent executes the necessary API calls through the MCP server
4. Results are gathered, formatted, and presented to you

## Logging

The agent logs all interactions to:
- Console (DEBUG level by default)
- File (`insurance_agent.log` - if file logging is enabled)

Logs include:
- User inputs and agent responses
- Tool calls and their arguments
- Response processing details
- Error information

## Troubleshooting

### Common Issues

1. **AWS Credentials Missing or Invalid**
   - Error: "Could not connect to the endpoint URL"
   - Solution: Check your AWS credentials and region

2. **MCP Server Not Running**
   - Error: "Connection refused" when connecting to the MCP server
   - Solution: Start the MCP server at http://localhost:8000/mcp

3. **Insurance API Not Running**
   - Error: "Error connecting to auto insurance API"
   - Solution: Make sure the insurance API is running at http://localhost:8001

4. **Response Format Issues**
   - Error: Agent displays raw JSON or list format instead of clean text
   - Solution: The response parser may need updates for new Strands versions

## 📝 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](../../../../LICENSE) file for details.


## Note

- MCP Server: Based on the LocalMCP FastMCP server
- Insurance API: Built with FastAPI
- Agent Framework: Strands Agents by Anthropic
- LLM: Claude 3.7 Sonnet via AWS Bedrock