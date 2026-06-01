# gateway Integration

| Information         | Details                                                        |
|:--------------------|:---------------------------------------------------------------|
| Tutorial type       | Advanced Example                                               |
| Agent type          | Search and retrieval assistant                                 |
| Agentic Framework   | None (direct boto3)                                            |
| LLM model           | Anthropic Claude Haiku 4.5                                     |
| Tutorial components | AgentCore harness + gateway — MCP proxy, tool routing          |
| Example complexity  | Intermediate                                                   |

## Overview

Demonstrates the full AgentCore gateway lifecycle: create a gateway with MCP protocol,
add an MCP target (Exa search), wire it to a harness, and invoke the agent so it
discovers and calls tools via the gateway.

## What is AgentCore gateway?

AgentCore gateway is a managed proxy between your agent and external tool servers (MCP, HTTP).
It provides centralized auth, routing rules, and observability for all tool traffic — without
changing your agent code.

```
[harness] → tools=[{type: "agentcore_gateway", gatewayArn: ...}]
                │
                ▼
            [gateway] ── auth + routing + observability
                │
                ▼
            [MCP Target] ── external MCP server
```

## End-to-End Flow

```
1. Create IAM execution role   (reuses utils/iam.py helper)
2. Create gateway              → IAM auth + MCP protocol
3. Add MCP target              → remote MCP server endpoint (default: Exa)
4. Create routing rule         → directs traffic to the target
5. Create harness              → wired to the gateway's ARN
6. invoke_harness              → agent discovers tools via gateway and calls them
7. Cleanup                     → delete harness, target, gateway, IAM role
```

## Sample Prompts

**Prompt**: "Search the web for the top 5 things to do in Tokyo in spring 2025."
**Expected Behavior**: Agent calls the Exa MCP tool via the gateway, retrieves search results, formats a numbered list.

**Prompt**: "Find recent news about Amazon Bedrock and summarize the top 3 stories."
**Expected Behavior**: Agent uses the search tool, retrieves articles, provides a summary.

**Prompt**: "What are the best hiking trails near Seattle? Include difficulty ratings."
**Expected Behavior**: Agent performs a web search via gateway, returns structured trail information.

**Prompt**: "Search for 'AWS re:Invent 2024 announcements' and list the top 5."
**Expected Behavior**: Agent calls search tool, returns a numbered list of major announcements.

## Key Concepts

**gateway vs direct MCP**: The `agentcore_gateway` tool type routes through gateway for centralized control. Direct `remote_mcp` connects without a gateway proxy.

**Target routing**: Targets can be MCP servers, Lambda functions, or HTTP endpoints. A single gateway can have multiple targets.

**IAM auth (`NONE` type)**: This example uses `authorizerType=NONE` for simplicity. For production, use `CUSTOM_JWT` with a Cognito user pool (see `07-oauth/`).

## Troubleshooting

### Issue: gateway stays in `CREATING` for >2 minutes
**Solution**: gateway provisioning can take up to 2-3 minutes. The polling loop handles this — just wait.

### Issue: Target `FAILED` status
**Solution**: Check the MCP endpoint is reachable. The default Exa endpoint (`https://mcp.exa.ai/mcp`) requires public internet access from the gateway.

### Issue: `HARNESS_POLL_TIMEOUT` exceeded
**Solution**: Increase `HARNESS_POLL_TIMEOUT` constant or retry after a few minutes.

## AgentCore CLI

Create a harness with gateway integration via the CLI (preview channel):

```bash
npm install -g @aws/agentcore@preview
agentcore create --name mygwagent --model-provider bedrock
```

The interactive wizard lets you configure gateway tools under **Advanced Settings → Tools**. After setup:

```bash
agentcore deploy
agentcore invoke --harness mygwagent \
  --session-id "$(uuidgen)" \
  "Search the web for the top 5 things to do in Tokyo in spring."
```

## Clean Up

Gateway targets must be deleted before the gateway:

```python
gw_control.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)
time.sleep(10)
gw_control.delete_gateway(gatewayIdentifier=gateway_id)
harness_control.delete_harness(harnessId=harness_id)
```

The script handles this automatically unless `--skip-cleanup` is passed.

## Running the Python Scripts

```bash
pip install -r ../../requirements.txt
```

```bash
# Default (Exa search, Tokyo travel query)
python gateway_integration.py

# Custom MCP endpoint and prompt
python gateway_integration.py \
    --mcp-endpoint https://your-mcp-server.example.com/mcp \
    --message "Search for recent AI research papers"

# Keep resources for inspection
python gateway_integration.py --skip-cleanup
```
