# Step Functions Orchestration

| Information         | Details                                                                  |
|:--------------------|:-------------------------------------------------------------------------|
| Tutorial type       | Advanced Example                                                         |
| Agent type          | Orchestrated harness lifecycle                                           |
| Agentic Framework   | None (direct boto3)                                                      |
| LLM model           | Anthropic Claude Haiku 4.5                                               |
| Tutorial components | AgentCore harness, AWS Step Functions (STANDARD), AWS Lambda             |
| Example complexity  | Advanced                                                                 |

## Overview

A harness has a lifecycle — **create → wait for READY → invoke → delete** — that
maps cleanly onto a state machine. This sample builds an AWS Step Functions
**STANDARD** workflow that drives that lifecycle end to end, runs it once, prints
the agent's answer, and tears everything down.

```
CreateHarness ─▶ WaitForReady ─▶ GetStatus ─▶ CheckStatus ─▶ InvokeHarness ─▶ DeleteHarness ─▶ Done
                      ▲                            │
                      └──────── not READY ─────────┘
```

## How it's wired

One small Lambda dispatches on an `action` field, so the whole lifecycle is a
single deployable unit:

| `action` | Calls |
|---|---|
| `create` | `create_harness` |
| `status` | `get_harness` (polled by the `Wait → Choice` loop) |
| `invoke` | `invoke_harness`, drains the response stream, returns the text |
| `delete` | `delete_harness` |

The script provisions everything it needs and cleans it all up:

1. **IAM** — harness execution role (shared `utils` helper), Lambda role, Step Functions role
2. **Lambda** — the action-dispatched worker (zipped and deployed inline)
3. **State machine** — the ASL definition above
4. **Execution** — started with the prompt; polled until it finishes
5. **Cleanup** — deletes the state machine, Lambda, and roles (the workflow deletes the harness itself)

## Sample Prompts

**Prompt** (default): "In two sentences, what is AWS Step Functions and when should I use it?"
**Expected Behavior**: The state machine creates a harness, waits for READY, invokes it with this prompt, returns the agent's two-sentence answer, then deletes the harness.

**Prompt** (`-m`): "List three serverless patterns for event-driven apps."
**Expected Behavior**: Same lifecycle, with the orchestrated agent answering the custom prompt.

## Key Concepts

**Why a Lambda task worker**: `InvokeHarness` returns a streaming response, which a native Step Functions SDK integration can't consume. The Lambda drains the stream and returns the final text.

**Polling loop**: `Wait → GetStatus → Choice` handles the asynchronous `CREATING → READY` transition; on `FAILED` it deletes the harness before failing the execution.

**State I/O**: Each task receives only the fields it needs, threaded forward with `ResultPath`.

> **Note:** This sample treats the harness lifecycle as a workflow *step*. If you
> instead want the **agent** to design or deploy a Step Functions state machine,
> enable the `aws-serverless` AWS Skill — see [08-aws-skills](../08-aws-skills).

## Clean Up

The script deletes the state machine, Lambda, and IAM roles on exit, and the
workflow deletes the harness itself. Pass `--skip-cleanup` to keep the state
machine and Lambda for inspection in the console.

## Running the Python Scripts

```bash
pip install -r ../../requirements.txt
```

```bash
# Run the full orchestration demo
python stepfunctions_orchestration.py

# Ask the orchestrated agent something specific
python stepfunctions_orchestration.py \
    -m "List three serverless patterns for event-driven apps."

# Keep the state machine + Lambda to inspect in the console
python stepfunctions_orchestration.py --skip-cleanup
```
