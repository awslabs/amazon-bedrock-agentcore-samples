# Agent & Gateway Registry

A platform for managing AI agents and MCP tools across your organization. Register agents (A2A, MCP, or agent-as-tool), route them through AgentCore Gateways, manage access with Cedar policies, and let agents discover each other via API.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Next.js Dashboard                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐│
│  │ Registry │ │ Clients  │ │ Policies │ │  Overview  ││
│  │ (CRUD)   │ │ & Access │ │ (Cedar)  │ │  (Gateway) ││
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘│
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              Amazon Bedrock AgentCore                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐│
│  │ Gateway  │  │ Identity │  │  Cedar   │  │ Runtime ││
│  │ (MCP)    │  │ (Auth)   │  │ (RBAC)  │  │ (Host)  ││
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘│
└─────────────────────────────────────────────────────────┘
```

| Component | Purpose |
|-----------|---------|
| **Registry** | Catalog of all agents and tools (A2A, MCP, agent-as-tool) with CRUD, search, and discovery API |
| **AgentCore Gateway** | Single MCP endpoint aggregating tools from multiple backends with inbound/outbound auth |
| **Cedar Policy Engine** | Per-client tool composition — controls which tools each caller can discover and invoke |
| **AgentCore Identity** | Workload identities for agent-to-agent auth, federated with Cognito or EntraID |
| **DynamoDB** | Registry data store (agents, tools, metadata) |
| **App Runner** | Hosts the Next.js dashboard |
| **Cognito** | Dashboard authentication |

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| **Node.js** | 18+ | [Install guide](https://nodejs.org/) |
| **Python** | 3.10+ | [Install guide](https://www.python.org/) |
| **Docker** | Latest | [Docker Desktop](https://docs.docker.com/desktop/) |
| **AWS CLI** | v2 | [Install guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |

You need AWS credentials configured with permissions for AgentCore, Cognito, DynamoDB, Secrets Manager, App Runner, ECR, and CloudFormation.

You also need at least one AgentCore Gateway created. See the [Gateway documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html).

### Install gatewayctl CLI

The platform uses `gatewayctl` for gateway operations (client management, policy management, tool listing).

```bash
cd agentcore-manager
pip install -e .
```

Verify:
```bash
gatewayctl --help
```

## Deploy

### Option A: One-click deploy to AWS

```bash
scripts/deploy.sh
```

This creates all infrastructure (DynamoDB, ECR, App Runner, Cognito, IAM roles), builds the Docker image, and deploys the platform. Takes 5-10 minutes.

After deployment:
- Platform URL is printed in the output
- Login: `admin@platform.local` / `Admin123!` (change password on first login)

### Option B: Local development

```bash
cd platform-ui
npm install
npx prisma db push    # creates local SQLite DB
npm run dev
```

Open http://localhost:3000

Create a `.env` file:
```
GATEWAY_REGION=us-east-1
```

## Features

### Registry

Register agents and tools with three protocol types:

| Protocol | Description | Example |
|----------|-------------|---------|
| **MCP** | Tool server exposing tools via MCP protocol | Terraform MCP server |
| **A2A** | Agent supporting A2A protocol | Strands agent on AgentCore Runtime |
| **Agent-as-Tool** | Agent without A2A, wrapped as MCP tools | Salesforce Agentforce, n8n |

CRUD operations: create, read (search + expand), update (inline edit), delete (with confirmation).

Sync tools from live gateways or MCP endpoints. Fetch A2A agent cards from AgentCore Runtime.

### Gateway Management

Per-gateway management with auto-detected identity provider (Cognito or EntraID):

- **Overview** — gateway details, metrics, IdP
- **Tools** — live tool listing grouped by target
- **Clients & Access** — create Team (Cognito/EntraID) or Agent (AgentCore Identity) clients with optional tool composition
- **Policies** — Cedar RBAC with permit-only policies, enforcement mode toggle

### Tool Composition via Cedar

One gateway, different tool views per caller. Cedar permit-only policies control both `tools/list` (discovery) and `tools/call` (execution):

```cedar
permit(
  principal is AgentCore::OAuthUser,
  action in [
    AgentCore::Action::"terraform-target___search_modules",
    AgentCore::Action::"agentforce-target___ask_agentforce"
  ],
  resource == AgentCore::Gateway::"<gateway-arn>"
)
when {
  principal.hasTag("client_id") &&
  principal.getTag("client_id") == "<client-id>"
};
```

### Agent Discovery API

Public API for agent-to-agent discovery:

```bash
# All agents and gateways
GET /api/registry/discover

# Search by capability
GET /api/registry/discover?q=salesforce

# Filter by protocol
GET /api/registry/discover?protocol=a2a%2Bmcp

# Gateways only
GET /api/registry/discover?type=gateways
```

### Connect from Agent Code

Each client in the dashboard includes a ready-to-copy Python code snippet:

```python
import boto3, requests

# Agent client: get token via AgentCore Identity
identity = boto3.client("bedrock-agentcore", region_name="us-east-1")
token = identity.get_workload_access_token(
    workloadName="my-orchestrator-agent"
)["accessToken"]

# Call gateway — sees only permitted tools
gateway_url = "https://gateway-xxx.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
resp = requests.post(gateway_url,
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={"jsonrpc": "2.0", "id": "1", "method": "tools/list"})
```

## Project Structure

```
├── agentcore-manager/       # gatewayctl CLI (pip install -e .)
├── platform-ui/             # Next.js dashboard
│   ├── prisma/              # SQLite schema (local dev)
│   ├── src/
│   │   ├── app/             # Pages + API routes
│   │   ├── components/      # Registry page, UI components
│   │   ├── lib/             # AWS SDK, DynamoDB, auth, types
│   │   └── server/          # tRPC router
│   └── Dockerfile
├── scripts/
│   └── deploy.sh            # One-click deploy
└── template.yaml            # CloudFormation (DynamoDB + ECR + App Runner + Cognito)
```

## Cleanup

```bash
aws cloudformation delete-stack --stack-name agent-gateway-registry --region us-east-1
```

This removes all resources (App Runner, DynamoDB table, ECR repo, Cognito pool, IAM roles).
