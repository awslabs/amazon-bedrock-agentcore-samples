# Automation Agents

Async agents triggered by tickets, emails, webhooks, and system events. Automate complex workflows with confidence scoring and human-in-the-loop (HITL) escalation.

Unlike conversational agents that serve end-users in real-time, automation agents operate in the background — processing events, coordinating specialized sub-agents, enforcing fine-grained policies, and producing auditable outputs. AgentCore provides the managed runtime for long-running async tasks, service-to-service identity, and the observability to track throughput and accuracy across high-volume pipelines.

---

## What makes an Automation Agent

| Dimension | Automation Agent Configuration |
|-----------|--------------------------------|
| **Identity** | Service identity (not user identity) — agent authenticates as itself to downstream systems |
| **Memory** | Minimal / stateless by default — state lives in the event payload or external store |
| **Runtime** | Longer timeouts acceptable — async processing, no streaming requirement |
| **Guardrails** | Confidence thresholds for auto-approve vs. escalate decisions |
| **Observability** | Throughput + accuracy metrics — track processing rates, failure rates, SLA compliance |
| **Gateway** | System-to-system API access (ticketing, ERP, payment processors) |

### Common Patterns

| Pattern | When to use |
|---------|-------------|
| **Workflow (DAG)** | Sequential or parallel steps with clear dependencies (e.g., claims: validate → enrich → route) |
| **Agents-as-Tools** | Specialized sub-agents invoked by an orchestrator for distinct tasks |
| **A2A (Agent-to-Agent)** | Agents on separate runtimes communicating via the A2A protocol |
| **Human-in-the-Loop** | Confidence below threshold triggers escalation to a human reviewer |

---

## Samples

| Sample | Vertical | Complexity | Key AgentCore Features |
|--------|----------|------------|------------------------|
| [event-driven-claims-agent](./event-driven-claims-agent/) | Insurance | Advanced | Runtime, Gateway, Memory, Policy, Evaluations, Observability — S3→EventBridge→Lambda→Runtime |
| [visa-b2b-account-payable-agent](./visa-b2b-account-payable-agent/) | B2B Payments | Advanced | Runtime, Gateway, Policy, Payments — automated invoice matching + ISO 20022 payment generation |
| [enterprise-web-intelligence-agent](./enterprise-web-intelligence-agent/) | Market Intelligence | Intermediate | Runtime, Browser — automated web scraping pipeline, dual-framework (LangGraph vs. Strands) |
| [intelligent-event-agent](./intelligent-event-agent/) | General / Events | Beginner | Runtime, Memory, Gateway — *(in development, no README yet)* |

---

## Choosing a Sample

- **Event-driven architecture (S3, EventBridge, SQS)?** Start with [event-driven-claims-agent](./event-driven-claims-agent/) — the most complete sample with all AgentCore services, CDK, and a working demo video.
- **Real-world payment API integration?** See [visa-b2b-account-payable-agent](./visa-b2b-account-payable-agent/) — Visa B2B Connect, multi-agent accounts payable.
- **Automated web intelligence / scraping pipeline?** See [enterprise-web-intelligence-agent](./enterprise-web-intelligence-agent/) — also useful for comparing LangGraph vs. Strands architectures.

---

## Related Categories

- [01-conversational-agents](../01-conversational-agents/) — Customer-facing chat agents with memory, identity, and guardrails
- [03-coding-assistants](../03-coding-assistants/) — IDE and CI-driven agents for code generation and review
