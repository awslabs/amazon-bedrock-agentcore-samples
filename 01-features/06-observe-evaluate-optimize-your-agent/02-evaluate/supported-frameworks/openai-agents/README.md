# Evaluate an OpenAI Agents SDK agent

Evaluate an [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) agent with Amazon Bedrock AgentCore Evaluations. This sample deploys the shared **HR Assistant** — re-implemented with the OpenAI Agents SDK — to AgentCore Runtime, then scores it with built-in and custom LLM-as-a-judge evaluators, both on-demand and online.

The HR Assistant, its 5 tools, mock data, and system prompt are identical to the Strands version in [`../../utils/`](../../utils/), so ground-truth and expected responses stay consistent across the framework samples.

## What you'll learn

| Concept                       | Description                                                                                             |
| ----------------------------- | ------------------------------------------------------------------------------------------------------- |
| **Framework instrumentation** | Make an OpenAI Agents SDK agent evaluable by adding one OpenTelemetry package — no instrumentation code |
| **OpenAI GPT-5.5 on Bedrock** | Call `openai.gpt-5.5` through Bedrock's OpenAI-compatible Responses API with a Bedrock API key          |
| **AgentCore Memory**          | Persist multi-turn conversation history in the AgentCore Memory service, across microVM restarts        |
| **On-demand evaluation**      | Score a recorded session with built-in + custom LLM-as-a-judge evaluators via `EvaluationClient`        |
| **Online evaluation**         | Continuously score live traffic with an online evaluation config                                        |
| **CLI evaluation**            | Re-evaluate any session from the terminal with the AgentCore CLI                                        |

```
┌───────────────┐  invoke_agent_runtime()  ┌────────────────────────────────┐
│  evaluate.py  │ ────────────────────────▶│  AgentCore Runtime             │
│               │◀──────────────────────── │  HR Assistant (OpenAI Agents)  │
│               │        responses         │   │            │               │
│               │                          │   │ Responses  │ history       │
│               │                          │   ▼ API        ▼               │
│               │                          │ Bedrock      AgentCore         │
│               │                          │ (GPT-5.5)    Memory            │
│               │                          └───────┬────────────────────────┘
│               │                                  │ OTel spans + events
│               │   Evaluate API           ┌───────▼────────────────────────┐
│ EvaluationClient ───────────────────────▶│  CloudWatch                    │
│               │◀──────────────────────── │  (spans, event records)        │
└───────────────┘        scores            └────────────────────────────────┘
```

## How it works

The agent is instrumented for evaluation with the **OpenTelemetry** OpenAI Agents library (`opentelemetry-instrumentation-openai-agents`, scope `opentelemetry.instrumentation.openai_agents`). On AgentCore Runtime, AWS Distro for OpenTelemetry (ADOT) auto-discovers the library at startup — no explicit instrumentation code is needed. The agent's spans and event records flow to CloudWatch, and AgentCore Evaluations reads them from there.

The LLM is **OpenAI GPT-5.5 on Amazon Bedrock** (`openai.gpt-5.5`), reached through the Bedrock mantle endpoint's OpenAI-compatible **Responses API** and authenticated with a [Bedrock API key](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html). The OpenAI Agents SDK talks to it via an `AsyncOpenAI` client:

```python
from agents import Agent, OpenAIResponsesModel
from openai import AsyncOpenAI
from aws_bedrock_token_generator import provide_token

# Bedrock API key: BEDROCK_API_KEY env var (long-term key) if set,
# otherwise a short-term key minted from the runtime's IAM role
api_key = os.environ.get("BEDROCK_API_KEY") or provide_token(region=MODEL_REGION)
client = AsyncOpenAI(base_url=f"https://bedrock-mantle.{MODEL_REGION}.api.aws/openai/v1", api_key=api_key)
model = OpenAIResponsesModel(model="openai.gpt-5.5", openai_client=client)

agent = Agent(name="HRAssistant", instructions=SYSTEM_PROMPT, model=model, tools=[...])
```

Both [Bedrock API key types](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-how.html) work here:

