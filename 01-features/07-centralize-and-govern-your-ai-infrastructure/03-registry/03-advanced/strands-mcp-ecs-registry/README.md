# Registry-Driven Agent with Strands, MCP, and ECS

## Overview

This sample demonstrates how to integrate **AWS Agent Registry** into an existing agentic architecture where the agent and MCP server are self-hosted on **Amazon ECS** — without requiring a full migration to AgentCore Runtime or AgentCore Gateway.

If you already host Strands agents and MCP servers on ECS or EKS and manage your own compute, networking, and container lifecycle, this sample shows how to adopt AWS Agent Registry as a **centralized discovery and governance layer** on top of that existing infrastructure — gaining semantic search, skill versioning, and approval workflows without changing how your agents and tools are deployed.

This sample is useful in two ways:
- **If you are already on ECS/EKS**: a practical starting point for adding registry-driven skill discovery to a self-hosted agentic system.
- **If you are evaluating AgentCore**: a reference for the registry integration pattern before adopting AgentCore Runtime or Gateway for compute.

Financial analysis is used as the example domain — the registry-driven architecture pattern applies broadly.

| Information | Details |
|-------------|---------|
| Use case type | Conversational AI |
| Agent type | Single agent with dynamic skill discovery |
| Use case components | Agent Registry, Strands Agent, MCP Server, Chat Interface |
| Use case vertical | Financial Analysis |
| Example complexity | Advanced |
| SDK used | Strands Agents SDK, Amazon Bedrock AgentCore SDK, boto3 |

## Architecture

```
Internet
    │
Chat ALB (public)
    │
Chat ECS (private subnet)
    │
Agent ALB (internal)
    │
Agent ECS (private subnet)
 │          │
Registry    API Gateway (HTTPS + SigV4)
(AWS API)       │
  via         VPC Link
 NAT GW          │
      │      MCP ALB (internal)
      │          │
   Amazon    MCP ECS (private subnet)
   Bedrock
```

### Components

| Component | Technology | Role |
|-----------|-----------|------|
| Agent Registry | AWS Agent Registry | Stores skills and MCP server schemas; serves semantic search |
| Strands Agent | Python / Strands SDK | Per-request: search registry → read skill → load tools → invoke the model |
| MCP Server | FastMCP / Python | Exposes `get_financial_data` and `get_kpi_benchmarks` tools |
| Chat Interface | FastAPI + SSE | Browser-facing proxy; streams agent step events to the UI |
| Infrastructure | ECS Fargate, API GW, VPC, CloudFormation | Private VPC; API Gateway bridges internal MCP server to the registry crawler |

### Two-Phase Request Flow

**Phase 1 — Pre-flight (before the model is invoked)**

1. **Registry search** — the raw user message is used as the search query. The registry returns records ranked by vector similarity. The agent filters to `AGENT_SKILLS` records.
2. **Parse frontmatter** — the top-ranked record's `SKILL.md` is parsed to read the `mcp_tools:` list.
3. **Selective MCP tool loading** — connects to the MCP server and loads *only* the declared tools.
4. **Build the Strands agent** — constructs the agent with base tools + the skill's MCP tools.

**Phase 2 — Strands reasoning loop (the LLM drives this)**

5. **Load full SKILL.md** — the LLM calls `search_and_load_skill` to load the complete skill procedure.
6. **Follow the procedure** — the LLM calls the MCP tools as instructed by the skill steps.
7. **Return answer** — results are streamed to the UI via SSE.

## What's in the Registry

`setup.py` and `register_skills.py` populate the registry with two types of records:

### MCP Record — `financial-tools-mcp`

One MCP record pointing to the MCP server. The registry crawler fetches the live server at registration time and stores the tool schemas inline. This record contains:

| Tool | Description |
|------|-------------|
| `get_financial_data` | Returns quarterly P&L data (revenue, COGS, operating expenses, EBITDA) for a given period |
| `get_kpi_benchmarks` | Returns industry benchmark thresholds and KPI formulas (Gross Margin, EBITDA Margin, OpEx Ratio, Revenue Growth) |

### AGENT_SKILLS Records — Five Skills

Each skill is a `SKILL.md` file stored as inline content in the registry. Skills declare which MCP tools they need in their YAML frontmatter — the agent loads only those tools per request.

| Skill | Description | MCP tools declared |
|-------|-------------|-------------------|
| `quarterly-kpi-calculator` | Calculates Gross Margin %, EBITDA Margin %, OpEx Ratio, and QoQ Revenue Growth from P&L data | `get_financial_data`, `get_kpi_benchmarks` |
| `cost-efficiency-analyzer` | Analyzes cost structure and operating expense efficiency | `get_financial_data`, `get_kpi_benchmarks` |
| `revenue-growth-analyst` | Deep-dives into top-line revenue growth across quarters | `get_financial_data` |
| `multi-quarter-trend-analysis` | Produces a 4-quarter narrative trend analysis | `get_financial_data`, `get_kpi_benchmarks` |
| `executive-financial-briefing` | One-page CFO/board-level financial briefing | `get_financial_data`, `get_kpi_benchmarks` |

