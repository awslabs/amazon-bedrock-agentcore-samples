# Programmatic (Code-Based) Evaluators

## Introduction

This tutorial shows how to build and run **custom code-based evaluators** with Amazon Bedrock AgentCore Evaluations. Instead of relying on an LLM as the judge, code-based evaluators delegate scoring to an AWS Lambda function you write. This gives you deterministic, low-cost, fully customizable evaluation logic that can encode exact business rules, format constraints, or data validation requirements that an LLM might interpret loosely.

The tutorial pairs code-based evaluators with the built-in LLM evaluators from the [groundtruth tutorial](../05-groundtruth-based-evalautions/) to show how both types work side-by-side in a mixed evaluation run.

---

## Key Concepts

### Code-Based vs Built-in Evaluators

| | Built-in (LLM-as-judge) | Code-based (Lambda) |
|---|---|---|
| **Judge** | LLM with a fixed evaluation prompt | Your custom Lambda function |
| **Output** | Probabilistic score with explanation | Deterministic score |
| **Cost** | LLM inference per evaluation | Lambda invocation  |
| **Best for** | Nuanced qualitative assessment | Exact data validation, business rules |
| **Customizable** | Limited (fixed prompt templates) | Fully customizable |

### Evaluator Levels

| Level | Invoked | Use when |
|---|---|---|
| **TRACE** | Once per agent response (turn) | Per-response checks, e.g. length, format |
| **SESSION** | Once per conversation session | End-to-end fact accuracy across all turns |

### SDK v1.6 Lambda Contract

The `@custom_code_based_evaluator()` decorator (new in SDK v1.6) converts raw Lambda events into typed `EvaluatorInput` and `EvaluatorOutput` objects, replacing the raw dict-based pattern from earlier versions.

```python
from bedrock_agentcore.evaluation import (
    EvaluatorInput, EvaluatorOutput, custom_code_based_evaluator,
)

@custom_code_based_evaluator()
def lambda_handler(input: EvaluatorInput, context) -> EvaluatorOutput:
    # input.session_spans      — list of OTel spans for the session
    # input.evaluation_level   — "TRACE" or "SESSION"
    # input.target_trace_id    — set by service for TRACE level
    return EvaluatorOutput(value=1.0, label="PASS", explanation="...")
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Notebook                                                                    │
│                                                                              │
│  1. Deploy Lambda functions (hr-response-length, hr-fact-checker)            │
│  2. Register evaluators via bedrock-agentcore-control                        │
│  3a. On-demand: EvaluationClient.run(session_id, evaluator_ids)             │
│  3b. Dataset: OnDemandEvaluationDatasetRunner.run(dataset, agent_invoker)   │
└────────────────┬────────────────────────────────────────────────────────────┘
                 │
     ┌───────────▼────────────┐        ┌──────────────────────────────┐
     │  AgentCore Runtime      │        │  AgentCore Evaluations DP   │
     │  HR Assistant agent     │──OTel─▶│  bedrock-agentcore          │
     │  (Strands Agents)       │        │                             │
     └─────────────────────────┘        │   ┌──────────────────────┐  │
                                        │   │  Builtin LLM evals   │  │
     ┌─────────────────────────┐        │   │  Correctness         │  │
     │  CloudWatch Logs        │        │   │  Helpfulness         │  │
     │  /aws/bedrock-agentcore/│        │   │  ResponseRelevance   │  │
     │  runtimes/<agent-id>    │        │   └──────────────────────┘  │
     └─────────────────────────┘        │   ┌──────────────────────┐  │
                                        │   │  Code-based Lambda   │  │
     ┌─────────────────────────┐        │   │  HRResponseLength    │  │
     │  AWS Lambda             │◀───────│   │  HRFactChecker       │  │
     │  hr-response-length     │        │   └──────────────────────┘  │
     │  hr-fact-checker        │        └─────────────────────────────┘
     └─────────────────────────┘
```

