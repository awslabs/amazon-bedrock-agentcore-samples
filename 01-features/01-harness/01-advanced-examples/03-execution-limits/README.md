# Execution Limits

| Information         | Details                                                         |
|:--------------------|:----------------------------------------------------------------|
| Tutorial type       | Advanced Example                                                |
| Agent type          | General-purpose task agent                                      |
| Agentic Framework   | None (direct boto3)                                             |
| LLM model           | Anthropic Claude Haiku 4.5                                      |
| Tutorial components | AgentCore harness — maxIterations, timeoutSeconds, maxTokens    |
| Example complexity  | Beginner                                                        |

## Overview

Control how much work a harness agent can do per invocation using three limit parameters.
Each limit is demonstrated with before/after comparisons showing the difference.

## What are Execution Limits?

| Parameter | What it controls |
|:----------|:-----------------|
| `maxIterations` | Maximum think → act → observe loop cycles |
| `timeoutSeconds` | Wall-clock deadline for the entire invocation |
| `maxTokens` | Maximum tokens the model can generate |

Pass any combination to `invoke_harness`. The agent stops as soon as any limit is hit.
Useful for keeping latency predictable, controlling cost, or preventing runaway tasks.

## Sample Prompts

**Prompt with maxIterations=1**: "Create 3 files: hello.txt, world.txt, readme.md"
**Expected Behavior**: Agent creates at most 1 file (one tool call per iteration), then stops.

**Prompt with timeoutSeconds=5**: "Write a Python prime number script, run it, show output."
**Expected Behavior**: Complex task cut short by the deadline — agent may not finish.

**Prompt with maxTokens=10**: "Explain the history of Python in detail."
**Expected Behavior**: Response is truncated to ~10 tokens — just a few words.

**Prompt with all limits**: "List files, create summary.txt"
**Expected Behavior**: Agent completes within whichever limit is hit first.

## Key Concepts

**stopReason**: The stream includes a `messageStop` event with a `stopReason` field indicating why the agent stopped: `end_turn` (finished naturally), `max_tokens`, `stop_sequence`, or a limit-based stop.

**Usage metadata**: The stream includes a `metadata` event with token counts: `inputTokens` and `outputTokens`.

**No default limits**: If you omit all limit parameters, the agent runs until it naturally completes or hits a server-side maximum.

## Troubleshooting

### Issue: Agent completes even with maxIterations=1
**Solution**: Simple prompts may require 0 tool calls (pure text response), so `maxIterations=1` still allows a full response. Try a multi-step task like creating multiple files.

### Issue: timeoutSeconds=5 doesn't produce a truncated response
**Solution**: The agent may respond quickly for simple tasks. Use a complex multi-step task (write + build + run + verify) to reliably trigger the timeout.

### Issue: maxTokens very low causes a validation error
**Solution**: Some models have a minimum maxTokens value. Try at least 10 tokens.

## AgentCore CLI

Invoke a deployed harness with execution limits via the CLI (preview channel):

```bash
npm install -g @aws/agentcore@preview
agentcore create --name mylimitedagent --model-provider bedrock
agentcore deploy
```

The CLI does not expose per-invocation `maxIterations`/`timeoutSeconds`/`maxTokens` flags directly — use the boto3 SDK (this tutorial) to experiment with those limits. The CLI is best for create/deploy/invoke workflows.

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
python execution_limits.py
```
