# System Components

## SRE Agent Core

Built on LangGraph, the core orchestrates multiple specialized agents. The Supervisor Agent coordinates investigations by analyzing queries and routing them to appropriate specialist agents. Each agent accesses domain-specific tools through the MCP protocol to interact with infrastructure APIs.

The collaboration model enables complex investigations across multiple domains. For example, investigating a pod failure might involve the Kubernetes Agent identifying resource constraints, the Metrics Agent providing historical analysis, and the Logs Agent correlating errors.

## AgentCore Gateway

The gateway provides secure communication between AI agents and infrastructure APIs. Built on the Model Context Protocol (MCP), it offers:

- Standardized interface for tool discovery and execution
- Authentication through bearer tokens
- Health monitoring for reliable operations
- Protocol translation and retry logic

## Infrastructure Integration

The system includes a demo environment for evaluation and testing:

**Demo Environment**: Four specialized API servers simulate Kubernetes clusters, log aggregation systems, metrics databases, and operational procedures. This allows evaluation without impacting production systems. The demo provides realistic mock data and API responses that showcase the agent system's capabilities in a controlled environment.