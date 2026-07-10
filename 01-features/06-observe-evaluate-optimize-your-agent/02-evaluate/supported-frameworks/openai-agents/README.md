# Evaluate an OpenAI Agents SDK agent

Evaluate an [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) agent with Amazon Bedrock AgentCore Evaluations. This sample deploys the shared **HR Assistant** — re-implemented with the OpenAI Agents SDK — to AgentCore Runtime, then scores it with built-in and custom LLM-as-a-judge evaluators, both on-demand and online.

The HR Assistant, its 5 tools, mock data, and system prompt are identical to the Strands version in [`../../utils/`](../../utils/), so ground-truth and expected responses stay consistent across the framework samples.

## How it works

The agent is instrumented for evaluation with the **OpenTelemetry** OpenAI Agents library (`opentelemetry-instrumentation-openai-agents`, scope `opentelemetry.instrumentation.openai_agents`). On AgentCore Runtime, AWS Distro for OpenTelemetry (ADOT) auto-discovers the library at startup — no explicit instrumentation code is needed. The agent's spans and event records flow to CloudWatch, and AgentCore Evaluations reads them from there.

The LLM is a **Bedrock-native OpenAI model** (`openai.gpt-oss-120b`) reached through the Bedrock mantle endpoint's OpenAI-compatible **Responses API**. The OpenAI Agents SDK talks to it via an `AsyncOpenAI` client:

```python
from agents import Agent, OpenAIResponsesModel
from openai import AsyncOpenAI
from aws_bedrock_token_generator import provide_token

token = provide_token(region=REGION)  # short-term Bedrock bearer token from the runtime's IAM role
client = AsyncOpenAI(base_url=f"https://bedrock-mantle.{REGION}.api.aws/v1", api_key=token)
model = OpenAIResponsesModel(model="openai.gpt-oss-120b", openai_client=client)

agent = Agent(name="HRAssistant", instructions=SYSTEM_PROMPT, model=model, tools=[...])
```

Three implementation details matter for evaluation:

- **Responses API, not Chat Completions.** The OpenTelemetry instrumentation extracts the agent's response text from Responses API spans (`ResponseSpanData`); with `OpenAIChatCompletionsModel` the response text is not captured on the spans and evaluators score empty responses. On Bedrock, the Responses API is served by the mantle endpoint (`https://bedrock-mantle.<region>.api.aws/v1`) with the model id `openai.gpt-oss-120b`.
- **Keep SDK tracing enabled.** The instrumentation hooks into the SDK's tracing pipeline, so do not call `set_tracing_disabled(True)` — that would silence the evaluation spans. The SDK's default platform.openai.com exporter is inert without an `OPENAI_API_KEY` and only logs a skip message.
- **AgentCore Memory for conversation history, not `SQLiteSession`.** The SDK's session classes are local to one microVM (history is lost across restarts) and replay full Responses API output items (including gpt-oss `reasoning` items) as the next turn's input, which the mantle endpoint rejects with an empty output. Instead, `deploy.py` creates an [AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html) resource and the agent persists each turn as a memory event (via `bedrock_agentcore.memory.MemoryClient`), reloading the plain `{"role", "content"}` history at the start of every invocation.

No API key is stored in code: `aws-bedrock-token-generator` mints a short-term bearer token from the runtime's IAM role credentials (a local SigV4 presign, no network call). The agent is rebuilt on every invocation so a long-lived runtime never reuses an expired token.

## Prerequisites

- Python 3.10+
- AWS CLI configured with credentials
- Access to `openai.gpt-oss-120b` on Amazon Bedrock in your region. gpt-oss is available in `us-west-2` and `us-east-1` among others — use one of those. Set `--region` accordingly.
- Permissions for: `bedrock-agentcore:*`, `bedrock-agentcore-control:*`, `logs:*`, `iam:CreateRole`, `iam:PutRolePolicy`, `s3:PutObject`, `bedrock:InvokeModel`

## Deploy the agent

```bash
pip install boto3
python deploy.py --region us-west-2
```

This builds an ARM64 deployment package, creates an AgentCore Memory resource (conversation history store, injected as `AGENTCORE_MEMORY_ID`), creates the AgentCore Runtime, and writes `agent_config.json` in this directory (read by `evaluate.py`).

The runtime's IAM role is granted `bedrock-mantle:CreateInference` and `bedrock-mantle:CallWithBearerToken` for the mantle Responses API, plus `bedrock:InvokeModel*` and `bedrock:CallWithBearerToken` (the latter pair covers the `bedrock-runtime/openai/v1` Chat Completions endpoint, should you switch `BEDROCK_OPENAI_BASE_URL` to it). The bearer-token actions are required because the OpenAI-compatible endpoints authenticate with a bearer token rather than SigV4.

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
- [Inference using Chat Completions API on Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-chat-completions-mantle.html)
- [Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
