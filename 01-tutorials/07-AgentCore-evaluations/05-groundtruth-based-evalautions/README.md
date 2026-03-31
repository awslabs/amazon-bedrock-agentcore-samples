# Ground Truth Evaluations — EvaluationClient and EvaluationRunner

## Overview

This tutorial demonstrates end-to-end evaluation of an agentic application using Amazon Bedrock AgentCore's two primary evaluation interfaces: **EvaluationClient** and **OnDemandEvaluationDatasetRunner**. Both are used with ground-truth reference inputs to measure factual correctness, goal achievement, and tool-use accuracy.

The tutorial uses an **HR Assistant agent** for Acme Corp — a Strands agent that helps employees with PTO management, HR policy lookups, benefits information, and pay stubs.

## What You'll Learn

- How to deploy a Strands agent to AgentCore Runtime
- When to use `EvaluationClient` vs `EvaluationRunner`
- How to evaluate existing sessions with ground-truth `ReferenceInputs`
- How to define an evaluation dataset with `TurnByTurnScenario` and `Turn`
- How to run automated dataset evaluations with `EvaluationRunner`
- How to interpret built-in evaluator results for trajectory, correctness, and goal-success metrics
- How to create **custom LLM-as-a-judge evaluators** with ground-truth placeholders

## Prerequisites

Before running this tutorial, ensure you have:

- Python 3.10+
- AWS credentials with permissions for:
  - AgentCore Runtime (`bedrock-agentcore:*`)
  - AgentCore Evaluations (`bedrock-agentcore:Evaluate`)
  - CloudWatch Logs (`logs:FilterLogEvents`, `logs:DescribeLogGroups`)
  - ECR (`ecr:*`)
  - IAM (for auto-creating the agent execution role)

## Files

| File | Description |
|---|---|
| `groundtruth_evaluations.ipynb` | Main tutorial notebook (standalone, end-to-end) |
| `hr_assistant_agent.py` | HR Assistant Strands agent deployed to AgentCore Runtime |
| `requirements.txt` | Python dependencies for the agent container |

## Tutorial Notebook

### [groundtruth_evaluations.ipynb](groundtruth_evaluations.ipynb)

A single self-contained notebook that walks through the full evaluation workflow in 7 steps:

| Step | Description |
|---|---|
| 1 | Install dependencies |
| 2 | Configure AWS session and region |
| 3a | Deploy the HR Assistant agent to AgentCore Runtime |
| 3b | **Create custom LLM-as-a-judge evaluators** with ground-truth placeholders |
| 4 | Invoke the agent to generate sessions with CloudWatch spans |
| 5 | **EvaluationClient** — evaluate existing sessions with ground truth |
| 6 | **OnDemandEvaluationDatasetRunner** — automated dataset evaluation |
| 7 | Cleanup |

## EvaluationClient vs EvaluationRunner

| | EvaluationClient | EvaluationRunner |
|---|---|---|
| **When to use** | You already have recorded sessions | You have a test dataset |
| **Input** | `session_id` + `agent_id` | `Dataset` of `TurnByTurnScenario` objects |
| **Best for** | Post-hoc analysis, debugging, incident investigation | Regression testing, CI/CD pipelines, batch evaluation |

## Ground-Truth Reference Inputs

`ReferenceInputs` supplies optional ground truth to `EvaluationClient`. Each field is consumed by specific evaluators:

| Field | Evaluators that use it | Description |
|---|---|---|
| `expected_response` | `Builtin.Correctness` | The ideal response text for semantic comparison |
| `expected_trajectory` | `Builtin.TrajectoryExactOrderMatch`, `Builtin.TrajectoryInOrderMatch`, `Builtin.TrajectoryAnyOrderMatch` | Ordered list of tool names the agent should call |
| `assertions` | `Builtin.GoalSuccessRate` | Free-text assertions the session should satisfy |

Evaluators that don't require ground truth (`Builtin.Helpfulness`, `Builtin.ResponseRelevance`) can be included in the same call — each evaluator reads only the fields it needs.

The same fields apply to `PredefinedScenario` objects in `OnDemandEvaluationDatasetRunner` datasets.

## Custom Evaluators with Ground Truth

In addition to built-in evaluators, you can define **custom LLM-as-a-judge evaluators** with
evaluation criteria written in natural language. Custom evaluators support the same ground-truth
fields through **placeholders** that the service substitutes at evaluation time.

### Placeholder reference

| Level | Placeholder | Filled from |
|---|---|---|
| TRACE | `{assistant_turn}` | Agent's actual response for that turn |
| TRACE | `{expected_response}` | `ReferenceInputs.expected_response` |
| TRACE | `{context}` | Conversation context preceding the turn |
| SESSION | `{actual_tool_trajectory}` | Tools the agent called during the session |
| SESSION | `{expected_tool_trajectory}` | `ReferenceInputs.expected_trajectory` |
| SESSION | `{assertions}` | `ReferenceInputs.assertions` |
| SESSION | `{available_tools}` | Tools available to the agent |


The notebook demonstrates two custom evaluators:

| Evaluator | Level | Placeholders | Description |
|---|---|---|---|
| `HRResponseSimilarity` | TRACE | `{assistant_turn}`, `{expected_response}` | Scores how closely the agent's response matches the expected answer |
| `HRAssertionChecker` | SESSION | `{actual_tool_trajectory}`, `{expected_tool_trajectory}`, `{assertions}` | Scores whether the agent called the right tools and satisfied all assertions |

## Built-in Evaluators Used

| Evaluator | Level | Ground Truth |
|---|---|---|
| `Builtin.Correctness` | TRACE | `expected_response` |
| `Builtin.GoalSuccessRate` | SESSION | `assertions` |
| `Builtin.TrajectoryExactOrderMatch` | SESSION | `expected_trajectory` |
| `Builtin.TrajectoryInOrderMatch` | SESSION | `expected_trajectory` |
| `Builtin.TrajectoryAnyOrderMatch` | SESSION | `expected_trajectory` |
| `Builtin.Helpfulness` | TRACE | None |
| `Builtin.ResponseRelevance` | TRACE | None |

**Evaluation levels:**
- **TRACE** — evaluated once per agent response (one result per conversational turn)
- **SESSION** — evaluated once per conversation (one result per scenario)

## The HR Assistant Agent

The agent is built with the [Strands Agents SDK](https://strandsagents.com/) and deployed on AgentCore Runtime. It exposes five tools backed by deterministic mock data, making evaluations fully reproducible:

| Tool | Description |
|---|---|
| `get_pto_balance` | Returns remaining PTO days for an employee |
| `submit_pto_request` | Submits a time-off request |
| `lookup_hr_policy` | Looks up PTO, remote work, parental leave, or code-of-conduct policies |
| `get_benefits_summary` | Returns health, dental, vision, 401k, or life insurance details |
| `get_pay_stub` | Retrieves gross and net pay for a given employee and period |

## Evaluation Scenarios

The notebook evaluates five scenarios that cover different evaluation patterns:

| Scenario | Turns | Key evaluators |
|---|---|---|
| PTO balance check | 1 | Correctness, Helpfulness, **HRResponseSimilarity** (custom) |
| PTO submission | 1 | GoalSuccessRate, Trajectory, Correctness, **HRResponseSimilarity** (custom) |
| Pay stub lookup | 1 | Correctness, GoalSuccessRate |
| PTO planning session | 3 | GoalSuccessRate, TrajectoryExactOrderMatch, **HRAssertionChecker** (custom) |
| New employee onboarding | 4 | GoalSuccessRate, TrajectoryAnyOrderMatch |

