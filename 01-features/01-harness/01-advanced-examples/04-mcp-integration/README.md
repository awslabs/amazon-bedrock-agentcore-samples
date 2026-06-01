# MCP Integration

| Information         | Details                                                         |
|:--------------------|:----------------------------------------------------------------|
| Tutorial type       | Advanced Example                                                |
| Agent type          | Research and web search assistant                               |
| Agentic Framework   | None (direct boto3)                                             |
| LLM model           | Anthropic Claude Haiku 4.5                                      |
| Tutorial components | AgentCore harness — remote_mcp tools, authentication, error handling |
| Example complexity  | Intermediate                                                    |

## Overview

Connect harness agents to external MCP servers for web search, APIs, and custom tools.
Covers single MCP tool, multiple tools, authenticated servers, error handling, and a
full research assistant use case.

## What is MCP?

The Model Context Protocol (MCP) is an open standard for AI agents to securely connect
to external data sources and tools. With MCP in harness, your agent can:

- Search the web (Exa, Brave)
- Access databases and APIs
- Interact with custom tools via a standardized protocol

```python
tools=[{
    "type": "remote_mcp",
    "name": "exa",                  # tool name the agent sees
    "config": {
        "remoteMcp": {
            "url": "https://mcp.exa.ai/mcp"   # MCP server endpoint
        }
    }
}]
```

The agent automatically discovers available tools from the MCP server and uses them as needed.

## Sample Prompts

**Prompt**: "Search for the latest developments in quantum computing in 2024."
**Expected Behavior**: Agent calls Exa MCP tool, retrieves articles, summarizes key breakthroughs.

**Prompt**: "Research 'Generative AI trends in enterprise 2024' and save a JSON report."
**Expected Behavior**: Agent searches, structures data into JSON, writes `/tmp/ai_trends_report.json`.

**Prompt**: "Compare search results about 'AWS re:Invent 2024' from different sources."
**Expected Behavior**: Agent uses multiple MCP tools (if configured), compares results.

**Prompt (error handling)**: "Search using an invalid MCP URL."
**Expected Behavior**: Agent receives an error event, reports gracefully without crashing.

## Key Concepts

**MCP tool discovery**: When the agent invokes an MCP tool, it first calls `tools/list` on the MCP server to discover available sub-tools. This happens automatically.

**Authentication**: Pass API keys via environment variables, never hardcode. For servers requiring headers, use the `headers` field in `remoteMcp` config (check latest API docs for your server).

**Multiple MCP tools**: Pass multiple tools in the same `invoke_harness` call. The agent decides which to use based on the task.

**timeoutSeconds**: Always set for MCP calls — web searches can take 10-30 seconds. Use `timeoutSeconds=300` for complex research tasks.

## Best Practices

**1. Always set timeouts** — MCP calls can take time, especially for web searches:
```python
timeoutSeconds=300  # 5 minutes for complex research tasks
```

**2. Handle authentication securely** — never hardcode API keys:
```python
# Use environment variables
api_key = os.getenv("MCP_API_KEY")

# Or AWS Secrets Manager
import boto3
secrets = boto3.client('secretsmanager')
api_key = secrets.get_secret_value(SecretId='mcp-api-key')['SecretString']
```

**3. Provide descriptive tool names** — the agent uses the name to reason about which tool to call:
```python
# Descriptive name
"name": "exa_web_search"
```

**4. Monitor and log MCP usage** — track which tools are used and their success rates:
```python
for event in response["stream"]:
    if "contentBlockStart" in event:
        tool_name = event["contentBlockStart"].get("start", {}).get("toolUse", {}).get("name")
        if tool_name:
            print(f"Tool used: {tool_name}")
```

**5. Test MCP servers independently** before integrating with harness:
```bash
curl -X POST https://mcp.exa.ai/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/list"}'
```

**6. Combine MCP with other harness tools** — MCP tools work alongside built-in capabilities:
```python
tools=[
    {"type": "remote_mcp", "name": "exa", "config": {...}},
    {"type": "agentcore_code_interpreter", "name": "code_interpreter"},
    {"type": "agentcore_browser", "name": "browser"},
]
```

## Troubleshooting

### Issue: MCP tool call produces no results
**Solution**: The MCP server may be unavailable or require authentication. Check the server URL and any required API keys. Test with `curl -X POST <url> -H "Content-Type: application/json" -d '{"method": "tools/list"}'`.

### Issue: `internalServerException` in the stream
**Solution**: This usually means the MCP server returned an error. Check the error message and verify the server is accessible from AWS.

### Issue: Research task times out
**Solution**: Increase `timeoutSeconds` to 300-600 for complex research tasks involving multiple searches and file generation.

## AgentCore CLI

Configure MCP tools for a harness via the CLI (preview channel):

```bash
npm install -g @aws/agentcore@preview
agentcore create --name myresearchagent --model-provider bedrock
```

The interactive wizard lets you add remote MCP servers under **Advanced Settings → Tools**. After configuring:

```bash
agentcore deploy
agentcore invoke --harness myresearchagent \
  --session-id "$(uuidgen)" \
  "Search for the latest developments in quantum computing in 2024."
```

## Clean Up

```python
control.delete_harness(harnessId=harness_id)
from utils.iam import delete_harness_role
delete_harness_role()
```

## Running the Python Scripts

```bash
pip install -r ../../requirements.txt
```

```bash
python mcp_integration.py

# Set an API key for authenticated MCP examples
export MCP_API_KEY="your-api-key"
python mcp_integration.py
```
