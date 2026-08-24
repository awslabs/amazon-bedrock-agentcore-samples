# Amazon Bedrock AgentCore Use Cases

End-to-end samples organized by agent type. Each folder maps to one of the three workload categories used in AgentCore documentation.

## Categories

### [01-conversational-agents](./01-conversational-agents/) 

* **[AWS Operations Agent](./AWS-operations-agent/)**: Intelligent AWS operations assistant with Okta authentication and comprehensive monitoring capabilities
* **[Customer Support Assistant](./customer-support-assistant/)**: Production-ready customer service agent with memory, knowledge base integration, and Google OAuth
* **[DB Performance Analyzer](./DB-performance-analyzer/)**: Database performance monitoring and analysis agent with PostgreSQL integration
* **[Device Management Agent](./device-management-agent/)**: IoT device management system with Cognito authentication and real-time monitoring
* **[Enterprise Web Intelligence Agent](./enterprise-web-intelligence-agent/)**: Web research and analysis agent using browser tools for competitive intelligence
* **[Farm Management Advisor](./farm-management-advisor/)**: Agricultural advisory system with plant detection, weather forecasting, and care recommendations
* **[Auth0 Multi-Agent OBO](./auth0-multi-agent-obo/)**: RFC 8693 On-Behalf-Of token exchange with Auth0 PKCE — coordinator exchanges user JWT for attenuated per-agent tokens in a multi-agent financial services system
* **[Finance Personal Assistant](./finance-personal-assistant/)**: Personal budget management with multi-agent workflows and guardrails
* **[Healthcare Appointment Agent](./healthcare-appointment-agent/)**: FHIR-compliant healthcare appointment scheduling with patient data integration
* **[Local Prototype to AgentCore](./local-prototype-to-agentcore/)**: Migration guide from local development to production AgentCore deployment
* **[Market Trends Agent](./market-trends-agent/)**: Financial market analysis with browser tools and memory integration
* **[SRE Agent](./SRE-agent/)**: Site reliability engineering assistant with multi-agent LangGraph workflows
* **[Text to Python IDE](./text-to-python-ide/)**: Code generation and execution environment with AgentCore Code Interpreter
* **[Data Analyst Conversational Assistant](./data-analyst-conversational-assistant/)**: Data analysis assistant with Amplify frontend and CDK deployment
* **[Claude Code Gateway MCP Server](./claude-code-gateway-mcp-server/)**: Integrate Claude Code with MCP Server using AgentCore Gateway for dynamic tool loading and centralized access
Agents that interact with users in real time. Users authenticate through an identity provider, the agent maintains session and long-term memory per user, and responses stream back as the agent works. See the [category README](./01-conversational-agents/README.md) for the full list and a guide on which sample to start with.

| Sample | Vertical | Key Features |
|--------|----------|--------------|
| [A2A-multi-agent-incident-response](./01-conversational-agents/A2A-multi-agent-incident-response/) | IT / DevOps | Runtime, Gateway, Memory, A2A (3 frameworks) |
| [AWS-operations-agent](./01-conversational-agents/AWS-operations-agent/) | Cloud Operations | Runtime, Gateway, Memory, Policy, Observability |
| [customer-support-assistant-vpc](./01-conversational-agents/customer-support-assistant-vpc/) | Retail / E-commerce | Runtime, Gateway (VPC) |
| [deep-research-agent](./01-conversational-agents/deep-research-agent/) | Research / Q&A | Gateway (Web Search), Runtime |
| [device-management-agent](./01-conversational-agents/device-management-agent/) | IoT / Smart Home | Runtime, Gateway, Policy, Identity (Cognito) |
| [finance-personal-assistant](./01-conversational-agents/finance-personal-assistant/) | Personal Finance | Gateway, Policy |
| [healthcare-appointment-agent](./01-conversational-agents/healthcare-appointment-agent/) | Healthcare | Runtime, Gateway, Policy, Observability (FHIR R4) |
| [lakehouse-agent](./01-conversational-agents/lakehouse-agent/) | Data and Analytics | Runtime, Gateway, Memory, Policy (row-level security) |
| [market-trends-agent](./01-conversational-agents/market-trends-agent/) | Financial Services | Runtime, Memory, Browser, Evaluations, Optimization |
| [SRE-agent](./01-conversational-agents/SRE-agent/) | Site Reliability | Runtime, Gateway, Memory, Observability |
| [video-games-sales-assistant](./01-conversational-agents/video-games-sales-assistant/) | Retail / Gaming | Runtime, Gateway, Memory |

### [02-workflow-automation-agents](./02-workflow-automation-agents/) 

Agents that run without a user in the loop. They are triggered by events such as file uploads, webhook calls, or scheduled jobs. Identity is service-to-service rather than user-facing, and memory is minimal since state is carried in the event payload.

| Sample | Vertical | Key Features |
|--------|----------|--------------|
| [event-driven-claims-agent](./02-workflow-automation-agents/event-driven-claims-agent/) | Insurance | Runtime, Gateway, Memory, Policy, Evaluations, Observability |
| [visa-b2b-account-payable-agent](./02-workflow-automation-agents/visa-b2b-account-payable-agent/) | B2B Payments | Runtime, Gateway, Policy, Payments |
| [enterprise-web-intelligence-agent](./02-workflow-automation-agents/enterprise-web-intelligence-agent/) | Market Intelligence | Runtime, Browser |
| [intelligent-event-agent](./02-workflow-automation-agents/intelligent-event-agent/) | General / Events | Runtime, Memory, Gateway *(in development)* |
| [multi-isv-orchestration](./02-workflow-automation-agents/multi-isv-orchestration/) | Enterprise CRM + ERP | Gateway (multi-target), Identity (Cognito + CustomOauth2) |
| [gpu-music-production-agent](./02-workflow-automation-agents/gpu-music-production-agent/) | Media & Entertainment | Runtime (EC2 capacity provider, GPU), Memory; local model inference, collocated agents on a shared volume |

### [03-coding-assistants](./03-coding-assistants/) 

Agents that help developers write, run, or fix code. Tasks tend to be longer-running and scoped to a project or repository. AgentCore Code Interpreter handles sandboxed execution, and Gateway can aggregate multiple developer tool APIs behind one MCP endpoint.

| Sample | Use Case | Key Features |
|--------|----------|--------------|
| [text-to-python-ide](./03-coding-assistants/text-to-python-ide/) | Text-to-Python IDE with sandboxed execution | Runtime, Code Interpreter, Memory, Policy |
| [claude-code-gateway-mcp-server](./03-coding-assistants/claude-code-gateway-mcp-server/) | Single MCP endpoint for Claude Code | Gateway, Identity |


## Resources
- [AgentCore docs](https://docs.aws.amazon.com/bedrock-agentcore/)
