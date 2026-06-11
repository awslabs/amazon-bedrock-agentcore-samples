# Coding Agents

IDE and CI-driven agents for code generation, refactor, and review. Long-running tasks in a sandboxed Code Interpreter runtime.

Coding agents differ from conversational agents in execution profile: tasks are often long-running (minutes to hours), scoped to a project or repository, and require secure sandboxed execution with audit trails. AgentCore Code Interpreter provides isolated container execution with no risk to your infrastructure. AgentCore Gateway aggregates developer tool APIs (GitHub, Jira, AWS) behind a single MCP endpoint, reducing context window overhead in IDE integrations.

---

## What makes a Coding Agent

| Dimension | Coding Agent Configuration |
|-----------|---------------------------|
| **Identity** | Developer identity — agent acts on behalf of the developer or CI service account |
| **Memory** | Project-scoped context — remembers codebase conventions, past decisions, open issues |
| **Runtime** | Long-running (hours), Code Interpreter for sandboxed execution |
| **Guardrails** | Code quality gates, security scanning, blocks malicious code generation |
| **Observability** | Per-task tracing — track which files were changed, which tools were called |
| **Gateway** | Aggregated MCP endpoint for IDE tools (GitHub, Jira, AWS, internal APIs) |

### Common Patterns

| Pattern | When to use |
|---------|-------------|
| **Plan-Act-Reflect** | Code generation with iterative self-review (plan → write → test → fix) |
| **Swarm** | Multi-file refactors where parallel agents handle different modules |
| **Human-in-the-Loop** | Code review gate — agent opens PR, human approves before merge |

---

## Samples

| Sample | Use Case | Complexity | Key AgentCore Features |
|--------|----------|------------|------------------------|
| [text-to-python-ide](./text-to-python-ide/) | Full-stack text-to-Python IDE with sandboxed code execution | Intermediate | Runtime, Code Interpreter, Memory, Policy (Guardrails) |
| [claude-code-gateway-mcp-server](./claude-code-gateway-mcp-server/) | Aggregate multiple MCP servers behind one AgentCore Gateway endpoint for Claude Code | Intermediate | Gateway (MCP aggregation), Identity |
| [gateway-schema-support-agent](./gateway-schema-support-agent/) | Auto-convert and repair OpenAPI specs for AgentCore Gateway compatibility | Intermediate | Gateway, Code tools |

---

## Choosing a Sample

- **Building a code generation or execution tool?** Start with [text-to-python-ide](./text-to-python-ide/) — demonstrates Code Interpreter, Runtime, Memory, and Guardrails together in a full-stack React + FastAPI app.
- **Managing MCP server sprawl for Claude Code in your enterprise?** See [claude-code-gateway-mcp-server](./claude-code-gateway-mcp-server/) — consolidates N MCP servers behind a single Gateway endpoint, reducing context window overhead and configuration sprawl.
- **Integrating an existing API with AgentCore Gateway?** See [gateway-schema-support-agent](./gateway-schema-support-agent/) — ICARUS automatically converts and repairs OpenAPI specs to meet Gateway requirements, cutting integration time from days to hours.

---

## Related Categories

- [01-conversational-agents](../01-conversational-agents/) — Customer-facing chat agents with memory, identity, and guardrails
- [02-automation-agents](../02-automation-agents/) — Async agents triggered by events, tickets, and webhooks
