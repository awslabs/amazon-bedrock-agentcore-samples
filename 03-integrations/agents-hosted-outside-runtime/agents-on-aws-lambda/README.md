# Agents on AWS Lambda — AgentCore Observability

This folder contains two complementary patterns for running agents in AWS Lambda with
AgentCore observability.

## Patterns at a glance

| Pattern | Folder | Agent runs in |
|:--------|:-------|:--------------|
| Agent wrapped in Lambda | [`02-agent-in-lambda/`](./02-agent-in-lambda/) | Lambda execution environment |
| Lambda invokes AgentCore runtime | [`01-lambda-invokes-runtime/`](./01-lambda-invokes-runtime/) | AgentCore runtime (container) |

---

### Pattern 1 — Agent wrapped in Lambda

The Strands agent runs **entirely inside Lambda**. ADOT is bundled via pip
(`aws-opentelemetry-distro`) and X-Ray active tracing is enabled in the console.
Gen AI spans flow to CloudWatch Application Signals automatically.

Best for: lightweight agents, event-driven workloads, low-latency response requirements.

→ [02-agent-in-lambda/README.md](./02-agent-in-lambda/README.md)

---

### Pattern 2 — Lambda invokes AgentCore runtime

Lambda acts as an **orchestration layer** that calls an agent hosted on an AgentCore runtime.
Because Lambda's execution environment suppresses outgoing OTel spans by default, the ADOT
Lambda Layer and W3C trace context propagation are required to stitch Lambda and runtime spans
into a single connected trace.

Best for: long-running agents, agents that need persistent state, agents already deployed as
AgentCore runtimes.

→ [01-lambda-invokes-runtime/README.md](./01-lambda-invokes-runtime/README.md)
