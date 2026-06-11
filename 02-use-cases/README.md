# Amazon Bedrock AgentCore — Use Cases

End-to-end applications showing AgentCore capabilities applied to real business problems. Samples are organized by agent archetype — the same three workload types used across AgentCore documentation and go-to-market.

---

## Agent Archetypes

### [01-conversational-agents](./01-conversational-agents/) — 19 samples

> Customer-facing chat agents with memory, identity, and guardrails. Move from prototype to production with enterprise security built in.

These agents serve end-users in real-time interactive sessions. Identity is user-facing (OAuth 2.0 token exchange with Entra ID, Okta, or Cognito). Memory is session + long-term, namespaced per user. Runtime is configured for streaming and sessions up to 8 hours. Guardrails protect against prompt injection, PII leakage, and off-topic inputs.

| Sample | Vertical | Key Features |
|--------|----------|--------------|
| [A2A-multi-agent-incident-response](./01-conversational-agents/A2A-multi-agent-incident-response/) | IT / DevOps | Runtime, Gateway, Memory, A2A (3 frameworks) |
| [A2A-realestate-agentcore-multiagents](./01-conversational-agents/A2A-realestate-agentcore-multiagents/) | Real Estate | Runtime, Gateway, Policy, Identity (Cognito), A2A |
| [auth0-multi-agent-obo](./01-conversational-agents/auth0-multi-agent-obo/) | Financial Services | Runtime, Gateway, Memory, Identity (RFC 8693 OBO) |
| [AWS-operations-agent](./01-conversational-agents/AWS-operations-agent/) | Cloud Operations | Runtime, Gateway, Memory, Policy, Observability |
| [cost-optimization-agent](./01-conversational-agents/cost-optimization-agent/) | Cloud FinOps | Runtime, Memory, Policy |
| [customer-support-assistant](./01-conversational-agents/customer-support-assistant/) | Retail / E-commerce | Runtime, Gateway, Memory, Policy, Evaluations |
| [customer-support-assistant-vpc](./01-conversational-agents/customer-support-assistant-vpc/) | Retail / E-commerce | Runtime, Gateway (VPC private networking) |
| [DB-performance-analyzer](./01-conversational-agents/DB-performance-analyzer/) | Database / DevOps | Runtime, Gateway, Observability |
| [device-management-agent](./01-conversational-agents/device-management-agent/) | IoT / Smart Home | Runtime, Gateway, Policy, Identity (Cognito) |
| [farm-management-advisor](./01-conversational-agents/farm-management-advisor/) | Agriculture | Runtime, Gateway, Memory |
| [finance-personal-assistant](./01-conversational-agents/finance-personal-assistant/) | Personal Finance | Gateway, Policy |
| [healthcare-appointment-agent](./01-conversational-agents/healthcare-appointment-agent/) | Healthcare | Runtime, Gateway, Policy, Observability (FHIR R4) |
| [lakehouse-agent](./01-conversational-agents/lakehouse-agent/) | Data & Analytics | Runtime, Gateway, Memory, Policy (row-level security) |
| [local-prototype-to-agentcore](./01-conversational-agents/local-prototype-to-agentcore/) | Insurance / Tutorial | Runtime, Gateway, Identity |
| [market-trends-agent](./01-conversational-agents/market-trends-agent/) | Financial Services | Runtime, Memory, Browser, Evaluations, Optimization |
| [role-based-hr-data-agent](./01-conversational-agents/role-based-hr-data-agent/) | HR / Compliance | Runtime, Gateway, Policy (Cedar field-level DLP) |
| [slide-deck-generator-memory-agent](./01-conversational-agents/slide-deck-generator-memory-agent/) | Productivity | Runtime, Memory |
| [SRE-agent](./01-conversational-agents/SRE-agent/) | Site Reliability | Runtime, Gateway, Memory, Observability |
| [video-games-sales-assistant](./01-conversational-agents/video-games-sales-assistant/) | Retail / Gaming | Runtime, Gateway, Memory |

---

### [02-automation-agents](./02-automation-agents/) — 4 samples

> Async agents triggered by tickets, emails, webhooks, and system events. Automate workflows with confidence scoring and HITL escalation.

These agents run in the background. Identity is service-to-service. Memory is minimal or stateless — state lives in the event payload or an external store. Runtime is configured for longer timeouts without streaming. Guardrails focus on confidence thresholds that determine auto-approve vs. human escalation.

| Sample | Vertical | Key Features |
|--------|----------|--------------|
| [event-driven-claims-agent](./02-automation-agents/event-driven-claims-agent/) | Insurance | Runtime, Gateway, Memory, Policy, Evaluations, Observability |
| [visa-b2b-account-payable-agent](./02-automation-agents/visa-b2b-account-payable-agent/) | B2B Payments | Runtime, Gateway, Policy, Payments |
| [enterprise-web-intelligence-agent](./02-automation-agents/enterprise-web-intelligence-agent/) | Market Intelligence | Runtime, Browser |
| [intelligent-event-agent](./02-automation-agents/intelligent-event-agent/) | General / Events | Runtime, Memory, Gateway *(in development)* |

---

### [03-coding-assistants](./03-coding-assistants/) — 3 samples

> IDE and CI-driven agents for code generation, refactor, and review. Long-running tasks in a sandboxed Code Interpreter runtime.

These agents work at developer timescales — tasks run for minutes to hours, scoped to a project or repository. Identity is developer identity or a CI service account. Memory is project-scoped. AgentCore Code Interpreter provides isolated container execution. AgentCore Gateway consolidates developer tool APIs behind a single MCP endpoint.

| Sample | Use Case | Key Features |
|--------|----------|--------------|
| [text-to-python-ide](./03-coding-assistants/text-to-python-ide/) | Full-stack text-to-Python IDE | Runtime, Code Interpreter, Memory, Policy (Guardrails) |
| [claude-code-gateway-mcp-server](./03-coding-assistants/claude-code-gateway-mcp-server/) | Unified MCP endpoint for Claude Code | Gateway (MCP aggregation), Identity |
| [gateway-schema-support-agent](./03-coding-assistants/gateway-schema-support-agent/) | Auto-fix OpenAPI specs for Gateway | Gateway, Code tools |

---

## Sample Quality & Roadmap

See [use-case-assessment.md](./use-case-assessment.md) for a full evaluation of all 27 samples:
- Scores across tier, AgentCore feature coverage, documentation quality, and unique problem value
- Starter Toolkit migration status — 18/27 samples need migration to native `bedrock-agentcore` SDK
- Per-sample improvement TODO lists
- Priority action plan (immediate / short-term / medium-term)

---

## Related Resources

- [01-tutorials](../01-tutorials/) — Feature-focused tutorials and Jupyter notebooks
- [03-integrations](../03-integrations/) — Framework and protocol integrations
- [06-workshops](../06-workshops/) — Hands-on workshop labs
- [AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
