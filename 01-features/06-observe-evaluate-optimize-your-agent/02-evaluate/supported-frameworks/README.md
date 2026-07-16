# Evaluate agents across supported frameworks

Amazon Bedrock AgentCore Evaluations works with agents built on a range of supported agent frameworks. This folder provides runnable examples for OpenAI Agents SDK and LlamaIndex, showing how the same evaluation flow applies regardless of how the agent is built.

Each sample deploys the same HR Assistant, the agent used across the sibling `02-evaluate/` samples, re-implemented in its framework. It then evaluates the agent with built-in and custom LLM-as-a-judge evaluators in on-demand and online modes. Because every sample uses the same 5 tools, mock data, system prompt, and ground-truth turns, results are directly comparable across frameworks.

## Samples

| Framework         | Instrumentation (OpenTelemetry)               | LLM                                          | Sample                             |
| :---------------- | :-------------------------------------------- | :------------------------------------------- | :--------------------------------- |
| OpenAI Agents SDK | `opentelemetry-instrumentation-openai-agents` | OpenAI GPT-5.5 on Bedrock (`openai.gpt-5.5`) | [`openai-agents/`](openai-agents/) |
| LlamaIndex        | `opentelemetry-instrumentation-llamaindex`    | Amazon Bedrock (`us.amazon.nova-lite-v1:0`)  | [`llamaindex/`](llamaindex/)       |

These samples use OpenTelemetry instrumentation. AgentCore Evaluations also supports OpenInference for framework and instrumentation-library pairs listed in [Supported agent frameworks](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks.html). On AgentCore Runtime, AWS Distro for OpenTelemetry (ADOT) discovers the installed instrumentation library at startup, so no explicit instrumentation code is needed in the agent.

The examples in this folder are not the boundary of evaluation support. AgentCore Evaluations uses each span's `scope.name` and framework-specific attributes to classify agent, model, and tool operations. Any framework and instrumentation-library pair in the supported matrix can use the same evaluation APIs when it emits the documented OpenTelemetry or OpenInference schema, including correlated event records when required. A custom scope is not automatically supported solely because its data is transported with OTLP.

## The shared HR Assistant scenario

Every sample re-implements the same agent: an HR assistant with 5 tools that return deterministic mock data (PTO balances, HR policies, benefits, pay stubs). Reusing one agent domain keeps the focus on the framework integration rather than the agent itself. Because the data is deterministic, the same evaluation ground truth (`expected_response`, `expected_trajectory`, `assertions`) is valid for every framework, so evaluation scores reflect the framework's behavior rather than differences in the agent's task.

## Making a supported framework agent evaluable

The recipe these samples follow generalizes to every supported framework:

1. Add the instrumentation package for your framework to the deployment dependencies. The evaluation service identifies spans by their `scope.name`, so the package and its declared framework dependency must be importable at runtime. ADOT silently skips an instrumentor whose dependency check fails.
2. Structure the agent so its telemetry is recoverable. Each framework page in the [developer guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks.html) lists best practices. For example, LlamaIndex agents must be workflow agents (`FunctionAgent` or `ReActAgent`), and OpenAI Agents must keep SDK tracing enabled because the instrumentation hooks into it.
3. Flush telemetry before returning. AgentCore Runtime suspends the microVM between invocations; call `force_flush()` on the tracer and logger providers at the end of each invocation so buffered spans and event records (which carry the response text evaluators score) are not lost.
4. Verify the spans, then evaluate. After invoking the agent, confirm records with your framework's scope name appear in CloudWatch (`aws/spans` and the runtime log group). If `Evaluate` returns "no spans with supported scope", the instrumentation is not active. Evaluation cannot fix missing telemetry.

Steps 1 through 3 are framework-specific. Everything from step 4 onward, including evaluators, `EvaluationClient`, online configs, and the CLI, is identical for every framework. Compare the two `evaluate.py` files to see that they differ only in names.

## Structure

Each sample is self-contained and runs from its own folder:

```
supported-frameworks/
  openai-agents/
    openai_hr_assistant.py    # agent (entrypoint)
    deploy.py                 # deploys to AgentCore Runtime, writes agent_config.json
    evaluate.py               # runs on-demand + online evaluation
    cleanup.py                # deletes resources created by deploy.py and evaluate.py
    requirements.txt          # evaluation-time dependencies
    README.md
  llamaindex/
    llamaindex_hr_assistant.py
    deploy.py
    evaluate.py
    cleanup.py
    requirements.txt
    README.md
```

Run each with:

```bash
cd <framework>
uv run --frozen --with-requirements requirements.txt python deploy.py --region us-west-2
uv run --frozen --with-requirements requirements.txt python evaluate.py --region us-west-2
uv run --frozen --with-requirements requirements.txt python cleanup.py
```

See each sample's README for framework-specific setup (model access, endpoints, and ARM64 packaging notes). Each sample also shows how to re-evaluate recorded sessions from the terminal with the [AgentCore CLI](https://www.npmjs.com/package/@aws/agentcore) (`agentcore run eval --runtime-arn ... --evaluator-arn ...`).

## Next steps

- Explore [`../ground-truth-based-evaluation/`](../ground-truth-based-evaluation/) for the `OnDemandEvaluationDatasetRunner` and `BatchEvaluationRunner` interfaces. They work unchanged against the runtimes deployed here because the evaluation flow is framework-agnostic.
- Explore [`../custom-code-based-evaluation/`](../custom-code-based-evaluation/) for deterministic Lambda-backed evaluators.
- Add trajectory evaluators (`Builtin.TrajectoryExactOrderMatch`, `InOrderMatch`, `AnyOrderMatch`) using the `expected_trajectory` already defined in each `evaluate.py`.

## Additional resources

- [Supported agent frameworks](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks.html)
- [Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [Build reliable AI agents with Amazon Bedrock AgentCore Evaluations](https://aws.amazon.com/blogs/machine-learning/build-reliable-ai-agents-with-amazon-bedrock-agentcore-evaluations/)
