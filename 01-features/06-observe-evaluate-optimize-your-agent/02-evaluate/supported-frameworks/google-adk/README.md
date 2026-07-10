# Evaluate a Google ADK Agent with AgentCore Evaluations

This sample demonstrates how to evaluate an agent built with the
[Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/) using
Amazon Bedrock AgentCore Evaluations.

## What this sample does

1. **Deploys** an HR Assistant agent (Google ADK) to AgentCore Runtime
2. **Instruments** it automatically via `openinference-instrumentation-google-adk`
3. **Invokes** a 3-turn conversation (PTO check → PTO request → policy lookup)
4. **Evaluates** using built-in + custom LLM-as-a-judge evaluators
5. **Sets up online evaluation** for continuous monitoring
6. **Cleans up** all resources when you're done

## Architecture

```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  evaluate.py │────▶│  AgentCore Runtime   │────▶│  CloudWatch Logs │
│  (invoke +   │     │  (Google ADK)        │     │  (OTel spans)    │
│   evaluate)  │     │  + LiteLLM → Bedrock │     └────────┬─────────┘
└──────────────┘     │  + ADOT auto-instr.  │              │
                     └─────────────────────┘              ▼
                                              ┌──────────────────────┐
                                              │  AgentCore Evaluation │
                                              │  Service              │
                                              │  - On-demand (API)    │
                                              │  - Online (config)    │
                                              └──────────────────────┘
```

## Model routing

By default, this sample uses **LiteLLM** to route model calls to **Claude on
Bedrock** — no external API key needed. To use Gemini natively instead:

```bash
export GOOGLE_API_KEY="your-key"
# Then in agent.py, change model to: "gemini-2.5-flash"
```

## Telemetry details

| Aspect | Value |
|--------|-------|
| Instrumentation library | `openinference-instrumentation-google-adk >= 0.1.13` |
| Scope name | `openinference.instrumentation.google_adk` |
| Invoke agent span | `openinference.span.kind` = `CHAIN` or `AGENT` |
| Tool span | `openinference.span.kind` = `TOOL` |
| Inference span | `openinference.span.kind` = `LLM` |

## Prerequisites

1. **AWS credentials** configured (`aws configure`)
2. **Bedrock model access** enabled for:
   - `us.anthropic.claude-sonnet-4-5-20250929-v1:0` (agent model via LiteLLM)
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
| `agent.py` | HR Assistant agent using Google ADK + LiteLLM |
| `deploy.py` | Deploy to AgentCore Runtime |
| `evaluate.py` | On-demand + online evaluation |
| `cleanup.py` | Delete all created resources |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | Container image for AgentCore |

## Related

- [Supported frameworks documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-google-adk.html)
- [AgentCore Evaluations overview](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluation.html)
- [Claude Agent SDK sample](../claude-agent-sdk/) (same HR Assistant, different framework)
- [Strands evaluation sample](../../llm-as-a-judge-evaluation/) (same HR Assistant, different framework)