**Evaluation flow:**
1. Agent is invoked; OTel spans are written to CloudWatch
2. `EvaluationClient` or `OnDemandEvaluationDatasetRunner` collects spans from CloudWatch
3. The service calls each evaluator — builtin evaluators run LLM inference; code-based evaluators invoke your Lambda with the span payload
4. All results are aggregated and returned

---

## Prerequisites

- **Python 3.10+** with the `agentcore-evals` Jupyter kernel (see parent README)
- **Docker** running locally (for agent container image build)
- **AWS credentials** with permissions for:
  - `bedrock-agentcore:*` — runtime and evaluations
  - `bedrock-agentcore-control:*` — evaluator registration
  - `lambda:CreateFunction`, `lambda:UpdateFunctionCode`, `lambda:AddPermission`, `lambda:GetFunction`
  - `logs:FilterLogEvents`, `logs:DescribeLogGroups` — CloudWatch span collection
  - `ecr:*` — container image for the agent
  - `iam:*` — auto-creating the agent execution role
- **IAM role** named `AgentCoreLambdaExecutionRole` with `AWSLambdaBasicExecutionRole` attached
- **bedrock-agentcore >= 1.6.0** installed in the notebook kernel

> **Tip:** If you already ran `groundtruth_evaluations.ipynb`, the agent is already deployed and its info is stored via `%store`. This notebook reloads it automatically and skips re-deployment.

---

## Files

| File | Description |
|---|---|
| `programmatic_evaluators.ipynb` | Main tutorial notebook (standalone, end-to-end) |
| `hr_assistant_agent.py` | HR Assistant Strands agent (same as groundtruth tutorial) |
| `requirements.txt` | Python dependencies (`bedrock-agentcore>=1.6.0`) |
| `lambdas/hr_response_length/lambda_function.py` | Response length evaluator Lambda |
| `lambdas/hr_fact_checker/lambda_function.py` | HR fact-checking evaluator Lambda |

---

## Evaluators Built in This Tutorial

### HRResponseLength (TRACE level)

Checks that each agent response is between 50 and 600 characters. Responses shorter than 50 chars are likely incomplete; longer than 600 suggests over-explanation. Thinking blocks (`<thinking>...</thinking>`) are stripped before measurement.

- **Level:** TRACE — evaluated once per agent response
- **Lambda:** `hr-response-length`
- **Returns:** `1.0` (PASS) if within range, `0.0` (FAIL) otherwise

### HRFactChecker (SESSION level)

Deterministically validates that the HR assistant's responses contain accurate facts drawn from the mock data store. Uses exact pattern matching with no LLM inference.

- **Level:** SESSION — evaluated once per conversation
- **Lambda:** `hr-fact-checker`
- **Facts checked:**
  - PTO balances: EMP-001 (10 remaining), EMP-002 (3 remaining), EMP-042 (13 remaining)
  - Pay stubs: gross/net pay figures for each employee/period
  - PTO request ID format `PTO-2026-NNN`
  - Policy facts: 15-day PTO accrual, 2-day advance notice, 401k 4% match, 90% health coverage
- **Returns:** fraction of applicable checks passed (0.0–1.0), labeled `PASS`, `PARTIAL`, `FAIL`, or `SKIP`

---

## Mixed Evaluator Set

The notebook runs `OnDemandEvaluationDatasetRunner` with five evaluators simultaneously:

| Evaluator | Type | Level |
|---|---|---|
| `Builtin.Correctness` | Built-in LLM | TRACE |
| `Builtin.Helpfulness` | Built-in LLM | TRACE |
| `Builtin.ResponseRelevance` | Built-in LLM | TRACE |
| `HRResponseLength` | Code-based Lambda | TRACE |
| `HRFactChecker` | Code-based Lambda | SESSION |

Results from all five evaluators are collected per scenario, letting you compare qualitative LLM scores with deterministic code scores side-by-side.

---

## Sample Prompts

The dataset includes five scenarios that exercise facts the `HRFactChecker` validates:

