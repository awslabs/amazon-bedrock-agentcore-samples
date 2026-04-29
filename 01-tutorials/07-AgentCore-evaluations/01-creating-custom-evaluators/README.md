# Creating Evaluators

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Evaluator Management                                    │
│                                                          │
│  bedrock-agentcore-control (boto3)                       │
│       │                                                  │
│       ├── list_evaluators()    ──► built-in list         │
│       ├── get_evaluator()      ──► evaluator details     │
│       ├── create_evaluator()   ──► custom evaluator      │
│       └── delete_evaluator()   ──► cleanup               │
│                                                          │
│  Custom Evaluator                                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Instructions (natural language)                 │   │
│  │  Rating Scale (numerical or categorical)         │   │
│  │  Model Config (Bedrock model + inference params) │   │
│  │  Level: TRACE | SESSION                          │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## What's This Feature

In this tutorial you will learn about AgentCore Evaluations built-in and custom metrics. You'll learn when to use each type and how to create custom evaluators tailored to your specific needs.

### What You'll Learn
- Understanding built-in evaluators and their use cases
- Creating custom evaluators for specialized requirements
- Selecting the right evaluation approach for your agents

### Built-in Evaluators

Built-in evaluators are pre-configured evaluators that use Large Language Models (LLMs) as judges to assess agent performance.

**Key Characteristics:**
- **Pre-configured**: Come with carefully crafted prompt templates, selected evaluator models, and standardized scoring criteria
- **Ready to use**: No additional configuration required—start evaluating immediately
- **Consistent**: Fixed configurations ensure reliability and consistency across assessments
- **Comprehensive**: Cover 13 critical evaluation dimensions including correctness, helpfulness, and safety

**When to Use Built-in Evaluators:**
- You need to implement quality evaluations quickly
- You want standardized assessment metrics across teams or projects
- Your evaluation needs align with common quality dimensions
- You prioritize consistency and reliability over customization

The following built-in evaluators are available:
* Response quality metrics:
  * **Builtin.Correctness**: Evaluates whether the information in the agent's response is factually accurate
  * **Builtin.Faithfulness**: Evaluates whether information in the response is supported by provided context/sources
  * **Builtin.Helpfulness**: Evaluates from user's perspective how useful and valuable the agent's response is
  * **Builtin.ResponseRelevance**: Evaluates whether the response appropriately addresses the user's query
  * **Builtin.Conciseness**: Evaluates whether the response is appropriately brief without missing key information
  * **Builtin.Coherence**: Evaluates whether the response is logically structured and coherent
  * **Builtin.InstructionFollowing**: Measures how well the agent follows the provided system instructions
  * **Builtin.Refusal**: Detects when agent evades questions or directly refuses to answer
* Task completion metrics:
  * **Builtin.GoalSuccessRate**: Evaluates whether the conversation successfully meets the user's goals
* Tool level metrics:
  * **Builtin.ToolSelectionAccuracy**: Evaluates whether the agent selected the appropriate tool for the task
  * **Builtin.ToolParameterAccuracy**: Evaluates how accurately the agent extracts parameters from user queries
* Safety metrics:
  * **Builtin.Harmfulness**: Evaluates whether the response contains harmful content
  * **Builtin.Stereotyping**: Detects content that makes generalizations about individuals or groups

**Note:** Built-in evaluator configurations cannot be modified to maintain evaluation consistency and reliability across all users, but you can create your own evaluator using a built-in one as a base.

### Custom Evaluators

Custom evaluators provide maximum flexibility by allowing you to define every aspect of your evaluation process while leveraging LLMs as underlying judges.

**Customization Options:**
- **Evaluator model**: Choose the LLM that best fits your evaluation needs
- **Evaluation prompts**: Craft evaluation instructions specific to your use case
- **Scoring schema**: Design scoring systems that align with your organization's metrics

**When to Use Custom Evaluators:**
- You're evaluating domain-specific agents (e.g., healthcare, finance, legal)
- You have unique quality standards or compliance requirements
- You need specialized scoring systems aligned with organizational KPIs
- Built-in evaluators don't capture your specific evaluation dimensions

**Example Use Cases:**
- Healthcare agents requiring HIPAA compliance evaluation
- Financial agents needing regulatory adherence scoring
- Customer service agents evaluated against brand-specific quality standards
- Technical support agents assessed on troubleshooting methodology

## CLI Commands

Install the AgentCore CLI:

```bash
npm install -g @aws/agentcore@0.11.0
```

List built-in evaluators via Python (no AWS CLI subcommand exists for this):

```python
import boto3
cp = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
response = cp.list_evaluators()
for ev in response["evaluators"]:
    print(ev["evaluatorId"], ev["evaluatorType"], ev["status"])
```

Create a custom evaluator via CLI (from inside your project directory):

```bash
# Add a custom evaluator to your project config using CLI flags:
agentcore add evaluator \
  --name response_quality_for_scope \
  --level TRACE \
  --model "global.anthropic.claude-sonnet-4-5-20250929-v1:0" \
  --instructions "Evaluate whether the agent response is relevant and accurate. Context: {context}" \
  --rating-scale 1-5-quality

# Then deploy to create the evaluator in AWS:
agentcore deploy
```

Create a custom evaluator directly via boto3:

```python
import boto3

cp = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
result = cp.create_evaluator(
    evaluatorName="response_quality_for_scope",
    level="TRACE",
    evaluatorConfig=eval_config,
)
evaluator_id = result["evaluatorId"]
```

## Cleanup

Delete a custom evaluator:

```bash
aws bedrock-agentcore-control delete-evaluator \
  --evaluator-id <evaluator-id> \
  --region us-east-1
```

Or via Python:

```python
import boto3
cp = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
cp.delete_evaluator(evaluatorId="<evaluator-id>")
```

## Next Steps

After completing this tutorial, proceed to [Using On-demand Evaluation](../02-running-evaluations) to learn how to apply these evaluators to your agent traces.
