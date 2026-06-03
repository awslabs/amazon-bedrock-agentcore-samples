# IT Incident Response Agent on Amazon Bedrock AgentCore

An event-driven IT assistant. Fire a Jira issue key at an SNS topic — an
AgentCore Runtime agent picks it up, fetches the issue from Jira via the
Atlassian Remote MCP server, diagnoses the issue using a Knowledge Base
and a few Lambda tools (all behind an AgentCore Gateway), records an
episode in AgentCore Memory, and writes a resolution comment + status
transition back into Jira — through the same MCP server.

## Architecture

```
┌──────────────────────┐
│  Jira automation     │  publish {"issue_key": "...", "requester_id": "..."}
│  (SNS topic)         │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  TicketEventHandler  │  thin pass-through; invokes the runtime
│       (Lambda)       │  with the issue key (no token handling)
└──────────┬───────────┘
           │
           ▼
┌─────────────────────────────────┐        ┌──────────────────────┐
│  AgentCore Runtime              │  MCP   │  AgentCore Gateway   │
│  (Strands agent in container)   │ ─────▶ │  inbound: Auth0 JWT  │
│  - @requires_access_token (M2M) │  Bearer│  4 Lambda targets    │
│    -> Auth0 access token        │        └──────────┬───────────┘
│  - @requires_access_token (3LO) │                   │
│    -> Atlassian access token    │       ┌───────────┴───────────┐
│  - aggregates tools from BOTH   │       │                       │
│    MCP servers into one Agent   │       ▼                       ▼
│  - writes Memory event          │       lookup_user,        query_kb ──▶ Bedrock KB
│  - comments + transitions Jira  │       get_process_info,                (OpenSearch
│    via Atlassian MCP            │       create_change_request            Serverless)
└──────────────┬──────────────────┘       (DynamoDB)
               │
               ▼ SSE
        ┌──────────────────────────────┐
        │ Atlassian Remote MCP server  │
        │ (mcp.atlassian.com/v1/sse)   │
        │ getJiraIssue / addComment /  │
        │ transitionIssue              │
        └──────────────────────────────┘
```

- **Trigger** : SNS event with a Jira issue key -> Lambda ->
  `InvokeAgentRuntime`. The Lambda is a thin pass-through; Jira is the
  system of record.
- **Identity**: two AgentCore Identity OAuth2 credential providers:
  - **Auth0 (CustomOauth2)** — M2M client_credentials. The Gateway uses
    a `CUSTOM_JWT` inbound authorizer pointed at the Auth0 OIDC
    discovery URL.
  - **Atlassian (AtlassianOauth2)** — 3LO authorization_code. The agent
    fetches its outbound Jira token via
    `@requires_access_token(auth_flow="USER_FEDERATION")`. AgentCore
    handles the OAuth dance internally; the agent never sees either
    client secret.
- **Tools** : 3 Lambda tools + 1 Knowledge-Base Lambda wrapper, all
  registered as Gateway Lambda targets. Plus the Atlassian MCP server's
  Jira tools, aggregated into the same Strands `Agent`.
- **Memory** : `CfnMemory` with a `summary_memory_strategy` named
  `incident_episodes` and namespace `incidents/{actorId}`. One event
  per issue; AgentCore rolls events into episodes per user.
- **State** : DynamoDB tables for `Users`, `Processes`, `ChangeRequests`.
  No local copy of Jira issues.
- **Observability**: AWS Distro for OpenTelemetry inside the runtime
  container — Strands and the MCP client are auto-instrumented. Spans +
  logs flow to a per-stack CloudWatch log group and surface in
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
6. **Atlassian Cloud site + Jira project** with at least one issue you
   can use for testing. See "Configure Jira" below.

## Configure Jira (Atlassian 3LO)

The agent reaches Jira through the Atlassian Remote MCP server at
`https://mcp.atlassian.com/v1/sse`. Authentication is OAuth 2.0 (3LO).

1. **Create the OAuth integration** at
   <https://developer.atlassian.com/console/myapps/> → "Create" → "OAuth
   2.0 integration".
2. **Add scopes** (Permissions → Jira API):
   - `read:me`
   - `read:jira-user`
   - `read:jira-work`
   - `write:jira-work`
   - `offline_access`
3. Copy **Client ID** and **Secret** into `.env`
   (`JIRA_OAUTH_CLIENT_ID` / `JIRA_OAUTH_CLIENT_SECRET`). The secret is
   loaded into AgentCore Identity at deploy time and never exposed to
   the runtime.
4. Set `JIRA_SITE_URL` to your Atlassian Cloud site
   (e.g. `https://your-tenant.atlassian.net`) and `JIRA_PROJECT_KEY` to
   the project where issues live.
5. **Add the callback URL after first deploy.** The stack output
   `JiraOauthCallbackUrl` is the redirect URI AgentCore Identity uses
   during the OAuth dance. After `cdk deploy`, copy that URL into the
   "Callback URL" field on the Atlassian OAuth app.

### One-time consent

Atlassian 3LO requires a real user to grant consent the first time the
agent runs. On the first invocation the runtime logs a warning like:

