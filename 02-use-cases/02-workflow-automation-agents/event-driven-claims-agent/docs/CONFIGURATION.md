# Configuration Reference

AgentCore resources are declared in `agentcore/agentcore.json`; supplementary AWS infra is in `agentcore/cdk/lib/infra-construct.ts`. The deployed CloudFormation stack is named **`AgentCore-ClaimsAgent-dev`**. None of these are required to change for a basic deploy — defaults work out of the box.

## Deploy-time Parameters

| Parameter | How to set | Default | Notes |
|-----------|------------|---------|-------|
| `SENDER_EMAIL` | `export SENDER_EMAIL=...` before deploy | `noreply@example.com` | SES verified sender for notifications. `infra-construct.ts` reads `process.env.SENDER_EMAIL` at synth. Must be SES-verified or emails are logged as drafts, not sent. |
| Region | `./deploy.sh <region>` | `us-west-2` | Sets `AWS_REGION`/`CDK_DEFAULT_REGION`. |
| Model | `AGENT_MODEL_ID` runtime env | `global.anthropic.claude-sonnet-4-6` | Read by `app/claimsagent/config.py`. |

```bash
export SENDER_EMAIL=claims@yourcompany.com
agentcore deploy --target dev --yes
```

---

## Runtime Environment Variables

Injected into the Container runtime by CDK. All are set automatically on deploy.

| Variable | Source | Example Value |
|----------|--------|---------------|
| `AGENTCORE_GATEWAY_URL` | CDK `gateway.gateway_url` | `https://xxx.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp` |
| `AGENTCORE_GATEWAY_TOKEN_ENDPOINT` | CDK Cognito domain | `https://claims-agent-{account}.auth.us-west-2.amazoncognito.com/oauth2/token` |
| `AGENTCORE_GATEWAY_OAUTH_SCOPES` | Hardcoded in CDK | `agentcore/invoke` |
| `AGENTCORE_GATEWAY_CLIENT_ID` | CDK `app_client.user_pool_client_id` | (Cognito client ID) |
| `AGENTCORE_GATEWAY_CLIENT_SECRET` | CDK `app_client.user_pool_client_secret.unsafe_unwrap()` | (Cognito client secret) |

For local development, copy `.env.example` to `.env` and fill in values from your deployed stack:
```bash
cp .env.example .env
# Then fill in values from: aws cloudformation describe-stacks --stack-name AgentCore-ClaimsAgent-dev
```

---

## Lambda Environment Variables

### ClaimsAgent-PolicyLookup
| Variable | Value |
|----------|-------|
| `POLICIES_TABLE` | `ClaimsAgent-Policies` |

### ClaimsAgent-CreateClaim
| Variable | Value |
|----------|-------|
| `CLAIMS_TABLE` | `ClaimsAgent-Claims` |

### ClaimsAgent-HumanReview
| Variable | Value |
|----------|-------|
| `REVIEWS_TABLE` | `ClaimsAgent-Reviews` |
| `REVIEW_SNS_TOPIC_ARN` | SNS topic ARN (from CDK) |

### ClaimsAgent-Notification
| Variable | Value |
|----------|-------|
| `SENDER_EMAIL` | CDK context `sender_email` or `noreply@example.com` |

### ClaimsAgent-ListPending
| Variable | Value |
|----------|-------|
| `CLAIMS_TABLE` | `ClaimsAgent-Claims` |

### ClaimsAgent-ResolveClaim
| Variable | Value |
|----------|-------|
| `CLAIMS_TABLE` | `ClaimsAgent-Claims` |
| `REVIEWS_TABLE` | `ClaimsAgent-Reviews` |

### ClaimsAgent-Trigger
| Variable | Value |
|----------|-------|
| `AGENTCORE_RUNTIME_ARN` | Runtime ARN (from CDK) |
| `COGNITO_USER_POOL_ID` | User pool ID (from CDK) |
| `COGNITO_CLIENT_ID` | App client ID (from CDK) |
| `COGNITO_CLIENT_SECRET` | App client secret (from CDK) |
| `COGNITO_TOKEN_ENDPOINT` | Cognito OAuth2 token URL |

---

## Cedar Policies

Cedar policies are declared in `agentcore/agentcore.json` under `policyEngines[0].policies`. Each policy is a `{ name, description, statement, validationMode }` object.

---

## MCP Tool Schema Format

Tool schemas in `lambdas/schemas/` define the contract between the MCP Gateway and each Lambda tool. The Gateway uses these schemas for tool discovery (semantic search matches against `description`) and input validation.

