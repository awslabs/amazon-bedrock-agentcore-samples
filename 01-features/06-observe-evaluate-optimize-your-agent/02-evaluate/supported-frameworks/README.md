# Evaluate agents across supported frameworks

Amazon Bedrock AgentCore Evaluations works with agents built on a range of agent frameworks, not just Strands. This folder shows one evaluation code sample per newly-supported framework, so you can see how the same evaluation flow applies regardless of how the agent is built.

Each sample deploys the same **HR Assistant** — the agent used across the sibling `02-evaluate/` samples — re-implemented in its framework, then evaluates it with built-in and custom LLM-as-a-judge evaluators (on-demand and online). Because every sample uses the same 5 tools, mock data, system prompt, and ground-truth turns, results are directly comparable across frameworks.

## Samples

| Framework         | Instrumentation (OpenTelemetry)               | LLM                                           | Sample                             |
| :---------------- | :-------------------------------------------- | :-------------------------------------------- | :--------------------------------- |
| OpenAI Agents SDK | `opentelemetry-instrumentation-openai-agents` | Bedrock-native OpenAI (`openai.gpt-oss-120b`) | [`openai-agents/`](openai-agents/) |
| LlamaIndex        | `opentelemetry-instrumentation-llamaindex`    | Amazon Bedrock (`us.amazon.nova-lite-v1:0`)   | [`llamaindex/`](llamaindex/)       |

All samples use **OpenTelemetry** instrumentation. On AgentCore Runtime, AWS Distro for OpenTelemetry (ADOT) auto-discovers the instrumentation library at startup from the deployment dependencies — no explicit instrumentation code is needed in the agent. See [Supported agent frameworks](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks.html) for the full framework and library matrix (OpenInference is also supported as an alternative for these frameworks).

## Why the same HR Assistant?

Reusing one agent domain keeps the focus on the framework integration rather than the agent itself. The tools return deterministic mock data (PTO balances, HR policies, benefits, pay stubs), so the same evaluation ground truth (`expected_response`, `expected_trajectory`, `assertions`) is valid for every framework, and evaluation scores reflect the framework's behavior rather than differences in the agent's task.

## Structure

Each sample is self-contained and runs from its own folder:

```
supported-frameworks/
  openai-agents/
    openai_hr_assistant.py    # agent (entrypoint)
    deploy.py                 # deploys to AgentCore Runtime, writes agent_config.json
    evaluate.py               # runs on-demand + online evaluation
    requirements.txt          # evaluation-time dependencies
    README.md
  llamaindex/
    llamaindex_hr_assistant.py
    deploy.py
    evaluate.py
    requirements.txt
    README.md
```

Run each with:

```bash
cd <framework>
pip install boto3
python deploy.py --region us-west-2      # deploy the agent
pip install -r requirements.txt
python evaluate.py --region us-west-2     # evaluate it
```

See each sample's README for framework-specific setup (model access, endpoints, and ARM64 packaging notes).

## Additional resources

- [Supported agent frameworks](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks.html)
- [Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [Build reliable AI agents with Amazon Bedrock AgentCore Evaluations](https://aws.amazon.com/blogs/machine-learning/build-reliable-ai-agents-with-amazon-bedrock-agentcore-evaluations/)
