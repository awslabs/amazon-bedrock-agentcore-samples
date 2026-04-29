# Running Evaluations with LangGraph

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  LangGraph Agent Evaluation Flow                         │
│                                                          │
│  AgentCore Runtime (LangGraph agent)                     │
│       │                                                  │
│       ▼ OTel spans                                       │
│  CloudWatch Logs                                         │
│       │                                                  │
│       ├── On-demand ──► EvaluationClient.run()           │
│       │                  evaluator_ids=[...]             │
│       │                  session_id=...                  │
│       │                  agent_id=...                    │
│       │                                                  │
│       └── Online ──► create_online_evaluation_config()   │
│                       (continuous sampling)              │
│                                                          │
│  Results ──► Scores + Explanations + Token Usage         │
└─────────────────────────────────────────────────────────┘
```

## What's This Feature

This tutorial demonstrates how to use AgentCore Evaluations with agents built using [LangGraph](https://www.langchain.com/langgraph). You'll learn to run both on-demand and online evaluations to assess and monitor your LangGraph agent's performance using built-in and custom evaluators.

### What You'll Learn

- Running on-demand evaluations on specific LangGraph agent traces
- Setting up online evaluations for continuous monitoring of LangGraph agents
- Using the AgentCore SDK (`bedrock_agentcore`) and boto3 to manage evaluations
- Analyzing evaluation results to improve agent quality

### Prerequisites

Before starting these tutorials, ensure you have:

- Completed [Tutorial 00: Prerequisites](../../00-prereqs) and created the LangGraph agent
- Completed [Tutorial 01: Creating Custom Evaluators](../../01-creating-custom-evaluators) and created a custom evaluator
- Your LangGraph agent deployed on AgentCore Runtime
- Generated at least one session with traces by invoking your agent
- Python 3.10+ installed
- AWS credentials configured with appropriate permissions

### Tutorial Structure

#### [01-on-demand-eval.ipynb](01-on-demand-eval.ipynb)

**Tutorial Type:** Evaluating LangGraph agent with on-demand evaluators (built-in and custom)

**What You'll Learn:**

- How to retrieve session and trace information from your deployed LangGraph agent
- Initializing the `EvaluationClient` from the `bedrock_agentcore` SDK
- Running on-demand evaluations on specific traces or sessions
- Using both built-in evaluators (e.g., `Builtin.Correctness`, `Builtin.Helpfulness`) and custom evaluators
- Interpreting evaluation results including scores, explanations, and token usage

**Key Concepts:**

- **Targeted Assessment**: Evaluate specific interactions by providing session or trace IDs
- **Synchronous Execution**: Get immediate results for your evaluation requests
- **Flexible Evaluator Selection**: Apply multiple evaluators to the same trace
- **Investigation Tool**: Perfect for analyzing specific interactions or validating fixes

#### [02-online-eval.ipynb](02-online-eval.ipynb)

**Tutorial Type:** Evaluating LangGraph agent with online evaluators (built-in and custom)

**What You'll Learn:**

- Creating online evaluation configurations for your LangGraph agent
- Configuring sampling rates and filtering rules
- Setting up continuous evaluation with built-in and custom evaluators
- Monitoring evaluation results in CloudWatch dashboards
- Managing online evaluation configurations (enable, disable, update, delete)

**Key Concepts:**

- **Continuous Monitoring**: Automatically evaluate agent performance as interactions occur
- **Sampling-Based**: Configure percentage-based sampling (e.g., evaluate 10% of sessions)
- **Real-time Insights**: Track quality trends and catch regressions early
- **Production-Ready**: Designed for scale with minimal performance impact

### LangGraph Agent Architecture

The LangGraph agent used in these tutorials includes:

**Tools:**

- Math tool for basic calculations
- Weather tool for weather information

**Model:**

- Anthropic Claude Haiku 4.5 from Amazon Bedrock

**Observability:**

- Automatic OTEL instrumentation via AgentCore Runtime
- Traces available in CloudWatch GenAI Observability Dashboard

### How Evaluations Work with LangGraph Agents

1. **Agent Invocation**: Your LangGraph agent processes user requests
2. **Trace Generation**: AgentCore Observability captures OTEL traces automatically
3. **Trace Storage**: Traces are stored in CloudWatch Log groups
4. **Evaluation**:
   - **On-demand**: You select specific sessions/traces to evaluate
   - **Online**: AgentCore automatically samples and evaluates based on your configuration
5. **Results Analysis**: View scores, explanations, and trends in CloudWatch

## CLI Commands

Install the AgentCore CLI:

```bash
npm install -g @aws/agentcore@0.11.0
```

Run on-demand evaluations:

```bash
# From inside your project directory:
agentcore run eval \
  --runtime acevallanggraph2 \
  --evaluator Builtin.GoalSuccessRate \
  --session-id <your-session-id>

