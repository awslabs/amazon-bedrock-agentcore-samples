# Getting started with AgentCore Memory

Start here if you are new to AgentCore Memory. This folder teaches the vocabulary, helps you pick an access surface (CLI, boto3, or AgentCore SDK), then walks the same end-to-end flow three ways so you can follow it with whichever surface you prefer.

| Step | File | What you learn |
|---|---|---|
| 1 | [01-memory-concepts.md](./01-memory-concepts.md) | Actor, session, event, strategy, namespace, memory record |
| 2 | [02-choosing-your-surface.md](./02-choosing-your-surface.md) | When to use the CLI vs boto3 vs the AgentCore SDK |
| 3a | [03-quickstart-cli.md](./03-quickstart-cli.md) | End-to-end flow with the AWS CLI |
| 3b | [04-quickstart-boto3.ipynb](./04-quickstart-boto3.ipynb) | Same flow with raw `boto3` clients |
| 3c | [05-quickstart-agentcore-sdk.ipynb](./05-quickstart-agentcore-sdk.ipynb) | Same flow with the `MemoryClient` from the AgentCore SDK |

All three quickstarts build the same resource, write the same event, add the same built-in strategy, and retrieve the same record — so you can switch surfaces without relearning the model.

## Where to go next

Once you have the concepts and a working quickstart:

- **Short-term memory primitives** → [`../01-short-term-memory/01-core-features/`](../01-short-term-memory/01-core-features/)
- **Long-term memory primitives** → [`../02-long-term-memory/01-core-features/`](../02-long-term-memory/01-core-features/)
- **Framework integrations (Strands, LangGraph, LlamaIndex)** → the `02-single-agent/` and `03-multi-agent/` folders under each memory type
- **Advanced integrations (Runtime, Identity, Guardrails, Browser, streaming use cases)** → [`../03-advanced-patterns/`](../03-advanced-patterns/)
- **Security patterns (IAM, Cognito, KMS)** → [`../04-security-patterns/`](../04-security-patterns/)