- **Short-term key (default, recommended for production).** `aws-bedrock-token-generator` mints one from the runtime's IAM role credentials on every invocation (a local SigV4 presign, no network call, valid up to 12h). Nothing is stored in code or config.
- **Long-term key (exploration).** Generate one from the Bedrock console (**API keys** → **Generate long-term API key**) or via `aws iam create-service-specific-credential --service-name bedrock.amazonaws.com`, then set it as the `BEDROCK_API_KEY` environment variable on the runtime. Long-term keys are tied to an auto-created IAM user with `AmazonBedrockLimitedAccess`.

Three implementation details matter for evaluation:

- **Responses API, not Chat Completions.** The OpenTelemetry instrumentation extracts the agent's response text from Responses API spans (`ResponseSpanData`); with `OpenAIChatCompletionsModel` the response text is not captured on the spans and evaluators score empty responses. GPT-5.5 is served on the mantle endpoint's `openai/v1` path (`https://bedrock-mantle.<region>.api.aws/openai/v1`) — note this differs from the `/v1` path used by gpt-oss models.
- **Keep SDK tracing enabled.** The instrumentation hooks into the SDK's tracing pipeline, so do not call `set_tracing_disabled(True)` — that would silence the evaluation spans. The SDK's default platform.openai.com exporter is inert without an `OPENAI_API_KEY` and only logs a skip message.
- **AgentCore Memory for conversation history, not `SQLiteSession`.** The SDK's session classes are local to one microVM (history is lost across restarts) and replay full Responses API output items (including model `reasoning` items) as the next turn's input, which the mantle endpoint rejects with an empty output. Instead, `deploy.py` creates an [AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html) resource and the agent persists each turn as a memory event (via `bedrock_agentcore.memory.MemoryClient`), reloading the plain `{"role", "content"}` history at the start of every invocation.

The agent is rebuilt on every invocation so a long-lived runtime never reuses an expired short-term key.

## Prerequisites

- Python 3.10+
- AWS CLI configured with credentials
- Access to `openai.gpt-5.5` on Amazon Bedrock. GPT-5.5 is served from `us-east-1` / `us-east-2` (see [the model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-55.html)); the runtime can be deployed in any region and calls the model cross-region via `BEDROCK_OPENAI_MODEL_REGION` (default `us-east-1`).
- Permissions for: `bedrock-agentcore:*`, `bedrock-agentcore-control:*`, `logs:*`, `iam:CreateRole`, `iam:PutRolePolicy`, `s3:PutObject`, `bedrock:InvokeModel`

## Deploy the agent

```bash
pip install boto3
python deploy.py --region us-west-2
```

This builds an ARM64 deployment package, creates an AgentCore Memory resource (conversation history store, injected as `AGENTCORE_MEMORY_ID`), creates the AgentCore Runtime, and writes `agent_config.json` in this directory (read by `evaluate.py`).

The runtime's IAM role is granted `bedrock-mantle:CreateInference` and `bedrock-mantle:CallWithBearerToken` for the mantle Responses API, plus `bedrock:InvokeModel*` and `bedrock:CallWithBearerToken` (the latter pair covers the `bedrock-runtime/openai/v1` Chat Completions endpoint, should you switch `BEDROCK_OPENAI_BASE_URL` to it). The bearer-token actions are required because the OpenAI-compatible endpoints authenticate with a Bedrock API key rather than SigV4. To use a long-term API key instead of the role-derived short-term key, add `environmentVariables={"BEDROCK_API_KEY": "<your-key>", ...}` to the `create_agent_runtime` call in `deploy.py` (for real workloads, prefer fetching it from AWS Secrets Manager instead of a plain environment variable).

## Run the evaluation

```bash
pip install -r requirements.txt
python evaluate.py --region us-west-2
```

The script:

1. Creates two custom LLM-as-a-judge evaluators (`HRResponseQuality` TRACE, `HRSessionCompleteness` SESSION).
2. Invokes the deployed agent for a 3-turn session and waits ~90s for CloudWatch span ingestion.
3. Runs on-demand evaluation with `EvaluationClient` (built-in + custom evaluators, with `ReferenceInputs` ground truth). Scores are saved to `results/on_demand_results.json`.
4. Creates an online evaluation config that continuously scores live traffic with built-in evaluators. Details are saved to `results/online_eval_config.json`.

## Expected output