# Using ARNs directly (outside a project directory):
agentcore run eval \
  --runtime-arn <agent-runtime-arn> \
  --evaluator Builtin.GoalSuccessRate \
  --evaluator Builtin.Correctness \
  --session-id <your-session-id> \
  --region us-east-1

# View saved evaluation history
agentcore evals history
```

Create an online evaluation configuration:

```bash
agentcore add online-eval \
  --name langraphevalconfig \
  --runtime acevallanggraph2 \
  --evaluator Builtin.GoalSuccessRate \
  --evaluator Builtin.Correctness \
  --evaluator Builtin.ToolParameterAccuracy \
  --evaluator Builtin.ToolSelectionAccuracy \
  --sampling-rate 100 \
  --enable-on-create

agentcore deploy

# Pause and resume:
agentcore pause online-eval langraphevalconfig
agentcore resume online-eval langraphevalconfig
```

Using the AgentCore SDK directly (Python):

```python
from bedrock_agentcore.evaluation import EvaluationClient
from datetime import timedelta

eval_client = EvaluationClient(region_name="us-east-1")

results = eval_client.run(
    evaluator_ids=["Builtin.GoalSuccessRate", "Builtin.Correctness"],
    agent_id=agent_id_langgraph,
    session_id=session_id_langgraph,
    look_back_time=timedelta(hours=24),
)

for result in results:
    print(result.get("label"), result.get("value"), result.get("explanation"))
```

Creating an online evaluation config (boto3):

```python
import boto3

cp = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
response = cp.create_online_evaluation_config(
    onlineEvaluationConfigName="langgraph_agent_eval2",
    rule={"samplingConfig": {"samplingPercentage": 100.0}},
    dataSourceConfig={
        "cloudWatchLogs": {
            "logGroupNames": ["/aws/bedrock-agentcore/runtimes/<agent-id>-DEFAULT"],
            "serviceNames": ["<runtime-name>.DEFAULT"],
        }
    },
    evaluators=[{"evaluatorId": "Builtin.GoalSuccessRate"}],
    evaluationExecutionRoleArn="arn:aws:iam::<account>:role/AgentCoreOnlineEvaluationRole",
    enableOnCreate=True,
)
```

## Expected Outcomes

After completing these tutorials, you will be able to:

- Evaluate specific LangGraph agent interactions using on-demand evaluations
- Set up continuous quality monitoring for production LangGraph agents
- Analyze evaluation results to identify areas for improvement
- Use both built-in and custom evaluators effectively
- Monitor agent quality trends over time

## Cleanup

Delete the online evaluation configuration:

```python
import boto3
cp = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
cp.delete_online_evaluation_config(onlineEvaluationConfigId="<config-id>")
```

Delete the IAM role created for online evaluation:

```bash
aws iam delete-role-policy \
  --role-name AgentCoreOnlineEvaluationRole \
  --policy-name AgentCoreOnlineEvalPolicy

aws iam delete-role \
  --role-name AgentCoreOnlineEvaluationRole
```

## Next Steps

After completing these LangGraph-specific tutorials:

- Explore the [Strands examples](../01-strands/) to see how evaluations work with different frameworks
- Proceed to [Tutorial 03: Advanced](../../03-advanced) for advanced evaluation techniques
- Review your evaluation results in the CloudWatch GenAI Observability Dashboard
