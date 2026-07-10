# Evaluate a LlamaIndex agent

Evaluate a [LlamaIndex](https://docs.llamaindex.ai/) agent with Amazon Bedrock AgentCore Evaluations. This sample deploys the shared **HR Assistant** — re-implemented as a LlamaIndex `FunctionAgent` workflow — to AgentCore Runtime, then scores it with built-in and custom LLM-as-a-judge evaluators, both on-demand and online.

The HR Assistant, its 5 tools, mock data, and system prompt are identical to the Strands version in [`../../utils/`](../../utils/), so ground-truth and expected responses stay consistent across the framework samples.

## How it works

The agent is instrumented for evaluation with the **OpenTelemetry** LlamaIndex library (`opentelemetry-instrumentation-llamaindex`, scope `opentelemetry.instrumentation.llamaindex`). On AgentCore Runtime, AWS Distro for OpenTelemetry (ADOT) auto-discovers the library at startup — no explicit instrumentation code is needed. The agent's spans and event records flow to CloudWatch, and AgentCore Evaluations reads them from there.

The agent is built as a LlamaIndex **agent workflow** using `FunctionAgent`, following the [AgentCore best practices for LlamaIndex agents](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-llamaindex.html):

```python
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.core.tools import FunctionTool
from bedrock_agentcore.memory import MemoryClient
from llama_index.core.base.llms.types import ChatMessage
from llama_index.llms.bedrock_converse import BedrockConverse

tools = [FunctionTool.from_defaults(fn=get_pto_balance), ...]
agent = FunctionAgent(
    tools=tools,
    llm=BedrockConverse(model="us.amazon.nova-lite-v1:0", region_name=REGION),
    system_prompt=SYSTEM_PROMPT,
    streaming=False,
)

# Conversation history persisted in AgentCore Memory, replayed as chat_history
memory_client = MemoryClient(region_name=REGION)
history = _load_chat_history(session_id)          # [ChatMessage] from list_events
response = await agent.run(prompt, chat_history=history)
memory_client.create_event(                        # persist the new turn
    memory_id=MEMORY_ID, actor_id=ACTOR_ID, session_id=session_id,
    messages=[(prompt, "USER"), (str(response), "ASSISTANT")],
)
```

- **Agent workflow** — `FunctionAgent` emits a top-level workflow span with inference and tool child spans, which is the structure AgentCore Evaluations reconstructs a session from.
- **FunctionTool** — each tool is registered as a `FunctionTool` so tool spans carry recoverable names, arguments, and results.
- **Text-serializable results** — the tools return JSON-serializable dicts, which LlamaIndex wraps in a text block for clean capture.
- **`streaming=False`** — one complete inference span per model call is what the evaluation service reads. It also avoids a `BedrockConverse` streaming parser issue (`TypeError` on split tool-call input deltas).
- **AgentCore Memory for conversation history** — each turn is stored in the [AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html) service via `bedrock_agentcore.memory.MemoryClient` and replayed as `chat_history`, so multi-turn context survives microVM restarts. `deploy.py` creates the memory resource and injects `AGENTCORE_MEMORY_ID`. Only USER/ASSISTANT text turns are stored: replaying stored tool-call messages (as the official `llama-index-memory-bedrock-agentcore` integration does) trips the Bedrock Converse API's toolUse/toolResult pairing validation on the next turn.

`FunctionAgent` is used (not `ReActAgent`) because Nova Lite supports native tool calling. If you swap in a model without tool calling, `ReActAgent` is the alternative; AgentCore then extracts the final answer from the standard `Answer:` section of its output.

The LLM is a Bedrock model (Nova Lite via `BedrockConverse`), matching the shared Strands agent so expected responses stay identical.

## Prerequisites

- Python 3.10+
- AWS CLI configured with credentials
- Access to `us.amazon.nova-lite-v1:0` on Amazon Bedrock in your region
- Permissions for: `bedrock-agentcore:*`, `bedrock-agentcore-control:*`, `logs:*`, `iam:CreateRole`, `iam:PutRolePolicy`, `s3:PutObject`, `bedrock:InvokeModel`

## Deploy the agent

```bash
pip install boto3
python deploy.py --region us-west-2
```

This builds an ARM64 deployment package, creates an AgentCore Memory resource (conversation history store, injected as `AGENTCORE_MEMORY_ID`), creates the AgentCore Runtime, and writes `agent_config.json` in this directory (read by `evaluate.py`).

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

`deploy.py` cross-compiles dependencies with `--platform manylinux2014_aarch64 --only-binary=:all:`. LlamaIndex pulls a broad dependency tree; if a transitive dependency lacks an aarch64 wheel and the install fails, either:

- add `--no-binary=<package>` for the offending pure-Python package, or
- build the zip on an ARM64 machine or in a `public.ecr.aws/lambda/python:3.13-arm64` container / AWS CodeBuild ARM instead of cross-compiling.

The sample installs the full `llama-index` meta-package (not just `llama-index-core`). This is required: ADOT's auto-instrumentation checks the OpenTelemetry LlamaIndex instrumentation's declared dependency (`llama-index`) at startup and silently skips the instrumentor if only `llama-index-core` is present — the agent then emits no evaluable spans.

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

- [Supported agent frameworks — LlamaIndex](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-llamaindex.html)
- [LlamaIndex documentation](https://docs.llamaindex.ai/)
- [Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
