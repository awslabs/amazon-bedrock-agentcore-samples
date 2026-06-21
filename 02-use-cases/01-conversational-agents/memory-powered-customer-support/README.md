# Memory-Powered Customer Support Agent

## Overview

An intelligent customer support agent that uses Amazon Bedrock AgentCore Memory to deliver personalized, context-aware support experiences. The agent remembers customer preferences, past interactions, and issue history across multiple sessions, eliminating the need for customers to repeat themselves.

This use case demonstrates both **short-term memory** (within a single conversation) and **long-term memory** (across sessions) using the AgentCore Memory service with semantic extraction strategies.

### Use case details

| Information         | Details                                                      |
|---------------------|--------------------------------------------------------------|
| Use case type       | Conversational                                               |
| Agent type          | Single agent                                                 |
| Use case components | Memory (short-term + long-term), Tools, Observability        |
| Use case vertical   | Customer Support / E-Commerce                                |
| Example complexity  | Intermediate                                                 |
| SDK used            | Amazon Bedrock AgentCore SDK, boto3, Strands Agents SDK      |

### Use case Architecture

```
                    +------------------+
                    |   Customer UI    |
                    +--------+---------+
                             |
                    +--------v---------+
                    | AgentCore Harness|
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
    +---------v----------+    +-------------v-----------+
    | Short-Term Memory  |    |   Long-Term Memory      |
    | (Session Context)  |    |   (Customer Preferences,|
    | - Current convo    |    |    Issue History, Facts) |
    | - Turn-by-turn     |    |   - Semantic Strategy   |
    +--------------------+    +-------------------------+
              |                             |
              +--------------+--------------+
                             |
                    +--------v---------+
                    |   Agent Logic    |
                    |  (Strands SDK)   |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
    +---------v--+  +--------v---+  +-------v--------+
    | Ticket Tool|  | KB Search  |  | Order Lookup   |
    | (Create,   |  | (Product   |  | (Status, Track)|
    |  Update)   |  |  Info)     |  |                |
    +------------+  +------------+  +----------------+
```

### Use case key Features

- **Cross-session memory**: Agent remembers customer name, preferences, and past issues
- **Semantic fact extraction**: Automatically extracts and stores key facts from conversations
- **Context-aware responses**: Uses past context to provide personalized support
- **Tool integration**: Ticket management, knowledge base search, order lookup
- **Clean architecture**: Separation of memory management from agent reasoning

## Prerequisites

- Python 3.10+
- AWS account with Amazon Bedrock access
- AWS IAM role with permissions for:
  - `bedrock-agentcore:*` (Memory operations)
  - `bedrock:InvokeModel` (LLM access)
- Access to Anthropic Claude models via Amazon Bedrock
- `pip` package manager

## Use case setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
export AWS_REGION="us-east-1"
export MEMORY_EXECUTION_ROLE_ARN="arn:aws:iam::<your-account-id>:role/AgentCoreMemoryExecutionRole"
```

If you do not have the IAM role, the setup script will create it:

```bash
python setup_iam.py
```

### 3. Create the memory store

```bash
python create_memory.py
```

This creates an AgentCore Memory resource with semantic extraction strategies for customer facts and issue history.

## Execution instructions

### Run the agent

```bash
python agent.py
```

### Sample prompts

Try these prompts to see memory in action:

**Session 1 (First contact):**
```
> Hi, my name is Sarah. I'm having trouble with my order #12345.
> The package arrived damaged. I ordered a laptop.
> I prefer email communication for follow-ups.
```

**Session 2 (Return visit - agent remembers Sarah):**
```
> Hi, I'm back. Any update on my issue?
> Also, I'd like to know about your return policy.
```

The agent will remember Sarah's name, order details, communication preference, and past issues without being told again.

## Clean up instructions

```bash
python cleanup.py
```

This deletes the AgentCore Memory resource and any associated data.

## Disclaimer

The examples provided in this repository are for experimental and educational purposes only. They demonstrate concepts and techniques but are not intended for direct use in production environments. Make sure to have Amazon Bedrock Guardrails in place to protect against [prompt injection](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-injection.html).