**Format:** Each file is a JSON array containing one tool object:

```json
[{
  "name": "tool-name",
  "description": "Human-readable description of what this tool does. The Gateway uses this for semantic search.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "param_name": { "type": "string", "description": "What this parameter is for" }
    },
    "required": ["param_name"]
  }
}]
```

**How it's wired:**
1. Schema file lives at `lambdas/schemas/<tool_name>.json`
2. `agentcore/agentcore.json` references it via `toolSchemaFile: "lambdas/schemas/<tool_name>.json"`
3. CDK loads it via `ToolSchema.from_local_asset(...)` during synthesis
4. The Gateway registers the tool with its name, description, and input schema
5. The agent discovers tools via semantic search (matching the `description` field)

**Important:** The Lambda handler's expected parameters must match the schema's `properties`. If you add a field to the schema, the Lambda must handle it. If you rename a field in the Lambda, update the schema to match.

---

### Policy 1: AllowAllTools

```cedar
permit(principal, action, resource is AgentCore::Gateway);
```

Grants all authenticated principals the ability to call any tool on the claims gateway. Uses `IGNORE_ALL_FINDINGS` validation mode.

### Policy 2: BlockExcessiveClaims

```cedar
forbid(principal, action, resource is AgentCore::Gateway)
when {
    context has "toolName" && context.toolName == "create-claim"
    && context has "input" && context.input has "estimated_amount"
    && context.input.estimated_amount >= 100000
};
```

Blocks `create-claim` tool calls when the estimated amount is ≥$100,000.

### Adding a New Policy

Add an entry to `policyEngines[0].policies` in `agentcore/agentcore.json`:

```json
{
  "name": "MyPolicyName",
  "description": "Description of what this policy does",
  "statement": "forbid(principal, action, resource is AgentCore::Gateway) when { context has \"toolName\" && context.toolName == \"my-tool\" };",
  "validationMode": "IGNORE_ALL_FINDINGS"
}
```

Then `agentcore validate && agentcore deploy --target dev --yes`.

### Policy Engine Mode

The gateway references the policy engine via `policyEngineConfiguration.mode` (set to `ENFORCE` in `agentcore.json`). In `ENFORCE` mode, Cedar denials block the tool call before it runs. Switch `mode` to `MONITOR` to observe and log policy decisions without blocking — handy while authoring new policies.

---

## Cognito Configuration

### User Pool: `ClaimsAgent-UserPool`

| Setting | Value |
|---------|-------|
| Name | `ClaimsAgent-UserPool` |
| Removal policy | `DESTROY` (deleted on `cdk destroy`) |
| Domain prefix | `claims-agent-{account}` |

### Resource Server

| Setting | Value |
|---------|-------|
| Identifier | `agentcore` |
| Scopes | `agentcore/invoke` |

### App Client: `ClaimsAgent-M2M`

| Setting | Value |
|---------|-------|
| Name | `ClaimsAgent-M2M` |
| Flow | `client_credentials` (machine-to-machine) |
| Secret | Auto-generated |
| Allowed scopes | `agentcore/invoke` |

### Token Endpoint

```
https://claims-agent-{account}.auth.{region}.amazoncognito.com/oauth2/token
```

### Obtaining a Token (for testing)

```python
import base64, json, urllib.parse, urllib.request

creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
data = urllib.parse.urlencode({
    "grant_type": "client_credentials",
    "scope": "agentcore/invoke",
}).encode()

req = urllib.request.Request(
    token_endpoint,
    data=data,
    headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {creds}",
    },
)
with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read())["access_token"]
```

See `scripts/get_token.py` for a ready-to-use script.

---

## SES Setup

The notification Lambda uses SES to send emails. SES is in sandbox mode by default.

### Sandbox Mode (default)

In sandbox mode, SES can only send to verified email addresses. To verify an address:

```bash
aws ses verify-email-identity --email-address your@email.com --region us-west-2
```

Click the verification link in the email. Then redeploy with the verified sender:

```bash
export SENDER_EMAIL=your@email.com
agentcore deploy --target dev --yes
```

### Production Mode

To send to any address, request SES production access:
1. Go to SES console → Account dashboard → Request production access
2. Fill in the use case form
3. Wait for AWS approval (typically 24-48 hours)

### SES IAM Permissions

The notification Lambda is granted:
```
ses:SendEmail
ses:SendRawEmail
arn:aws:ses:{region}:{account}:identity/*
```