```
[1/4] Creating custom LLM-as-a-judge evaluators ...
  Creating HRResponseQuality (TRACE) ...
  Creating HRSessionCompleteness (SESSION) ...

[2/4] Invoking HR Assistant to generate a session ...
  Turn 1: What is the PTO balance for employee EMP-001?
         -> Employee EMP-001 has 10 PTO days remaining (15 total, 5 used) ...
  Turn 2: Please submit a PTO request for EMP-001 from 2026-07-14 to 2026-07-18.
         -> Your PTO request has been submitted and approved. Request ID: PTO-2026-001 ...
  Turn 3: What is the company remote work policy?
         -> Employees may work remotely up to 3 days per week ...

[3/4] Running on-demand evaluation (EvaluationClient) ...
  Evaluator                                     Value    Label
  --------------------------------------------------------------------------------
  Builtin.GoalSuccessRate                       1.0      Yes
  Builtin.Correctness                           1.0      Perfectly Correct
  Builtin.Helpfulness                           1.0      Above And Beyond
  HRResponseQuality                             1.0      excellent
  HRSessionCompleteness                         1.0      complete

[4/4] Creating online evaluation configuration ...
  Online evaluation config created: hr_openai_eval_<suffix>-XXXXXXXXXX
```

TRACE-level evaluators (`Correctness`, `Helpfulness`, `HRResponseQuality`) return one score per turn, so the full run prints 11 results. Online evaluation results appear a few minutes later in CloudWatch at `/aws/bedrock-agentcore/evaluations/results/<config-id>`, one record per evaluator per sampled turn with `gen_ai.evaluation.score.value` and `gen_ai.evaluation.explanation` attributes.

## Evaluate from the CLI

Once sessions exist in CloudWatch, you can re-evaluate them from the terminal with the [AgentCore CLI](https://www.npmjs.com/package/@aws/agentcore) — no Python needed. Because this sample deploys with a plain `deploy.py` (not an `agentcore` project), use the standalone flags:

```bash
npm install -g @aws/agentcore

AGENT_ARN=$(jq -r .agent_arn agent_config.json)
agentcore run eval \
  --runtime-arn "$AGENT_ARN" \
  --evaluator-arn Builtin.Helpfulness Builtin.Correctness \
  --region us-west-2 \
  --session-id <session-id-from-evaluate-py-output> \
  --days 1
```

```
Agent: hr_openai_xxxxxxxx-XXXXXXXXXX | Sessions: 1 | Lookback: 1d

  Builtin.Helpfulness: 0.94

Results saved to: eval_2026-07-10_13-03-07.json
```

Ground truth can be supplied inline with `--assertion`, `--expected-trajectory`, and `--expected-response`. Omit `--session-id` to evaluate every session in the lookback window.

## Troubleshooting ARM64 wheels

`deploy.py` cross-compiles dependencies with `--platform manylinux2014_aarch64 --only-binary=:all:`. If a dependency lacks an aarch64 wheel and the install fails, either:

- add `--no-binary=<package>` for the offending pure-Python package, or
- build the zip on an ARM64 machine or in a `public.ecr.aws/lambda/python:3.13-arm64` container / AWS CodeBuild ARM instead of cross-compiling.

## Clean up

```bash
# Delete the agent runtime and its memory resource
AGENT_ID=$(jq -r .agent_id agent_config.json)
MEMORY_ID=$(jq -r .memory_id agent_config.json)
REGION=$(jq -r .region agent_config.json)
aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-id "$AGENT_ID" --region "$REGION"
aws bedrock-agentcore-control delete-memory --memory-id "$MEMORY_ID" --region "$REGION"

# Disable and delete the online evaluation config (id in results/online_eval_config.json)
aws bedrock-agentcore-control update-online-evaluation-config \
    --online-evaluation-config-id <config-id> --execution-status DISABLED --region "$REGION"
aws bedrock-agentcore-control delete-online-evaluation-config \
    --online-evaluation-config-id <config-id> --region "$REGION"
```

## Additional resources

- [Supported agent frameworks — OpenAI Agents](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-openai-agents.html)
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [GPT-5.5 model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-55.html)
- [Amazon Bedrock API keys](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html)
- [Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