| Scenario | Prompt | Expected behavior |
|---|---|---|
| `pto-balance-check` | "What is the current PTO balance for employee EMP-001?" | Agent calls `get_pto_balance`, reports 10 remaining days |
| `submit-pto-request` | "Please submit a PTO request for EMP-001 from 2026-04-14 to 2026-04-16 for a family vacation." | Agent calls `submit_pto_request`, returns a `PTO-2026-NNN` ID |
| `pay-stub-lookup` | "Can you pull up the January 2026 pay stub for employee EMP-001?" | Agent calls `get_pay_stub`, reports gross $8,333.33 / net $5,362.50 |
| `pto-policy-lookup` | "What is the company PTO policy?" | Agent calls `lookup_hr_policy`, mentions 15-day accrual and 2-day advance notice |
| `health-benefits` | "Can you tell me about the company health insurance options?" | Agent calls `get_benefits_summary`, mentions 90% premium coverage |

You can extend the dataset with additional scenarios to test more HR topics (remote work policy, parental leave, 401k, etc.).

---

## Notebook Walkthrough

| Step | Description |
|---|---|
| 1 | Install dependencies (`bedrock-agentcore>=1.6.0`) |
| 2 | Configure AWS session, region, and Lambda role ARN |
| 3 | Agent setup — reload from `%store` (groundtruth notebook) or deploy fresh |
| 4 | Define Lambda evaluator functions using the `@custom_code_based_evaluator()` decorator |
| 5 | Deploy Lambda functions (bundled with bedrock-agentcore SDK + pydantic) |
| 6 | Register evaluators via `bedrock-agentcore-control` boto3 service |
| 7 | On-demand evaluation with `EvaluationClient` (code-based + builtin evaluators) |
| 8 | Dataset evaluation with `OnDemandEvaluationDatasetRunner` (mixed evaluator set) |
| 9 | Inspect and compare results (per-scenario tables + aggregate score comparison) |
| 10 | Cleanup — delete Lambda functions, evaluator records, and agent runtime |

---

## Span Structure (Strands / AgentCore OTel)

Lambda functions receive OTel spans from the evaluation service. Key fields:

```
span.name                                  e.g. "invoke_agent", "llm_call"
span.attributes.gen_ai.operation.name      "execute_tool" for tool-call spans
span.attributes.gen_ai.tool.name           tool name (e.g. "get_pto_balance")
span.span_events[*]
  .body.output.messages[*]
  .content.message                         final agent response text
```

`EvaluatorInput.session_spans` provides the full list. At TRACE level, `EvaluatorInput.target_trace_id` identifies which trace to scope the evaluation to.

---

## When to Use Code-Based Evaluators

- **Exact data validation** — check that specific numbers, IDs, or codes appear in responses
- **Format compliance** — validate response length, structure, or formatting constraints
- **Business rule enforcement** — encode domain-specific rules that LLMs might interpret loosely
- **High-volume evaluation** — reduce cost for evaluations that run on every production session
- **Regulatory requirements** — verify that required disclosures or disclaimers are always present

> **Note:** Code-based evaluators are supported for **on-demand evaluation** (`EvaluationClient`, `OnDemandEvaluationDatasetRunner`) only. Online evaluation configs support built-in LLM evaluators only.

---

## Cleanup

To remove created AWS resources:

```python
# Delete Lambda functions
for fn in ["hr-response-length", "hr-fact-checker"]:
    lambda_client.delete_function(FunctionName=fn)

# Delete evaluator registrations
for name, eid in CODE_EVAL_IDS.items():
    cp_client.delete_evaluator(evaluatorId=eid)

# Delete agent runtime (only if deployed in this notebook)
if not _agent_loaded:
    agent_runtime.delete()
```

Alternatively, run the cleanup cell (Step 10) in the notebook — it is commented out by default to prevent accidental deletion.

---

## Next Steps

- Extend `HRFactChecker` with additional business rules as your agent and data model evolve
- Combine code-based evaluators with `EvaluationClient` to validate specific production sessions
- Add code-based evaluators to your CI/CD pipeline for zero-cost regression testing on every deployment
- Explore the [groundtruth tutorial](../05-groundtruth-based-evalautions/) for `EvaluationClient` and ground-truth-based evaluations with built-in evaluators