This scopes permissions to identities in the deploying account, not `*`.

---

## Bedrock Model Access

The Runtime needs access to the Bedrock model specified in `app/claimsagent/model/load.py`.

### Default Model

```
global.anthropic.claude-sonnet-4-6
```

This is a cross-region inference profile that automatically routes to the nearest available region.

### Enable Model Access

1. Go to **Bedrock console** → **Model access** → **Manage model access**
2. Enable **Claude Sonnet** (Anthropic)
3. Click **Save changes**

Available in: us-east-1, us-west-2, eu-west-1, ap-northeast-1 (check console for current list).

### IAM Permissions

The Runtime role is granted:
```json
{
  "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
  "Resource": [
    "arn:aws:bedrock:{region}::foundation-model/anthropic.claude-sonnet-4-6",
    "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-6",
    "arn:aws:bedrock:*:*:inference-profile/*"
  ]
}
```

### Changing the Model

Preferred: set the `AGENT_MODEL_ID` environment variable on the Runtime (in `agentcore/agentcore.json` → `runtimes[0].envVars`), then redeploy:

```bash
agentcore deploy --target dev --yes
```

`app/claimsagent/model/load.py` reads `AGENT_MODEL_ID` (via `config.py`), so no code change is needed.

---

## Memory Configuration

Memory is declared in `agentcore/agentcore.json` under `memories`:

```json
{
  "name": "ClaimsAgentMemory",
  "eventExpiryDuration": 90,
  "strategies": [
    { "type": "SEMANTIC", "name": "semantic_strategy", "namespaces": ["claims/{actorId}/facts"] },
    { "type": "SUMMARIZATION", "name": "summary_strategy", "namespaces": ["claims/{actorId}/{sessionId}"] }
  ]
}
```

| Setting | Value | Notes |
|---------|-------|-------|
| Expiration | 90 days | Adjust `eventExpiryDuration` |
| SEMANTIC | enabled | Fact/concept retrieval across sessions |
| SUMMARIZATION | enabled | Session compression for repeat claimants |

### Disabling Memory

Remove the `memories` entry (or unset `MEMORY_ID`). The Runtime degrades gracefully — `app/claimsagent/memory/session.py` returns `None` when `MEMORY_ID` is unset, and `main.py` wraps the session manager in try/except.

---

## Online Evaluation

Configured in `agentcore/agentcore.json` under `onlineEvalConfigs`:

```json
{
  "name": "ClaimsEvaluation",
  "agent": "claimsagent",
  "evaluators": ["Builtin.Helpfulness", "Builtin.Correctness", "Builtin.ToolSelectionAccuracy"],
  "samplingRate": 100,
  "description": "Online evaluation for claims agent (3 built-in metrics)"
}
```

A custom LLM-as-judge evaluator (`ClaimsQualityEvaluator`) is also declared under `evaluators` for on-demand use.

| Setting | Value | Notes |
|---------|-------|-------|
| Sampling | 100% | Every invocation is evaluated. Reduce for cost savings in production. |
| Built-in metrics | 3 | Helpfulness, Correctness, Tool Selection Accuracy |
| Custom evaluator | LLM-as-judge | Defined separately (`ClaimsQualityEvaluator`). Use for on-demand evaluation only — requires reference inputs not available online. |

### Valid Built-in Evaluator IDs

| ID | What it measures |
|----|-----------------|
| `HELPFULNESS` | Whether the response helps the user |
| `CORRECTNESS` | Whether the response is factually accurate |
| `TOOL_SELECTION_ACCURACY` | Whether the right tools were chosen at the right time |
| `GOAL_SUCCESS_RATE` | Whether the agent achieved its stated goal |

**Tip:** Use the exact IDs above — the tool-selection metric is `ToolSelectionAccuracy`.

### Prerequisites

Online Evaluation requires CloudWatch Transaction Search to be enabled in your region:
1. Go to **CloudWatch console** → **Settings** → **Transaction Search**
2. Enable Transaction Search
3. Then deploy the stack

---

## Deploying to a Different Region

```bash
./deploy.sh us-east-1
```

The deploy script sets `CDK_DEFAULT_REGION`, `AWS_DEFAULT_REGION`, and `AWS_REGION` automatically.

**Note:** Ensure the Bedrock model (`global.anthropic.claude-sonnet-4-6`) is available in your target region. The global inference profile handles cross-region routing automatically.
