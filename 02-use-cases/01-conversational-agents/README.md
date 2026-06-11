# Conversational Agents

Customer-facing chat agents with memory, identity, and guardrails. Move from prototype to production with enterprise security built in.

AgentCore handles the undifferentiated heavy lifting — session management, user authentication against enterprise IdPs, long-term memory, content safety, and tool access — so you focus on the conversation logic.

---

## What makes a Conversational Agent

| Dimension | Conversational Agent Configuration |
|-----------|-------------------------------------|
| **Identity** | End-user OAuth token exchange (Entra ID, Okta, Cognito) — agent acts *on behalf of the user* |
| **Memory** | Session memory for multi-turn context + long-term memory for cross-session recall, namespaced per user |
| **Runtime** | Streaming enabled, session affinity, sessions up to 8 hours |
| **Guardrails** | Content filters, topic boundaries, PII redaction — protects against prompt injection and social engineering |
| **Observability** | Per-conversation tracing with user context — debugs "the agent gave me wrong info" |
| **Gateway** | User-scoped tool access with auth propagation — agent calls APIs as the authenticated user |

### Common Patterns

| Pattern | When to use |
|---------|-------------|
| **Single Agent + Tools** | Single domain, fewer than ~10 tools, straightforward flows |
| **Agents-as-Tools** | Multi-domain support, complex routing across specializations |
| **Graph (Intent Router)** | Structured flows with conditional branching |
| **Human-in-the-Loop** | Regulated industries (healthcare, finance), high-stakes decisions |

---

## Samples

| Sample | Vertical | Complexity | Key AgentCore Features |
|--------|----------|------------|------------------------|
| [A2A-multi-agent-incident-response](./A2A-multi-agent-incident-response/) | IT / DevOps | Advanced | Runtime, Gateway, Memory, A2A — three frameworks (Strands, OpenAI Agents, Google ADK) |
| [A2A-realestate-agentcore-multiagents](./A2A-realestate-agentcore-multiagents/) | Real Estate | Advanced | Runtime, Gateway, Policy, Identity (Cognito), A2A — coordinator + search + booking sub-agents |
| [auth0-multi-agent-obo](./auth0-multi-agent-obo/) | Financial Services | Advanced | Runtime, Gateway, Memory, Identity (RFC 8693 OBO — attenuated tokens per sub-agent) |
| [AWS-operations-agent](./AWS-operations-agent/) | Cloud Operations | Advanced | Runtime, Gateway, Memory, Policy, Observability (multi-framework: Strands + ADK + OpenAI) |
| [cost-optimization-agent](./cost-optimization-agent/) | Cloud FinOps | Beginner | Runtime, Memory, Policy — natural language AWS cost Q&A |
| [customer-support-assistant](./customer-support-assistant/) | Retail / E-commerce | Intermediate | Runtime, Gateway, Memory, Policy, Evaluations |
| [customer-support-assistant-vpc](./customer-support-assistant-vpc/) | Retail / E-commerce | Intermediate | Runtime, Gateway — VPC private networking pattern |
| [DB-performance-analyzer](./DB-performance-analyzer/) | Database / DevOps | Intermediate | Runtime, Gateway, Observability — natural language PostgreSQL analysis |
| [device-management-agent](./device-management-agent/) | IoT / Smart Home | Intermediate | Runtime, Gateway, Policy, Identity (Cognito) |
| [farm-management-advisor](./farm-management-advisor/) | Agriculture | Intermediate | Runtime, Gateway, Memory — plant health analysis with image input |
| [finance-personal-assistant](./finance-personal-assistant/) | Personal Finance | Beginner | Gateway, Policy — workshop notebooks |
| [healthcare-appointment-agent](./healthcare-appointment-agent/) | Healthcare | Intermediate | Runtime, Gateway, Policy, Observability — FHIR R4 / HealthLake |
| [lakehouse-agent](./lakehouse-agent/) | Data & Analytics | Advanced | Runtime, Gateway, Memory, Policy — OAuth row-level security over S3 Tables + Athena |
| [local-prototype-to-agentcore](./local-prototype-to-agentcore/) | Insurance / Tutorial | Intermediate | Runtime, Gateway, Identity — step-by-step local-to-production migration guide |
| [market-trends-agent](./market-trends-agent/) | Financial Services | Advanced | Runtime, Memory, Browser, Evaluations, Optimization — personalized broker investment assistant |
| [role-based-hr-data-agent](./role-based-hr-data-agent/) | HR / Compliance | Advanced | Runtime, Gateway, Policy (Cedar field-level DLP) — role-scoped HR data access |
| [slide-deck-generator-memory-agent](./slide-deck-generator-memory-agent/) | Productivity | Beginner | Runtime, Memory — side-by-side basic vs. enhanced Memory comparison |
| [SRE-agent](./SRE-agent/) | Site Reliability | Advanced | Runtime, Gateway, Memory, Observability — multi-agent with MCP tools and runbooks |
| [video-games-sales-assistant](./video-games-sales-assistant/) | Retail / Gaming | Intermediate | Runtime, Gateway, Memory — Next.js + Amplify Gen 2 frontend |

---

## Choosing a Sample

- **New to AgentCore?** Start with [local-prototype-to-agentcore](./local-prototype-to-agentcore/) for a guided migration walkthrough, or [slide-deck-generator-memory-agent](./slide-deck-generator-memory-agent/) for a focused Memory demo.
- **Multi-agent A2A?** See [A2A-multi-agent-incident-response](./A2A-multi-agent-incident-response/) (3 frameworks) or [A2A-realestate-agentcore-multiagents](./A2A-realestate-agentcore-multiagents/) (React UI + Cognito).
- **Enterprise identity (OBO / token exchange)?** See [auth0-multi-agent-obo](./auth0-multi-agent-obo/) — RFC 8693 On-Behalf-Of.
- **Healthcare / FHIR?** See [healthcare-appointment-agent](./healthcare-appointment-agent/).
- **Data Q&A with row-level security?** See [lakehouse-agent](./lakehouse-agent/).
- **VPC private networking?** See [customer-support-assistant-vpc](./customer-support-assistant-vpc/).
- **Role-based data access with Cedar policies?** See [role-based-hr-data-agent](./role-based-hr-data-agent/).
- **SRE / infrastructure operations?** See [SRE-agent](./SRE-agent/).
- **Financial market intelligence with optimization?** See [market-trends-agent](./market-trends-agent/).

---

## Related Categories

- [02-automation-agents](../02-automation-agents/) — Async agents triggered by events, tickets, and webhooks
- [03-coding-assistants](../03-coding-assistants/) — IDE and CI-driven agents for code generation and review
