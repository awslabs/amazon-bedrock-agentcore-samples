# Step Functions Integration

| Information         | Details                                                                  |
|:--------------------|:-------------------------------------------------------------------------|
| Tutorial type       | Advanced Example                                                         |
| Agent type          | Agent invoked as a workflow step                                         |
| Agentic Framework   | None (direct boto3)                                                      |
| LLM model           | Anthropic Claude Haiku 4.5                                               |
| Tutorial components | AgentCore harness, AWS Step Functions (native `invokeHarness` integration) |
| Example complexity  | Intermediate                                                             |

## Overview

Step Functions has a **native (optimized) service integration** for AgentCore
Harness. A Task state calls `InvokeHarness` directly — **no Lambda, no glue
code**. In Workflow Studio it appears as the **AgentCore InvokeHarness** state.

This sample builds a STANDARD state machine with that one native Task, runs it
against a harness, prints the agent's answer, and tears everything down. Putting
the agent in a Task state lets you wrap the usual Step Functions toolbox around
it — retries, catches, choices, and `Map` fan-out.

## How it's wired

The whole integration is one Task state — this is the heart of the sample:

```json
{
  "Type": "Task",
  "Resource": "arn:aws:states:::bedrockagentcore:invokeHarness",
  "Arguments": {
    "HarnessArn": "arn:aws:bedrock-agentcore:...:harness/my-harness",
    "RuntimeSessionId": "{% $uuid() %}",
    "Messages": [{ "Role": "user", "Content": [{ "Text": "{% $states.input.message %}" }] }],
    "Model": { "BedrockModelConfig": { "ModelId": "global.anthropic.claude-haiku-4-5-20251001-v1:0" } }
  },
  "End": true
}
```

The script:

1. **Harness** — creates one (or reuse yours with `--harness-arn`)
2. **Step Functions role** — grants `bedrock-agentcore:InvokeHarness` on the harness ARN. With the native integration, the *state machine* role calls the harness directly (there is no Lambda role).
3. **State machine** — the single native Task above
4. **Execution** — started with `{"message": "..."}`; the prompt flows in via `$states.input.message`
5. **Cleanup** — deletes the state machine, role, and any harness it created

## Things to know about the native integration

- **PascalCase parameters** (`HarnessArn`, `Messages`, `Model`) — even though the underlying API is camelCase.
- **Request-Response only** — `.sync` and `.waitForToken` patterns are not supported.
- **Converse-shaped output** — read the answer from `Output.Message.Content[].Text`; you also get `StopReason` and `Usage`. Only the final assistant turn is returned (earlier multi-turn turns are dropped).
- **15-minute max** on the Task — keep the harness `TimeoutSeconds` under that.
- The Step Functions resource URI is `bedrockagentcore` (no hyphen); the harness ARN uses `bedrock-agentcore` (with hyphen).

## Sample Prompts

**Prompt** (default): "In two sentences, what is AWS Step Functions and when should I use it?"
**Expected Behavior**: The state machine invokes the harness and the execution output contains the agent's two-sentence answer under `Output.Message.Content`.

**Prompt** (`-m`): "List three serverless patterns for event-driven apps."
**Expected Behavior**: Same flow with the custom prompt.

## Key Concepts

**No Lambda needed**: `arn:aws:states:::bedrockagentcore:invokeHarness` calls the harness natively. The state machine's own role needs `bedrock-agentcore:InvokeHarness`.

**Error handling**: The Task shows a `Retry` on `BedrockAgentCore.ThrottlingException` and a `Catch` to a `Fail` state — the recommended pattern for the integration.

**JSONata input**: `RuntimeSessionId` uses `{% $uuid() %}` and the user message is pulled from execution input with `{% $states.input.message %}`.

> **Note:** This sample puts the *agent* into a workflow step. If you instead want
> the agent to **design or deploy** a Step Functions state machine, enable the
> `aws-serverless` AWS Skill — see [08-aws-skills](../08-aws-skills).

## Clean Up

The script deletes the state machine, the Step Functions role, and any harness it
created on exit. Pass `--skip-cleanup` to keep them for inspection in the console.

## Running the Python Scripts

```bash
pip install -r ../../requirements.txt
```

```bash
# Run the demo end to end (creates a harness, runs the state machine, cleans up)
python stepfunctions_orchestration.py

# Ask the agent something specific
python stepfunctions_orchestration.py \
    -m "List three serverless patterns for event-driven apps."

# Reuse an existing harness
python stepfunctions_orchestration.py --harness-arn arn:aws:bedrock-agentcore:us-west-2:111122223333:harness/my-harness

# Keep the state machine to inspect in the console
python stepfunctions_orchestration.py --skip-cleanup
```