## Core Idea

> **Separate what an agent knows how to do from the agent itself.**

Skills, procedures, and tool dependencies are stored in the AWS Agent Registry as `SKILL.md` files. The agent is a generic executor. You can add or update skills without touching agent code or redeploying.

```
User prompt
  → Registry search (find the right skill)
    → Parse SKILL.md frontmatter (which MCP tools are needed)
      → Load only those tools from the MCP server
        → LLM reasoning loop (follow the skill procedure)
          → Final answer
```

## Key Features

- **Zero hardcoded skills** — the agent discovers all capabilities at runtime from the registry
- **Selective tool loading** — only the MCP tools declared in a skill's frontmatter are loaded per request
- **Auto-approval workflow** — registry records go from DRAFT → PENDING_APPROVAL → APPROVED in a single script
- **SigV4 MCP transport** — MCP server is behind API Gateway with IAM auth; agent signs every request
- **SSE streaming** — agent reasoning steps stream to the chat UI in real time

## Prerequisites

### Required Software

- **Python 3.11+**
- **Docker** (for building container images)
- **AWS CLI** (configured with appropriate permissions)

### AWS Account Requirements

- **AWS Region**: `us-east-1` (AgentCore public preview availability)
- **Amazon Bedrock AgentCore** enabled in your account
- **Model access**: `us.anthropic.claude-sonnet-4-6` (cross-region inference profile)
- **Three ECR repositories** for the agent, chat, and MCP server images

### IAM Permissions

Your AWS user/role needs permissions for:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "ecs:*",
        "ecr:*",
        "ec2:*",
        "elasticloadbalancing:*",
        "apigateway:*",
        "s3:*",
        "ssm:*",
        "cognito-idp:*",
        "iam:*",
        "logs:*",
        "bedrock-agentcore:*"
      ],
      "Resource": "*"
    }
  ]
}
```

## Deployment Steps

### 1. Build and Push Docker Images

```bash
AWS_ACCOUNT=<your-account-id>
REGION=us-east-1

# Authenticate with ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com

# MCP server
docker build -t $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/financial-agent-mcp:latest deploy/mcp/
docker push $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/financial-agent-mcp:latest

# Strands agent
docker build -t $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/financial-agent-agent:latest deploy/agent/
docker push $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/financial-agent-agent:latest

# Chat interface
docker build -t $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/financial-agent-chat:latest deploy/chat/
docker push $AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/financial-agent-chat:latest
```

### 2. Deploy the CloudFormation Stack

```bash
aws cloudformation deploy \
  --template-file deploy/infra/cfn.yaml \
  --stack-name financial-agent \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    McpImageUri=$AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/financial-agent-mcp:latest \
    AgentImageUri=$AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/financial-agent-agent:latest \
    ChatImageUri=$AWS_ACCOUNT.dkr.ecr.$REGION.amazonaws.com/financial-agent-chat:latest
```

The stack creates: VPC with private/public subnets, NAT Gateway, ECS Fargate cluster, three ECS services (MCP/Agent/Chat), internal ALBs, API Gateway + VPC Link, S3 skills bucket, Cognito User Pool, IAM roles, and CloudWatch log groups.

### 3. Start the MCP Service

The MCP service must be running before registry setup — the registry crawler will attempt to crawl it during record creation.

```bash
aws ecs update-service \
  --cluster financial-agent-cluster \
  --service financial-agent-mcp \
  --desired-count 1
```

### 4. Run One-Time Registry Setup

Get the stack outputs first:

```bash
aws cloudformation describe-stacks \
  --stack-name financial-agent \
  --query "Stacks[0].Outputs"
```

Then run setup:

```bash
python deploy/infra/setup.py \
  --region us-east-1 \
  --bucket <SkillsBucketName from outputs> \
  --apigw-url <McpApiGwUrl from outputs>
```

This will:
1. Upload skill artifacts to S3
2. Create the AWS Agent Registry
3. Publish and auto-approve the MCP record (registry crawls the API Gateway URL to populate tool schemas)
4. Publish and auto-approve the `quarterly-kpi-calculator` AGENT_SKILLS record
5. Write `REGISTRY_ARN` and `SKILLS_BUCKET` to SSM Parameter Store

> **Why a Python script and not CloudFormation?**
> The AWS Agent Registry (`bedrock-agentcore-control`) does not have CloudFormation resource types yet. `setup.py` handles all registry operations via direct boto3 API calls.

### 5. Register Additional Skills

```bash
python deploy/infra/register_skills.py \
  --registry-arn <REGISTRY_ARN from setup output> \
  --region us-east-1
