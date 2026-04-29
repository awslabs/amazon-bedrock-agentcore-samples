# AgentCore Evaluations Tutorials

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  AgentCore Evaluations                                   │
│                                                          │
│  Agent ──► AgentCore Runtime ──► CloudWatch Logs        │
│                  │                    │                  │
│                  │              OTel spans               │
│                  │                    │                  │
│  On-demand ◄─────┼────── EvaluationClient.run()         │
│  evaluation      │                                       │
│                  │                                       │
│  Online    ◄─────┼────── create_online_evaluation_config│
│  evaluation      │         (continuous sampling)         │
│                  ▼                                       │
│              Evaluators                                  │
│           (built-in + custom)                            │
│                  │                                       │
│                  ▼                                       │
│          Score + Explanation                             │
└─────────────────────────────────────────────────────────┘
```

## What's This Feature

Amazon Bedrock AgentCore Evaluations helps you optimize your agent's quality based on real-world interactions.

While AgentCore Observability provides operational insights into agent health, AgentCore Evaluations focuses on agent decision quality and performance outcomes.

It provides built-in and custom evaluators with both on-demand and online evaluation capabilities.

### Built-in and Custom Evaluators

AgentCore Evaluations offers 13 built-in evaluators for critical dimensions like correctness, helpfulness, and safety, plus the ability to create custom evaluators for business-specific requirements.

Test your agents during development and deployment using the on-demand evaluations API, or monitor production agents with the online evaluations API.

### On-demand Evaluations

Run synchronous, on-demand evaluations using built-in and custom metrics on individual traces.

The system uses OpenTelemetry (OTEL) traces to perform scoring and returns a response that includes:
- Score value
- Explanation for the score
- Token usage

### Online Evaluations

In production, you need continuous performance monitoring across all interactions without manually evaluating each trace. A statistical sample is often sufficient for generating meaningful performance metrics.

AgentCore Evaluations' online capabilities enable automatic sampling and evaluation:

- Define your sample size and trace selection criteria
- Choose your evaluation metrics (built-in or custom)
- AgentCore Evaluations handles the rest, generating the performance data you need to monitor your agent at scale

## CLI Commands

Install the AgentCore CLI (version pinned for reproducibility):

```bash
npm install -g @aws/agentcore@0.11.0
```

Deploy an agent:

```bash
# Create and deploy a Strands agent
agentcore create --name my_eval_agent --framework Strands
cd my_eval_agent
agentcore deploy

# Create and deploy a LangGraph agent
agentcore create --name my_langgraph_agent --framework LangChain_LangGraph
cd my_langgraph_agent
agentcore deploy
```

Run on-demand evaluations:

```bash
agentcore run eval \
  --runtime my_eval_agent \
  --evaluator Builtin.GoalSuccessRate \
  --evaluator Builtin.Correctness \
  --session-id <session-id>

# View saved evaluation history
agentcore evals history
```

Add an online evaluation configuration:

```bash
agentcore add online-eval \
  --name my_online_eval \
  --runtime my_eval_agent \
  --evaluator Builtin.GoalSuccessRate \
  --evaluator Builtin.Correctness \
  --sampling-rate 100 \
  --enable-on-create

agentcore deploy
```

## Tutorials Overview

In these tutorials we will cover the following functionality:
- [Pre-requisites](00-prereqs): Creating a sample agent to use during the evaluation tutorials
- [Create a custom evaluator](01-creating-custom-evaluators): Learn about built-in and custom metrics, and create a custom metric for evaluating your agents
- [Using on-demand and online evaluations](02-running-evaluations): Learn how to use on-demand and online evaluations to build, optimize, and monitor your agent at scale
- [Advanced](03-advanced): Explore advanced capabilities including using the boto3 SDK to query Amazon CloudWatch logs for on-demand evaluation, and creating local dashboards to visualize experiments with different agent configuration

## Cleanup

Delete agent runtimes when no longer needed:

```bash
aws bedrock-agentcore delete-agent-runtime \
  --agent-runtime-id <agent-runtime-id> \
  --region <region>
```

Delete online evaluation configurations:

```python
import boto3
cp = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
cp.delete_online_evaluation_config(onlineEvaluationConfigId="<config-id>")
```

Delete custom evaluators:

```python
cp.delete_evaluator(evaluatorId="<evaluator-id>")
```
