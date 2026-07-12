# Evaluate agents across supported frameworks

Amazon Bedrock AgentCore Evaluations works with agents built on a range of agent frameworks, not just Strands. This folder shows one evaluation code sample per newly-supported framework, so you can see how the same evaluation flow applies regardless of how the agent is built.

Each sample deploys the same **HR Assistant** — the agent used across the sibling `02-evaluate/` samples — re-implemented in its framework, then evaluates it with built-in and custom LLM-as-a-judge evaluators (on-demand and online). Because every sample uses the same 5 tools, mock data, system prompt, and ground-truth turns, results are directly comparable across frameworks.

## Samples

| Framework         | Instrumentation (OpenTelemetry)               | LLM                                          | Sample                             |
| :---------------- | :-------------------------------------------- | :------------------------------------------- | :--------------------------------- |
| OpenAI Agents SDK | `opentelemetry-instrumentation-openai-agents` | OpenAI GPT-5.5 on Bedrock (`openai.gpt-5.5`) | [`openai-agents/`](openai-agents/) |
| LlamaIndex        | `opentelemetry-instrumentation-llamaindex`    | Amazon Bedrock (`us.amazon.nova-lite-v1:0`)  | [`llamaindex/`](llamaindex/)       |

All samples use **OpenTelemetry** instrumentation. On AgentCore Runtime, AWS Distro for OpenTelemetry (ADOT) auto-discovers the instrumentation library at startup from the deployment dependencies — no explicit instrumentation code is needed in the agent. See [Supported agent frameworks](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks.html) for the full framework and library matrix (OpenInference is also supported as an alternative for these frameworks).

## The shared HR Assistant scenario

Every sample re-implements the same agent: an HR assistant with 5 tools that return deterministic mock data (PTO balances, HR policies, benefits, pay stubs). Reusing one agent domain keeps the focus on the framework integration rather than the agent itself, and because the data is deterministic, the same evaluation ground truth (`expected_response`, `expected_trajectory`, `assertions`) is valid for every framework — evaluation scores reflect the framework's behavior rather than differences in the agent's task.

## Making any framework agent evaluable

The recipe these samples follow generalizes to every supported framework:

1. **Add the instrumentation package** for your framework to the deployment dependencies. The evaluation service identifies spans by their `scope.name`, so the package (and its declared framework dependency) must be importable at runtime — ADOT silently skips an instrumentor whose dependency check fails.
2. **Structure the agent so its telemetry is recoverable.** Each framework page in the [developer guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks.html) lists best practices — for example, LlamaIndex agents must be workflow agents (`FunctionAgent`/`ReActAgent`), and OpenAI Agents must keep SDK tracing enabled because the instrumentation hooks into it.
3. **Flush telemetry before returning.** AgentCore Runtime suspends the microVM between invocations; call `force_flush()` on the tracer and logger providers at the end of each invocation so buffered spans and event records (which carry the response text evaluators score) are not lost.
4. **Verify the spans, then evaluate.** After invoking the agent, confirm records with your framework's scope name appear in CloudWatch (`aws/spans` and the runtime log group). If `Evaluate` returns "no spans with supported scope", the instrumentation is not active — evaluation cannot fix missing telemetry.

Steps 1–3 are framework-specific; everything from step 4 on (evaluators, `EvaluationClient`, online configs, the CLI) is identical for every framework — compare the two `evaluate.py` files to see they differ only in names.

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

See each sample's README for framework-specific setup (model access, endpoints, and ARM64 packaging notes). Each sample also shows how to re-evaluate recorded sessions from the terminal with the [AgentCore CLI](https://www.npmjs.com/package/@aws/agentcore) (`agentcore run eval --runtime-arn ... --evaluator-arn ...`).

## Next steps

- Explore [`../ground-truth-based-evaluation/`](../ground-truth-based-evaluation/) for the `OnDemandEvaluationDatasetRunner` and `BatchEvaluationRunner` interfaces — they work unchanged against the runtimes deployed here, because the evaluation flow is framework-agnostic.
- Explore [`../custom-code-based-evaluation/`](../custom-code-based-evaluation/) for deterministic Lambda-backed evaluators.
- Add trajectory evaluators (`Builtin.TrajectoryExactOrderMatch`, `InOrderMatch`, `AnyOrderMatch`) using the `expected_trajectory` already defined in each `evaluate.py`.

## Additional resources

- [Supported agent frameworks](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks.html)
- [Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [Build reliable AI agents with Amazon Bedrock AgentCore Evaluations](https://aws.amazon.com/blogs/machine-learning/build-reliable-ai-agents-with-amazon-bedrock-agentcore-evaluations/)
