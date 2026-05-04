# Advanced patterns

Composite use cases that build on top of the memory primitives covered in [`../01-short-term-memory/01-core-features/`](../01-short-term-memory/01-core-features/) and [`../02-long-term-memory/01-core-features/`](../02-long-term-memory/01-core-features/).

| Folder | Pattern | Starts from |
|---|---|---|
| [`01-runtime-integration/`](./01-runtime-integration/) | Memory + AgentCore Runtime | Any framework example |
| [`02-identity-integration/`](./02-identity-integration/) | Memory + AgentCore Identity + Runtime | Runtime integration |
| [`03-guardrails-integration/`](./03-guardrails-integration/) | Memory + Bedrock Guardrails | Any long-term memory example |
| [`04-memory-browser/`](./04-memory-browser/) | Web UI for inspecting memory resources | — |
| [`05-streaming-use-cases/`](./05-streaming-use-cases/) | Cross-region replication, personalisation, cross-customer analytics — all built on the streaming primitive | [LTM 01-core-features/09-record-streaming](../02-long-term-memory/01-core-features/09-record-streaming.ipynb) |
| [`06-observability.ipynb`](./06-observability.ipynb) | CloudWatch metrics and logs for stream health and extraction pipelines | — |

For the **streaming primitive itself** (enabling streaming, `METADATA_ONLY` vs `FULL_CONTENT` modes, consuming from Kinesis), see [LTM 01-core-features/09-record-streaming.ipynb](../02-long-term-memory/01-core-features/09-record-streaming.ipynb). That notebook is the prerequisite for everything in `05-streaming-use-cases/`.
