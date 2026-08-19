# Claude Agent SDK - Orchestrator-Workers Pattern

| Information         | Details                                                                      |
|---------------------|------------------------------------------------------------------------------|
| Agent type          | Asynchronous with Streaming                                                 |
| Agentic Framework   | Claude Agent SDK                                                           |
| Agentic Pattern     | [Orchestrator-Workers](https://www.anthropic.com/engineering/building-effective-agents) |
| LLM model           | Anthropic Claude (via Bedrock)                                              |
| Components          | AgentCore Runtime                                                           |
| Example complexity  | Medium                                                                      |
| SDK used            | Amazon BedrockAgentCore Python SDK, Claude Agent SDK                        |

This example demonstrates the **Orchestrator-Workers** agentic pattern using Claude Agent SDK's native subagent support (`AgentDefinition` + `Task` tool), deployed on AWS Bedrock AgentCore.

## Pattern Overview

The Orchestrator-Workers pattern uses a central agent that dynamically decomposes tasks, delegates to specialized worker agents, then synthesizes results. This is one of Anthropic's [recommended agentic patterns](https://www.anthropic.com/engineering/building-effective-agents).

### Architecture

```
                     ┌──────────────────────┐
   User Prompt ────> │   Orchestrator Agent  │
                     │                       │
                     │  Decides what to      │
                     │  delegate and to whom │
                     └───────┬──────┬────────┘
                             │      │
                      Task tool    Task tool
                             │      │
                     ┌───────▼──┐ ┌─▼──────────┐
                     │  code-   │ │  reporter   │
                     │  analyzer│ │             │
                     │          │ │  Tools:     │
                     │  Tools:  │ │  Read,Write │
                     │  Read,   │ │             │
                     │  Grep,   │ │  Writes     │
                     │  Glob    │ │  structured │
                     │          │ │  reports    │
                     │  Read-   │ │             │
                     │  only    │ │             │
                     └──────────┘ └─────────────┘
```

### Key concepts

- **Subagents** run with **isolated context** — the orchestrator only sees results, not intermediate steps
- Each subagent has **restricted tools** — `code-analyzer` cannot write files, `reporter` cannot run commands
- Subagents are invoked via the **Task tool** and defined using `AgentDefinition`
- Subagents **cannot spawn their own subagents** (one level deep only)
- Subagents can run **in parallel** when their tasks are independent

For more details on subagents, see the [Claude Agent SDK subagents documentation](https://platform.claude.com/docs/en/agent-sdk/subagents).

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
- AWS account with Bedrock AgentCore access
- Node.js and npm (for Claude Code CLI)

## Setup Instructions

### 1. Create a Python Environment with uv

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Requirements

```bash
uv pip install -r requirements.txt
```

### 3. Configure and Launch with Bedrock AgentCore

```bash
# Configure your agent for deployment
agentcore configure -e agent.py --disable-memory

# Deploy your agent with environment variables
agentcore launch --env CLAUDE_CODE_USE_BEDROCK=1 --env AWS_BEARER_TOKEN_BEDROCK=<your-token>
```

**Note**: The Claude Agent SDK requires either `ANTHROPIC_API_KEY` or AWS Bedrock access. This example uses `CLAUDE_CODE_USE_BEDROCK=1` for Bedrock integration.

### 4. Testing Your Agent

```bash
# Analyze code in the current directory
agentcore invoke '{"prompt": "Analyze the Python files in this project and write a summary report of the code structure"}'

# Find issues in a specific file
agentcore invoke '{"prompt": "Review agent.py for potential issues and write a findings report"}'

# Analyze dependencies
agentcore invoke '{"prompt": "Examine all import statements across the project and report on the dependency structure"}'
```

## How It Works

1. The **orchestrator** receives the user prompt
2. It decides which subagent(s) to invoke based on the task
3. The **code-analyzer** subagent examines code with read-only tools (`Read`, `Grep`, `Glob`)
4. The **reporter** subagent writes structured summaries using findings (`Read`, `Write`)
5. The orchestrator synthesizes results and streams the response back

## Clean Up

```bash
agentcore destroy
```
