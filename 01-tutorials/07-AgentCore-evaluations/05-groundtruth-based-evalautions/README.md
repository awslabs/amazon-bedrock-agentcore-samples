# Ground Truth Evaluations with Custom Evaluators

## Introduction

This tutorial demonstrates end-to-end evaluation of an agentic application using
[**Amazon Bedrock AgentCore Evaluations**](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/evaluations.html) with ground-truth reference inputs. It covers
the two primary evaluation interfaces — `EvaluationClient` and
`OnDemandEvaluationDatasetRunner` — and shows how to create **custom LLM-as-a-judge
evaluators** that use ground-truth placeholders to tailor scoring criteria to your
application domain.

The tutorial deploys an **HR Assistant agent** for Acme Corp — a
[Strands Agents](https://strandsagents.com/) application that helps employees with PTO
management, HR policy lookups, benefits information, and pay stub retrieval. Its tools
return deterministic mock data, making evaluation results fully reproducible.

### Key concepts covered

| Concept | Description |
|---|---|
| `EvaluationClient` | Evaluate specific existing CloudWatch sessions against ground-truth references |
| `OnDemandEvaluationDatasetRunner` | Define a test dataset, auto-invoke the agent per scenario, and evaluate the results |
| `ReferenceInputs` | Supply `expected_response`, `expected_trajectory`, and `assertions` as ground truth |
| Custom evaluators | Create LLM-as-a-judge evaluators with domain-specific instructions and ground-truth placeholders |


> **Further reading**
> - [Ground-truth evaluations — custom evaluators](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/ground-truth-evaluations.html#gt-custom-evaluators)
> - [Dataset-based evaluations](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/dataset-evaluations.html)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Tutorial Notebook (groundtruth_evaluations.ipynb)                      │
│                                                                         │
│  Step 1  ──► bedrock-agentcore-starter-toolkit                         │
│               │  CodeBuild builds image, pushes to ECR                  │
│               └──► AgentCore Runtime  (HR Assistant Agent)              │
│                         │  invoke_agent_runtime()                       │
│  Step 2  ──► bedrock-agentcore-control ──► Custom Evaluators           │
│               create_evaluator()                                        │
│                                                                         │
│  Step 3   ──► AgentCore Runtime  (generate sessions)                    │
│               │  OTel spans ──► CloudWatch Logs                         │
│                                                                         │
│  Step 4   ──► EvaluationClient.run()                                    │
│               │  CloudWatchAgentSpanCollector reads spans               │
│               └──► Evaluate API  ──► Built-in + Custom Evaluators       │
│                                       └──► Scores & Explanations        │
│                                                                         │
│  Step 5   ──► OnDemandEvaluationDatasetRunner.run()                     │
│               │  Invokes agent per scenario                             │
│               │  Waits for CloudWatch ingestion                         │
│               └──► Evaluate API  ──► Built-in + Custom Evaluators       │
│                                       └──► Per-scenario Results         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Component roles**

| Component | Role |
|---|---|
| AgentCore Runtime | Hosts the containerised HR Assistant, emits OTel spans to CloudWatch |
| CloudWatch Logs | Stores session spans; queried by `CloudWatchAgentSpanCollector` |
| `bedrock-agentcore-control` | Control plane — creates custom evaluators and agent runtimes |
| Evaluate API (`bedrock-agentcore`) | Data plane — scores sessions against evaluator definitions |
| Starter Toolkit | Builds the Docker image via CodeBuild and registers the runtime; no local Docker required |

---

## Prerequisites

- **Python 3.10+** with the packages in `requirements.txt`
- **AWS credentials** configured (e.g. via `aws configure` or environment variables) with
  permissions for:
  - `bedrock-agentcore:*` — invoke agent runtime and call Evaluate API
  - `bedrock-agentcore-control:CreateAgentRuntime`, `UpdateAgentRuntime`,
    `GetAgentRuntime`, `CreateEvaluator` — deploy agent and register evaluators
  - `logs:FilterLogEvents`, `logs:DescribeLogGroups`, `logs:StartQuery`,
    `logs:GetQueryResults` — read CloudWatch spans
  - `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`,
    `ecr:InitiateLayerUpload`, `ecr:PutImage` — push container image
  - `codebuild:StartBuild`, `codebuild:BatchGetBuilds` — image build via CodeBuild
  - `iam:CreateRole`, `iam:AttachRolePolicy`, `iam:PassRole` — auto-create execution roles
  - `s3:PutObject`, `s3:GetObject` — CodeBuild source upload
- **No local Docker required** — the starter toolkit builds the container image via
  AWS CodeBuild

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Usage

### Run the notebook

Open and run [`groundtruth_evaluations.ipynb`](groundtruth_evaluations.ipynb) top-to-bottom.
Each cell is idempotent — re-running the notebook updates the existing agent runtime and
creates fresh custom evaluators with a unique suffix to avoid naming conflicts.

```bash
jupyter notebook groundtruth_evaluations.ipynb
```

Or execute non-interactively:

```bash
jupyter nbconvert --to notebook --execute --inplace groundtruth_evaluations.ipynb
```

### Notebook walkthrough

| Step | Cell(s) | What happens |
|---|---|---|
| **1 — Install** | `install` | Installs `bedrock-agentcore`, `strands-agents`, and other dependencies |
| **2 — Configure** | `setup` | Creates a boto3 session and sets `REGION` |
| **3a — Deploy agent** | `nn72gdo2s4h`, `deploy`, `wait-deploy`, `agent-config` | Writes `hr_assistant_agent.py`, builds image via CodeBuild, creates/updates the AgentCore Runtime, polls until `READY` |
| **3b — Create evaluators** | `76hyptexblj` | Creates `HRResponseSimilarity` (TRACE) and `HRAssertionChecker` (SESSION) custom evaluators via `bedrock-agentcore-control` |
| **4 — Invoke agent** | `invoke-single`, `invoke-multi`, `invoke-onboard` | Runs 5 sessions (single- and multi-turn), waits 60 s for CloudWatch ingestion |
| **5 — EvaluationClient** | `ec-*` | Evaluates each session by session ID using built-in and custom evaluators |
| **6 — DatasetRunner** | `runner-*` | Defines a 5-scenario dataset, invokes the agent per scenario, waits 180 s, evaluates all scenarios |
| **7 — Cleanup** | `cleanup` | (Commented out) Deletes the agent runtime |

### Using `EvaluationClient` directly

```python
from bedrock_agentcore.evaluation import EvaluationClient, ReferenceInputs
from datetime import timedelta

ec = EvaluationClient(region_name="us-east-1")

results = ec.run(
    evaluator_ids=["Builtin.Correctness", "Builtin.GoalSuccessRate", MY_CUSTOM_EVAL_ID],
    session_id="<session-id>",
    agent_id="<agent-id>",
    look_back_time=timedelta(hours=2),
    reference_inputs=ReferenceInputs(
        expected_response="Employee EMP-001 has 10 remaining PTO days.",
        assertions=["Agent called get_pto_balance", "Agent reported 10 remaining days"],
        expected_trajectory=["get_pto_balance"],
    ),
)
```

### Using `OnDemandEvaluationDatasetRunner` directly

```python
from bedrock_agentcore.evaluation import (
    Dataset, PredefinedScenario, Turn,
    EvaluationRunConfig, EvaluatorConfig,
    OnDemandEvaluationDatasetRunner,
    CloudWatchAgentSpanCollector,
)

dataset = Dataset(scenarios=[
    PredefinedScenario(
        scenario_id="pto-check",
        turns=[Turn(
            input="What is the PTO balance for EMP-001?",
            expected_response="EMP-001 has 10 remaining PTO days.",
        )],
        expected_trajectory=["get_pto_balance"],
        assertions=["Agent reported 10 remaining PTO days"],
    ),
])

runner = OnDemandEvaluationDatasetRunner(region="us-east-1")
result = runner.run(
    config=EvaluationRunConfig(
        evaluator_config=EvaluatorConfig(evaluator_ids=["Builtin.Correctness"]),
        evaluation_delay_seconds=180,
    ),
    dataset=dataset,
    agent_invoker=my_invoker_fn,
    span_collector=CloudWatchAgentSpanCollector(log_group_name=CW_LOG_GROUP, region="us-east-1"),
)
```

---

## Sample Prompts

The following prompts are used in the notebook. They can also be sent directly to a
deployed HR Assistant to generate sessions for evaluation.

### Single-turn

| Prompt | Expected tool | Expected outcome |
|---|---|---|
| `What is the current PTO balance for employee EMP-001?` | `get_pto_balance` | 10 remaining days (15 total, 5 used) |
| `Please submit a PTO request for EMP-001 from 2026-04-14 to 2026-04-16 for a family vacation.` | `submit_pto_request` | Approved, request ID `PTO-2026-001` |
| `Can you pull up the January 2026 pay stub for employee EMP-001?` | `get_pay_stub` | Gross $8,333.33, net $5,362.50 |
| `What is the company PTO policy?` | `lookup_hr_policy` | 15 days/year, 2-day advance notice, 5-day rollover |
| `How does the 401k match work?` | `get_benefits_summary` | 100% match up to 4%, 50% on next 2%, 3-year vesting |
| `Check the PTO balance for EMP-002 and if they have at least 2 days, submit a request for 2026-05-26 to 2026-05-27.` | `get_pto_balance` → `submit_pto_request` | 3 days remaining → request approved |

### Multi-turn

**PTO planning (3 turns)**
1. `How many PTO days do I have left? My employee ID is EMP-001.`
2. `Great. I'd like to take December 23 to December 25 off. Please submit a request.`
3. `Remind me — what is the policy on rolling over unused PTO?`

Expected trajectory: `get_pto_balance` → `submit_pto_request` → `lookup_hr_policy`

**New employee onboarding (4 turns)**
1. `I just joined the company. What is the remote work policy?`
2. `How much PTO do I get as a new employee?`
3. `What life insurance benefit does the company provide?`
4. `Can you check the current PTO balance for employee EMP-042?`

Expected trajectory: `lookup_hr_policy` → `lookup_hr_policy` → `get_benefits_summary` → `get_pto_balance`

---

## Custom Evaluators with Ground Truth

Custom evaluators let you define evaluation criteria in natural language. The service
substitutes **ground-truth placeholders** from `ReferenceInputs` before scoring.

### Placeholder reference

| Level | Placeholder | Populated from |
|---|---|---|
| TRACE | `{assistant_turn}` | Agent's actual response for that turn |
| TRACE | `{expected_response}` | `ReferenceInputs.expected_response` |
| TRACE | `{context}` | Conversation context preceding the turn |
| SESSION | `{actual_tool_trajectory}` | Tools the agent called during the session |
| SESSION | `{expected_tool_trajectory}` | `ReferenceInputs.expected_trajectory` |
| SESSION | `{assertions}` | `ReferenceInputs.assertions` |
| SESSION | `{available_tools}` | Tools available to the agent |

### Creating a custom evaluator

```python
import boto3, uuid

cp = boto3.client("bedrock-agentcore-control", region_name="us-east-1")

# Trace-level: response similarity using ground-truth placeholders
result = cp.create_evaluator(
    evaluatorName=f"ResponseSimilarity_{uuid.uuid4().hex[:8]}",
    level="TRACE",
    evaluatorConfig={
        "llmAsAJudge": {
            "instructions": (
                "Compare the agent's response with the expected response.\n"
                "Agent response: {assistant_turn}\n"
                "Expected response: {expected_response}\n\n"
                "Rate how closely the responses match on a scale of 0 to 1."
            ),
            "ratingScale": {
                "numerical": [
                    {"value": 0.0, "label": "not_similar",
                     "definition": "Response is factually different from expected."},
                    {"value": 0.5, "label": "partially_similar",
                     "definition": "Response partially matches expected."},
                    {"value": 1.0, "label": "highly_similar",
                     "definition": "Response is semantically equivalent to expected."},
                ]
            },
            "modelConfig": {
                "bedrockEvaluatorModelConfig": {
                    "modelId": "us.amazon.nova-lite-v1:0",
                    "inferenceConfig": {"maxTokens": 512},
                }
            },
        }
    },
)
custom_evaluator_id = result["evaluatorId"]
```

Pass `custom_evaluator_id` to `EvaluationClient.run()` or `EvaluatorConfig` like any
built-in evaluator ID. Seed the level cache to avoid an extra `get_evaluator` lookup:

```python
eval_client._evaluator_level_cache[custom_evaluator_id] = "TRACE"
```

### Custom evaluators in this tutorial

| Evaluator | Level | Placeholders used | Where used |
|---|---|---|---|
| `HRResponseSimilarity` | TRACE | `{assistant_turn}`, `{expected_response}` | EvaluationClient (Steps 5a, 5b), DatasetRunner (Step 6) |
| `HRAssertionChecker` | SESSION | `{actual_tool_trajectory}`, `{expected_tool_trajectory}`, `{assertions}` | EvaluationClient (Step 5d, multi-turn), DatasetRunner (Step 6) |

> **Note:** SESSION-level custom evaluators require a session with multiple tool calls to
> extract a meaningful trajectory. They are used on multi-turn sessions in Step 5d and on
> all DatasetRunner scenarios in Step 6, where a 180-second ingestion delay ensures span
> data is complete before evaluation.

---

## Built-in Evaluators

| Evaluator | Level | Ground truth required |
|---|---|---|
| `Builtin.Correctness` | TRACE | `expected_response` |
| `Builtin.Helpfulness` | TRACE | None |
| `Builtin.ResponseRelevance` | TRACE | None |
| `Builtin.GoalSuccessRate` | SESSION | `assertions` |
| `Builtin.TrajectoryExactOrderMatch` | SESSION | `expected_trajectory` |
| `Builtin.TrajectoryInOrderMatch` | SESSION | `expected_trajectory` |
| `Builtin.TrajectoryAnyOrderMatch` | SESSION | `expected_trajectory` |

**Evaluation levels:**
- **TRACE** — one result per conversational turn (agent response)
- **SESSION** — one result per complete conversation

---

## Files

| File | Description |
|---|---|
| `groundtruth_evaluations.ipynb` | Main tutorial notebook — self-contained, end-to-end |
| `requirements.txt` | Python dependencies installed into the agent container |

`hr_assistant_agent.py` and `.bedrock_agentcore.yaml` are generated at runtime (by the `%%writefile` notebook cell and the starter toolkit respectively)

---

## Clean Up

### Delete the agent runtime

Uncomment and run the cleanup cell in the notebook:

```python
agentcore_runtime.delete()
```

Or via the AWS CLI:

```bash
aws bedrock-agentcore delete-agent-runtime \
    --agent-runtime-id hr_assistant_eval_tutorial-xfZ3yiH356 \
    --region us-east-1
```

### Delete custom evaluators

```python
import boto3

cp = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
for evaluator_id in [CUSTOM_RESPONSE_SIMILARITY_ID, CUSTOM_ASSERTION_CHECKER_ID]:
    cp.delete_evaluator(evaluatorId=evaluator_id)
    print(f"Deleted {evaluator_id}")
```

### Delete the ECR repository

```bash
aws ecr delete-repository \
    --repository-name bedrock-agentcore-hr_assistant_eval_tutorial \
    --region us-east-1 \
    --force
```

### Delete CloudWatch log group

```bash
aws logs delete-log-group \
    --log-group-name /aws/bedrock-agentcore/runtimes/hr_assistant_eval_tutorial-xfZ3yiH356-DEFAULT \
    --region us-east-1
```

---

## Additional Resources

- [Ground-truth evaluations — custom evaluators](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/ground-truth-evaluations.html#gt-custom-evaluators)
- [Dataset-based evaluations](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/dataset-evaluations.html)
- [Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [Strands Agents SDK](https://strandsagents.com/)
- [Build reliable AI agents with Amazon Bedrock AgentCore Evaluations](https://aws.amazon.com/blogs/machine-learning/build-reliable-ai-agents-with-amazon-bedrock-agentcore-evaluations/)