```
Atlassian consent required (one-time). Visit: https://auth.atlassian.com/authorize?...
```

Open that URL, log in as the Atlassian user the agent should act as,
approve the scopes — AgentCore Identity caches the refresh token and
all subsequent runs are non-interactive.

## Configure

```bash
cp .env.example .env
$EDITOR .env
```

Required keys:

| Key                         | Purpose                                                       |
| --------------------------- | ------------------------------------------------------------- |
| `STACK_NAME`                | CFN stack name. Resource prefix.                              |
| `AWS_REGION`                | Deploy region (e.g. `us-west-2`).                             |
| `AGENT_MODEL_ID`            | Bedrock model for the Strands agent.                          |
| `KB_EMBEDDING_MODEL_ID`     | Bedrock embedding model for the KB.                           |
| `AUTH0_DOMAIN`              | e.g. `your-tenant.us.auth0.com`.                              |
| `AUTH0_CLIENT_ID`           | M2M client ID.                                                |
| `AUTH0_CLIENT_SECRET`       | M2M client secret. Loaded into AgentCore Identity on deploy.  |
| `AUTH0_AUDIENCE`            | The Auth0 API Identifier.                                     |
| `JIRA_OAUTH_CLIENT_ID`      | Atlassian OAuth 2.0 (3LO) client ID.                          |
| `JIRA_OAUTH_CLIENT_SECRET`  | Atlassian client secret. Loaded into AgentCore Identity.      |
| `JIRA_SITE_URL`             | e.g. `https://your-tenant.atlassian.net`.                     |
| `JIRA_PROJECT_KEY`          | Project key for the issues the agent operates on (e.g. INC).  |

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

After the first deploy, copy the `JiraOauthCallbackUrl` output into the
Atlassian OAuth app's allowed-callback list (see "Configure Jira"
above).

Stack outputs you'll use:

| Output                 | Description                                  |
| ---------------------- | -------------------------------------------- |
| `TicketsTopicArn`      | SNS topic; publish `{issue_key}` events.     |
| `AgentRuntimeArn`      | AgentCore Runtime ARN.                       |
| `GatewayUrl`           | MCP endpoint of the AgentCore Gateway.       |
| `MemoryId`             | AgentCore Memory ID.                         |
| `KnowledgeBaseId`      | Bedrock KB ID.                               |
| `RuntimeLogGroupName`  | CloudWatch log group for runtime spans/logs. |
| `OtelServiceName`      | OTEL `service.name` of the runtime.          |
| `OnlineEvalConfigName` | Name of the online evaluation config.        |
| `JiraOauthProviderName`| AgentCore Identity provider for Atlassian.   |
| `JiraOauthCallbackUrl` | Redirect URI to add to the Atlassian app.    |

## Run an end-to-end demo

1. Create a real Jira issue in your project (any summary/description).
   Note the key — e.g. `INC-1042`.
2. Edit `seed-data/sample_ticket.json` to use that key + a real
   `requester_id` from `seed-data/users.json`.
3. Publish:

```bash
./scripts/publish_ticket.sh

# Tail the runtime logs while the agent runs
aws logs tail /aws/bedrock-agentcore/runtimes --follow --region us-west-2

# After ~30 seconds, check the resolved issue in Jira
./scripts/show_ticket.sh INC-1042
```

You should see the issue's status moved to a resolved state and a
resolution comment authored by the agent's Atlassian user.

### Custom events

Publish your own:

```bash
cat > /tmp/my-event.json <<'JSON'
{
  "issue_key": "INC-2099",
  "requester_id": "U-1002"
}
JSON

./scripts/publish_ticket.sh /tmp/my-event.json
```

Event schema:

| Field          | Type   | Notes                                                  |
| -------------- | ------ | ------------------------------------------------------ |
| `issue_key`    | string | Required. The Jira issue key (e.g. `INC-1042`).        |
| `requester_id` | string | Optional. Falls back to `issue_key` if not provided.   |

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
# DDB change-request rows
aws dynamodb scan --table-name <ChangeRequestsTable> --region $AWS_REGION

# AgentCore Memory events for a user
aws bedrock-agentcore list-events \
  --memory-id <MemoryId> \
  --actor-id U-1001 \
  --region $AWS_REGION

# Runtime logs
aws logs tail /aws/bedrock-agentcore/runtimes --since 10m --region $AWS_REGION

# The Jira issue itself
./scripts/show_ticket.sh INC-1042
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
- **Atlassian MCP returns 401 / `invalid_grant`.** The 3LO callback
  URL on the Atlassian app must exactly match `JiraOauthCallbackUrl`.
  If the consent flow was skipped, run the agent once interactively to
  pick up the consent URL from the runtime logs.
- **KB query returns no results.** First-time ingestion runs as part
  of deploy but completes asynchronously; wait ~2 minutes after the
  stack finishes, or re-run `StartIngestionJob` manually.
- **Build step times out.** The agent image is ARM64; CodeBuild ARM64
  is slower than x86. Bump `BuildTrigger`'s timeout in the stack if
  you hit it consistently.
