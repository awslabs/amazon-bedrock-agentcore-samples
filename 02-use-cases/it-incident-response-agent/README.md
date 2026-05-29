# IT Incident Response Agent on Amazon Bedrock AgentCore

An event-driven IT assistant. Publish a "ticket" to SNS — an AgentCore
Runtime agent picks it up, diagnoses the issue using a Knowledge Base
and a few Lambda tools (all behind an AgentCore Gateway), records an
episode in AgentCore Memory, and writes a resolution comment back to
the ticket store.

## Architecture

```
┌──────────────────────┐
│  Mock-Jira event     │  publish JSON ticket
│  (SNS topic)         │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  TicketEventHandler  │  persists ticket, invokes the runtime
│       (Lambda)       │  (no token handling)
└──────────┬───────────┘
           │
           ▼
┌─────────────────────────────────┐        ┌──────────────────────┐
│  AgentCore Runtime              │  MCP   │  AgentCore Gateway   │
│  (Strands agent in container)   │ ─────▶ │  inbound: Auth0 JWT  │
│  - @requires_access_token       │  Bearer│  4 Lambda targets    │
│    -> AgentCore Identity        │        └──────────┬───────────┘
│       -> Auth0 (M2M)            │                   │
│  - calls 4 tools via Gateway    │       ┌───────────┴───────────┐
│  - writes Memory event          │       │                       │
│  - writes resolution to DDB     │       ▼                       ▼
└──────────────────────────────────       lookup_user,        query_kb ──▶ Bedrock KB
                                          get_process_info,                (OpenSearch
                                          create_change_request            Serverless)
                                          (DynamoDB)
```

- **Trigger** : SNS (mock Jira ticket) -> Lambda -> `InvokeAgentRuntime`.
- **Identity**: Auth0 + AgentCore Identity. The Gateway uses a
  `CUSTOM_JWT` inbound authorizer pointed at the Auth0 OIDC discovery
  URL. The agent fetches its outbound token via AgentCore Identity
  (`@requires_access_token`, `auth_flow="M2M"`) — AgentCore does the
  client_credentials grant against Auth0 internally; the agent never
  sees the client secret.
- **Tools** : 3 Lambda tools + 1 Knowledge-Base Lambda wrapper, all
  registered as Gateway Lambda targets.
- **Memory** : `CfnMemory` with a `summary_memory_strategy` named
  `incident_episodes` and namespace `incidents/{actorId}`. One event
  per ticket; AgentCore rolls events into episodes per user.
- **State** : DynamoDB tables for `Users`, `Processes`, `Tickets`,
  `ChangeRequests`. The agent writes the resolution + status directly
  to the `Tickets` row at the end of the run.
- **Observability**: AWS Distro for OpenTelemetry inside the runtime
  container — Strands and the MCP client are auto-instrumented. Spans
  - logs flow to a per-stack CloudWatch log group and surface in
    CloudWatch GenAI Observability.
- **Evaluation**: an `OnlineEvaluationConfig` continuously samples
  runtime traces and runs four built-in LLM-as-a-judge evaluators
  (`GoalSuccessRate`, `Correctness`, `Helpfulness`,
  `ToolSelectionAccuracy`). On-demand evaluation lives in
  `scripts/evaluate.py` and includes a custom `IncidentResolutionQuality`
  evaluator on top of the built-ins.

## Prerequisites

1. AWS account + CLI configured (`aws sts get-caller-identity` works).
2. **Bedrock model access** in your region for:
   - The agent model (default `claude-sonnet-4-6`).
   - The KB embedding model (default `amazon.titan-embed-text-v2:0`).
     See [Bedrock model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html).
3. Node + AWS CDK v2 (`npm install -g aws-cdk`, version ≥ 2.220).
4. Python 3.10+.
5. **Auth0 tenant** (free):
   - Create a Machine-to-Machine **Application**.
   - Create an **API** with an Identifier — that's your
     `AUTH0_AUDIENCE`. Authorize the M2M app on the API.

## Configure

```bash
cp .env.example .env
$EDITOR .env
```

Required keys:

| Key                     | Purpose                                                 |
| ----------------------- | ------------------------------------------------------- |
| `STACK_NAME`            | CFN stack name. Resource prefix.                        |
| `AWS_REGION`            | Deploy region (e.g. `us-west-2`).                       |
| `AGENT_MODEL_ID`        | Bedrock model for the Strands agent.                    |
| `KB_EMBEDDING_MODEL_ID` | Bedrock embedding model for the KB.                     |
| `AUTH0_DOMAIN`          | e.g. `your-tenant.us.auth0.com`.                        |
| `AUTH0_CLIENT_ID`       | M2M client ID.                                          |
| `AUTH0_CLIENT_SECRET`   | M2M client secret. Stored in Secrets Manager on deploy. |
| `AUTH0_AUDIENCE`        | The Auth0 API Identifier.                               |

