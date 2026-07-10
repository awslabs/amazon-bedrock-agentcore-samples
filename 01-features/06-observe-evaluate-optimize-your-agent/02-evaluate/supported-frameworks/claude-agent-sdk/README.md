# Evaluate a Claude Agent SDK Agent with AgentCore Evaluations

This sample demonstrates how to evaluate an agent built with the
[Claude Agent SDK](https://docs.claude.com/en/api/agent-sdk/overview) using
Amazon Bedrock AgentCore Evaluations.

## What this sample does

1. **Deploys** an HR Assistant agent (Claude Agent SDK) to AgentCore Runtime
2. **Instruments** it automatically via `openinference-instrumentation-claude-agent-sdk`
3. **Invokes** a 3-turn conversation (PTO check → PTO request → policy lookup)
4. **Evaluates** using built-in + custom LLM-as-a-judge evaluators
5. **Sets up online evaluation** for continuous monitoring
6. **Cleans up** all resources when you're done

## Architecture

```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  evaluate.py │────▶│  AgentCore Runtime   │────▶│  CloudWatch Logs │
│  (invoke +   │     │  (Claude Agent SDK)  │     │  (OTel spans)    │
│   evaluate)  │     │  + ADOT auto-instr.  │     └────────┬─────────┘
└──────────────┘     └─────────────────────┘              │
                                                           ▼
                                              ┌──────────────────────┐
                                              │  AgentCore Evaluation │
                                              │  Service              │
                                              │  - On-demand (API)    │
                                              │  - Online (config)    │
                                              └──────────────────────┘
```

## Telemetry details

| Aspect | Value |
|--------|-------|
| Instrumentation library | `openinference-instrumentation-claude-agent-sdk >= 0.1.3` |
| Scope name | `openinference.instrumentation.claude_agent_sdk` |
| Invoke agent span | `openinference.span.kind` = `AGENT` |
| Tool span | `openinference.span.kind` = `TOOL` |
| Inference span | N/A (model metadata on AGENT span) |

## Prerequisites

1. **AWS credentials** configured (`aws configure`)
2. **Bedrock model access** enabled for:
   - `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (agent model)
   - `us.amazon.nova-lite-v1:0` (judge model for evaluation)
3. **AgentCore CLI** installed: `npm install -g @aws/agentcore`
4. **Python 3.12+** with pip

## Quick start (< 15 minutes)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Deploy the agent to AgentCore
python deploy.py --region us-east-1

# 3. Run evaluation (invokes agent + evaluates spans)
python evaluate.py

# 4. Review results
cat results/on_demand_results.json

# 5. Cleanup when done
python cleanup.py
```

## Cost estimate

| Component | Cost per run |
|-----------|-------------|
| Bedrock (agent, 3 turns) | ~$0.10 |
| Bedrock (judge, 4 evaluations) | ~$0.01 |
| CloudWatch Logs | ~$0.01 |
| **Total** | **< $0.15** |

> ⚠️ Run `python cleanup.py` when finished to avoid ongoing charges.

## Files

| File | Purpose |
|------|---------|
| `agent.py` | HR Assistant agent using Claude Agent SDK |
| `deploy.py` | Deploy to AgentCore Runtime |
| `evaluate.py` | On-demand + online evaluation |
| `cleanup.py` | Delete all created resources |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | Container image for AgentCore |

## Related

- [Supported frameworks documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-claude-agent-sdk.html)
- [AgentCore Evaluations overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluation.html)
- [Strands evaluation sample](../../llm-as-a-judge-evaluation/) (same HR Assistant, different framework)