```

Registers all skills in `my_skills/` not already in the registry. Safe to re-run — skips existing records.

### 6. Start Agent and Chat Services

```bash
aws ecs update-service --cluster financial-agent-cluster --service financial-agent-agent --desired-count 1
aws ecs update-service --cluster financial-agent-cluster --service financial-agent-chat --desired-count 1
```

Access the chat UI at the `ChatEndpoint` URL from the stack outputs.

## Sample Queries

Once deployed, interact with the agent using natural language:

```
"Calculate the quarterly KPIs for Q3 2025"
"Show me gross margin and EBITDA for last quarter"
"Are we spending too much on operating expenses?"
"Show me the revenue growth trend over the last 4 quarters"
"Give me an executive briefing on how the business is doing"
"Compare Q2 and Q3 2025 revenue growth"
```

## Troubleshooting

### Common Issues

**"Unable to assume the provided IAM role" during registry setup**

The AgentCore registry crawler calls `sts:AssumeRole` on the role specified in `credentialProviderConfigurations`. The role's trust policy must explicitly allow `bedrock-agentcore.amazonaws.com` as a service principal.

```yaml
# In the agent task role's AssumeRolePolicyDocument:
- Effect: Allow
  Principal:
    Service: bedrock-agentcore.amazonaws.com
  Action: sts:AssumeRole
```

**Registry crawler fails to parse MCP server response**

FastMCP defaults to SSE (Server-Sent Events). The registry crawler sends a one-shot HTTP POST and expects plain JSON. Enable JSON responses:

```python
mcp_app = mcp.http_app(json_response=True)  # required for registry URL-sync crawling
```

**Agent cannot find MCP server URL after startup**

`search_registry_records` does not return `synchronizationConfiguration`. The MCP server URL is stored by the crawler inside `descriptors.mcp.server.inlineContent` as a JSON string:

```python
inline = record["descriptors"]["mcp"]["server"]["inlineContent"]
server_json = json.loads(inline)
url = server_json["remotes"][0]["url"]
```

**RuntimeError on every MCP request**

FastMCP's lifespan must be passed to Starlette explicitly:

```python
app = Starlette(
    routes=[...],
    lifespan=mcp_app.lifespan,  # required — omitting causes RuntimeError on every request
)
```

### Debug Commands

```bash
# Check ECS service status
aws ecs describe-services --cluster financial-agent-cluster \
  --services financial-agent-mcp financial-agent-agent financial-agent-chat

# View agent logs
aws logs tail /ecs/financial-agent/agent --follow

# List registry records
aws bedrock-agentcore-control list-registry-records \
  --registry-id <REGISTRY_ID> --region us-east-1

# Search registry
aws bedrock-agentcore search-registry-records \
  --search-query "financial KPIs" \
  --registry-ids "<REGISTRY_ARN>" \
  --region us-east-1
```

## Cleanup Instructions

### 1. Delete Registry Records and Registry

```bash
# List and delete all records first
aws bedrock-agentcore-control list-registry-records \
  --registry-id <REGISTRY_ID> --region us-east-1

aws bedrock-agentcore-control delete-registry-record \
  --registry-id <REGISTRY_ID> --record-id <RECORD_ID> --region us-east-1

# Then delete the registry
aws bedrock-agentcore-control delete-registry \
  --registry-id <REGISTRY_ID> --region us-east-1
```

### 2. Scale Down ECS Services

```bash
aws ecs update-service --cluster financial-agent-cluster --service financial-agent-mcp --desired-count 0
aws ecs update-service --cluster financial-agent-cluster --service financial-agent-agent --desired-count 0
aws ecs update-service --cluster financial-agent-cluster --service financial-agent-chat --desired-count 0
```

### 3. Delete the CloudFormation Stack

```bash
# Empty the S3 bucket first
aws s3 rm s3://financial-agent-skills-<account-id> --recursive

# Then delete the stack
aws cloudformation delete-stack --stack-name financial-agent
```

## Project Structure

```
strands-mcp-ecs-registry/
├── deploy/
│   ├── agent/                          # Strands agent service
│   │   ├── agent.py                    # FastAPI app + registry + MCP logic
│   │   ├── streamable_http_sigv4.py    # SigV4-signed MCP transport
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── chat/                           # Chat interface service
│   │   ├── chat.py                     # FastAPI SSE proxy
│   │   ├── static/index.html           # React chat UI
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── mcp/                            # MCP server service
│   │   ├── mcp_server.py               # FastMCP server with financial tools
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── infra/
│       ├── cfn.yaml                    # CloudFormation stack (~800 lines)
│       ├── setup.py                    # One-time registry + S3 setup
│       └── register_skills.py          # Add AGENT_SKILLS records to registry
└── my_skills/
    ├── quarterly-kpi-calculator/       # Gross Margin, EBITDA, OpEx, QoQ Growth
    ├── cost-efficiency-analyzer/       # Cost structure and expense efficiency
    ├── revenue-growth-analyst/         # Top-line revenue growth deep-dive
    ├── multi-quarter-trend-analysis/   # 4-quarter trend narrative
    └── executive-financial-briefing/   # One-page CFO/board briefing
```

## Additional Resources

- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
- [AWS Agent Registry Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/registry.html)
- [Strands Agents SDK](https://github.com/strands-agents/sdk-python)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [FastMCP](https://github.com/jlowin/fastmcp)

## Disclaimer

The examples provided in this repository are for experimental and educational purposes only. They demonstrate concepts and techniques but are not intended for direct use in production environments without further review and hardening. Make sure to have Amazon Bedrock Guardrails in place to protect against prompt injection.
