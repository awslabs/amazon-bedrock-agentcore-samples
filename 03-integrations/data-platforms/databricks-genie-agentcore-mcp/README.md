# Databricks Genie via Amazon Bedrock AgentCore Gateway (MCP)

Expose a [Databricks Genie](https://docs.databricks.com/en/genie/index.html) space as a governed MCP tool to Amazon Bedrock agents through [Amazon Bedrock AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html), with the agent hosted on [AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime.html). Bedrock agents ask plain-English business questions; Genie returns lakehouse-native SQL answers grounded in Unity Catalog. The gateway authenticates to Databricks as a service principal (machine-to-machine), so queries run with — and are audited under — that service principal's Unity Catalog permissions. For per-user identity and attribution, see the [per-user delegation sample](../databricks-dbsql-per-user-delegation).

![Databricks Genie via Amazon Bedrock AgentCore Gateway architecture](images/architecture.png)

## Overview

This sample registers the [Databricks-managed Genie MCP endpoint](https://docs.databricks.com/en/generative-ai/mcp/managed-mcp.html) (`/api/2.0/mcp/genie/{space_id}`) as a target in Amazon Bedrock AgentCore Gateway. Once registered, any Bedrock agent associated with the gateway can call Genie as a tool — no custom NL-to-SQL chain, no data copy into Knowledge Bases, no parallel metric definitions. The gateway manages:

- **Inbound auth** — AgentCore Identity (fronted by Amazon Cognito in this sample) authorizes agent → tool calls
- **Outbound auth** — Databricks OAuth2 M2M credentials, registered via `CreateOauth2CredentialProvider` (scoped to `genie`) and retrieved by Gateway at tool-invocation time
- **Audit** — Unity Catalog audit logs attribute SQL execution to the service principal; AgentCore Runtime and Gateway emit CloudWatch traces for each tool invocation

> **Auth model.** This sample uses machine-to-machine (client-credentials) auth end to end, so Genie runs as the service principal — the right model for a shared, application-level integration. Per-user Unity Catalog attribution (Authorization Code / OBO) is **not** available on a managed `mcpServer` gateway target; use the [`databricks-dbsql-per-user-delegation`](../databricks-dbsql-per-user-delegation) sample (RFC 8693 token exchange) when you need each end user's own permissions.

This sample complements the existing Databricks integrations in this folder:

- [`databricks-dbsql-agentcore-gateway`](../databricks-dbsql-agentcore-gateway) — Databricks SQL MCP with M2M auth
- [`databricks-dbsql-per-user-delegation`](../databricks-dbsql-per-user-delegation) — Per-user delegation via RFC 8693 token exchange

## Prerequisites

1. AWS credentials configured (`aws configure`) with permissions to create AgentCore resources and IAM roles, plus Bedrock foundation-model access in your region (Claude, Nova, or your preferred model)
2. Databricks workspace on AWS with Unity Catalog enabled and at least one [Genie Space](https://docs.databricks.com/en/genie/index.html) with Trusted Assets defined
3. Databricks service principal with an [OAuth M2M secret](https://docs.databricks.com/en/dev-tools/auth/oauth-m2m.html). The service principal needs **all three** of the following — see [Service principal permissions](#service-principal-permissions) below, as a missing grant does not surface until the first real query:
   - `CAN RUN` on the Genie space
   - `CAN USE` on the SQL warehouse that backs the Genie space
   - `USE CATALOG` / `USE SCHEMA` / `SELECT` on the tables behind it
4. Python 3.10+

### Service principal permissions

Grant all three before running the notebook. The warehouse grant is easy to miss: `tools/list`
succeeds without it and the gateway target still reaches `READY`, so the integration looks
healthy right up until the first query fails.

Find the warehouse backing your Genie space:

```bash
databricks api get /api/2.0/genie/spaces/$GENIE_SPACE_ID   # returns warehouse_id
```

Then grant, replacing `$SP_APP_ID` with the service principal's **application ID**:

```bash
# 1. Genie space
databricks api patch /api/2.0/permissions/genie/$GENIE_SPACE_ID \
  --json '{"access_control_list":[{"service_principal_name":"'$SP_APP_ID'","permission_level":"CAN_RUN"}]}'

# 2. SQL warehouse behind the space
databricks api patch /api/2.0/permissions/warehouses/$WAREHOUSE_ID \
  --json '{"access_control_list":[{"service_principal_name":"'$SP_APP_ID'","permission_level":"CAN_USE"}]}'

# 3. Unity Catalog objects (repeat per schema the space reads)
databricks api patch /api/2.1/unity-catalog/permissions/catalog/$CATALOG \
  --json '{"changes":[{"principal":"'$SP_APP_ID'","add":["USE_CATALOG"]}]}'
databricks api patch /api/2.1/unity-catalog/permissions/schema/$CATALOG.$SCHEMA \
  --json '{"changes":[{"principal":"'$SP_APP_ID'","add":["USE_SCHEMA","SELECT"]}]}'
```

Symptoms of each missing grant, as returned inside the Genie message payload:

| Missing grant | Error |
|---|---|
| Warehouse `CAN_USE` | `PERMISSION_DENIED: <sp-id> is not authorized to use or monitor this SQL Endpoint` |
| UC `SELECT` / `USE SCHEMA` | `PERMISSION_DENIED: No access to '<catalog>.<schema>.<table>' … you must have SELECT on each data asset` |

## Getting Started

The notebook covers:

1. Configure Databricks + AWS credentials
2. Create (or reuse) an AgentCore Gateway with Cognito inbound auth
3. Register a Databricks OAuth2 credential provider for outbound auth via `CreateOauth2CredentialProvider`
4. Grant the gateway role the IAM permissions it needs to fetch tokens and read the stored secret
5. Add the Databricks Genie MCP endpoint as a Gateway target and synchronize tools
6. Verify the gateway locally with a Strands agent + MCP client, using sample prompts
7. Deploy the agent to AgentCore Runtime and invoke it end-to-end
8. Validate governance via Unity Catalog audit logs and CloudWatch traces
9. Clean up — destroy the runtime deployment, then delete the target, credential provider, and gateway

## Resources

- [Databricks Genie](https://docs.databricks.com/en/genie/index.html)
- [Databricks managed MCP servers](https://docs.databricks.com/en/generative-ai/mcp/managed-mcp.html)
- [Databricks OAuth M2M authentication](https://docs.databricks.com/en/dev-tools/auth/oauth-m2m.html)
- [Amazon Bedrock AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
- [Amazon Bedrock AgentCore Identity](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html)
- [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime.html)
- [Strands Agents](https://strandsagents.com/)
- [AgentCore Gateway tutorials](https://github.com/awslabs/agentcore-samples/tree/main/01-tutorials/02-AgentCore-gateway)
