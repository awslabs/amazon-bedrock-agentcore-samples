# Amazon Bedrock AgentCore Memory

Managed memory for AI agents: short-term conversation context, long-term extracted records, branching, streaming, and framework integrations.

## Start here

New to AgentCore Memory? → [`00-getting-started/`](./00-getting-started/). You'll get the vocabulary, pick a surface (CLI / boto3 / AgentCore SDK), and walk the same end-to-end flow through whichever one fits.

## Top-level layout

| Folder | What's inside |
|---|---|
| [`00-getting-started/`](./00-getting-started/) | Concepts, surface decision guide, and three quickstarts (CLI, boto3, AgentCore SDK) |
| [`01-short-term-memory/`](./01-short-term-memory/) | Events, sessions, branching — plus Strands / LangGraph / LlamaIndex single- and multi-agent examples |
| [`02-long-term-memory/`](./02-long-term-memory/) | Strategies (semantic, summary, user-preference, episodic, overrides, self-managed), namespaces, retrieval, batch APIs, redrive, streaming — plus framework examples across the three integration patterns |
| [`03-advanced-patterns/`](./03-advanced-patterns/) | Runtime integration, identity integration, guardrails, memory browser, streaming use cases, observability |
| [`04-security-patterns/`](./04-security-patterns/) | IAM scoping, Cognito federation, KMS encryption |

## How this tree is organized

Two axes:

1. **Memory type** → short-term vs long-term. Pick once based on what you're storing.
2. **Inside each memory type**:
   - `01-core-features/` — framework-agnostic walkthroughs of the underlying primitives
   - `02-single-agent/` and `03-multi-agent/` — framework integrations (Strands, LangGraph, LlamaIndex), each offering three patterns: built-in hook, custom hook, and memory-as-tool

A third concern — access surface (CLI / boto3 / AgentCore SDK) — is orthogonal. Surfaces are interchangeable; the choice is made per notebook based on what's clearest, not by folder. The getting-started section shows the same flow in all three. Elsewhere, primitive/ops tutorials default to boto3 and agent tutorials default to the AgentCore SDK.

## The three integration patterns

| Pattern | What it is | When to use |
|---|---|---|
| **Built-in hook / callback / memory block** | The framework's out-of-the-box AgentCore adapter | Fastest path; standard save/retrieve lifecycle |
| **Custom hook / callback / memory block** | You implement your own | Conditional logic, custom retrieval, multi-strategy orchestration |
| **Memory-as-tool** | Memory ops exposed as tools the LLM calls | Agent decides when to recall/save |

## Finding things

- **Primitives by API** (`CreateEvent`, `RetrieveMemoryRecords`, branching, streaming, batch) → core-features folders.
- **By framework** (Strands, LangGraph, LlamaIndex) → `with-<framework>-agent/` under each memory type.
- **By pattern** (built-in / custom / tool) → one level deeper inside the framework folder.
- **By integration** (Runtime, Identity, Guardrails, Browser, streaming use cases) → `03-advanced-patterns/`.
- **By policy concern** (IAM, Cognito, KMS) → `04-security-patterns/`.

## Resources

- [AgentCore Memory documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html)
- [Deep-dive video](https://www.youtube.com/live/-N4v6-kJgwA)

## Prerequisites

- Python 3.10 or higher
- AWS account with Amazon Bedrock and AgentCore access
- Jupyter for the notebook-based tutorials
- Per-tutorial `requirements.txt` where present