## Deploy

```bash
./scripts/deploy.sh
```

The script will:

1. Create a `.venv` and install CDK.
2. `cdk bootstrap` if needed.
3. `cdk deploy` the stack.

Expected duration: ~15–20 minutes (most of it is the agent CodeBuild
and KB ingestion).

Stack outputs you'll use:

| Output                 | Description                                  |
| ---------------------- | -------------------------------------------- |
| `TicketsTopicArn`      | SNS topic; publish JSON tickets here.        |
| `TicketsTableName`     | DynamoDB table that stores ticket state.     |
| `AgentRuntimeArn`      | AgentCore Runtime ARN.                       |
| `GatewayUrl`           | MCP endpoint of the AgentCore Gateway.       |
| `MemoryId`             | AgentCore Memory ID.                         |
| `KnowledgeBaseId`      | Bedrock KB ID.                               |
| `RuntimeLogGroupName`  | CloudWatch log group for runtime spans/logs. |
| `OtelServiceName`      | OTEL `service.name` of the runtime.          |
| `OnlineEvalConfigName` | Name of the online evaluation config.        |

## Run an end-to-end demo

```bash
# Publish the bundled sample ticket (INC-1042: VPN issues for U-1001)
./scripts/publish_ticket.sh

# Tail the runtime logs while the agent runs
aws logs tail /aws/bedrock-agentcore/runtimes --follow --region us-west-2

# After ~30 seconds, check the resolved ticket
./scripts/show_ticket.sh INC-1042
```

You should see a row with `status=Resolved` and a `resolution_comment`
written by the agent.

### Custom tickets

Publish your own ticket:

```bash
cat > /tmp/my-ticket.json <<'JSON'
{
  "ticket_id": "INC-2099",
  "requester_id": "U-1002",
  "title": "Outlook search returns nothing",
  "description": "Search box is empty results, on macOS, version 16.84.",
  "priority": "MEDIUM"
}
JSON

./scripts/publish_ticket.sh /tmp/my-ticket.json
```

Ticket schema (all fields required):

| Field          | Type   | Notes                                   |
| -------------- | ------ | --------------------------------------- |
| `ticket_id`    | string | Unique. Used as Memory `session_id`.    |
| `requester_id` | string | Must exist in the `Users` table.        |
| `title`        | string |                                         |
| `description`  | string |                                         |
| `priority`     | string | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL`. |

## Observability + Evaluation

Spans and logs from the runtime go to the CloudWatch log group named in
the `RuntimeLogGroupName` output. View traces in the CloudWatch GenAI
Observability console, filtering on the service name from the
`OtelServiceName` output.

Online evaluation runs continuously — results land back in CloudWatch
under the same `service.name`. To run evaluators on demand against a
specific session:

```bash
python scripts/evaluate.py                # latest trace
python scripts/evaluate.py <trace_id>     # a specific trace
```

The script registers a custom `IncidentResolutionQuality` LLM-as-a-judge
evaluator on first use, then runs it alongside the four built-ins.

> First-time setup: enable **CloudWatch Transaction Search** in the
> region or traces won't surface for evaluation.

## Inspect what the agent did

```bash
# DDB rows
aws dynamodb scan --table-name <ChangeRequestsTable> --region $AWS_REGION

# AgentCore Memory events for a user
aws bedrock-agentcore list-events \
  --memory-id <MemoryId> \
  --actor-id U-1001 \
  --region $AWS_REGION

# Runtime logs
aws logs tail /aws/bedrock-agentcore/runtimes --since 10m --region $AWS_REGION
```

## Cleanup

```bash
./scripts/destroy.sh
```

CloudFormation deletes the gateway and its targets via the native L1
constructs. If `cdk destroy` hangs, the usual culprits are OpenSearch
Serverless or Bedrock KB taking a few minutes to drop — check the
CloudFormation console.

## Troubleshooting

- **`cdk deploy` fails on the gateway custom resource.** Check the
  CloudWatch log group for `GatewayProvisionerFn`. The most common
  causes are an Auth0 discovery URL that doesn't resolve, or an
  `AUTH0_AUDIENCE` that doesn't match the API Identifier.
- **`InvokeAgentRuntime` returns 401.** The Auth0 token's audience
  must match `AUTH0_AUDIENCE`. Confirm the M2M app is _authorized_
  on the API in Auth0.
- **KB query returns no results.** First-time ingestion runs as part
  of deploy but completes asynchronously; wait ~2 minutes after the
  stack finishes, or re-run `StartIngestionJob` manually.
- **Build step times out.** The agent image is ARM64; CodeBuild ARM64
  is slower than x86. Bump `BuildTrigger`'s timeout in the stack if
  you hit it consistently.
