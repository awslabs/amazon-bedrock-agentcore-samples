# Event-Driven Claims Agent — AI Coding Assistant Context

> **For humans:** This file provides context for AI coding assistants (Kiro, Cursor, Claude Code, GitHub Copilot). For the human-readable documentation, see [docs/](./docs/README.md), [README.md](./README.md), or [docs/tutorial.md](./docs/tutorial.md).

This project is an **event-driven insurance claims processor** built on Amazon Bedrock AgentCore. It uses a dual-agent architecture (Claims Processor + Validation Agent) and deploys as a single CloudFormation stack (`AgentCore-ClaimsAgent-dev`) via the AgentCore CLI.

> **Important:** AgentCore resources (Runtime, Gateway, Memory, PolicyEngine, OnlineEval) are declared in `agentcore/agentcore.json` and managed by the AgentCore CLI. Supplementary infrastructure (DynamoDB, Lambda tools, SNS, S3, Cognito, EventBridge) is defined in the TypeScript CDK app at `agentcore/cdk/lib/infra-construct.ts`. Use `agentcore validate` and `agentcore dev` while iterating; run `agentcore deploy --target dev` to deploy everything together.

---

## Architecture

```
S3 upload (claims-inbox/)
  → EventBridge rule
    → Trigger Lambda (lambdas/trigger/handler.py)
        reads S3 object, gets Cognito M2M JWT, invokes Runtime via HTTPS
      → AgentCore Runtime (Container: app/claimsagent/)
          Phase 1: Claims Processor → lookup_policy → ACCEPT/REJECT decision
          Phase 2: Validation Agent → reviews decision → CONFIDENCE + ROUTING
          Phase 3: Execution → create_claim / human_review / send_notification
        → AgentCore Gateway (MCP, Cognito M2M auth, Cedar policy enforcement)
            → 6 Lambda tool functions (lambdas/<tool>/handler.py)
```

**Auth:** All callers use Cognito M2M JWT (`client_credentials` flow) — not SigV4.

---

## Directory Structure

```
event-driven-claims-agent/
├── AGENTS.md                          # This file
├── CLAUDE.md                          # Claude Code guidance
├── README.md                          # Full project documentation
├── deploy.sh                          # One-command deploy (runs CDK)
├── app/claimsagent/
│   ├── Dockerfile                     # Multi-stage, Python 3.12, ARM64
│   ├── main.py                        # All agent logic: prompts, agents, routing
│   ├── model/load.py                  # BedrockModel (global.anthropic.claude-sonnet-4-6)
│   ├── mcp_client/client.py           # Stub — MCPClient is configured in main.py
│   └── requirements.txt              # Add new runtime deps HERE (used by Dockerfile)
├── lambdas/                           # One directory per Gateway tool
│   ├── schemas/                       # MCP tool schemas (JSON) — matched by CDK
│   ├── trigger/handler.py             # EventBridge → Runtime invocation
│   ├── create_claim/handler.py        # DDB put on ClaimsTable
│   ├── policy_lookup/handler.py       # DDB get on PoliciesTable
│   ├── list_pending_claims/handler.py # DDB scan for pending_review claims
│   ├── resolve_claim/handler.py       # DDB update on ClaimsTable + ReviewsTable
│   ├── human_review/handler.py        # DDB put on ReviewsTable + SNS publish
│   └── notification/handler.py        # SES send email
├── agentcore/
│   ├── agentcore.json                 # Declarative AgentCore resources (Runtime/Gateway/Memory/PolicyEngine/Eval)
│   ├── aws-targets.json               # Deployment targets (account + region)
│   └── cdk/lib/
│       ├── infra-construct.ts         # Supplementary AWS infra (DynamoDB, S3, SNS, Cognito, EventBridge, Lambdas)
│       └── cdk-stack.ts               # Integration: wires infra ARNs + JWT authorizer + runtime env vars
├── scripts/
│   ├── deploy.sh                      # Deploy helper
│   ├── seed_dynamodb.py              # Populate test policies
│   ├── test_invoke.py                # Direct Runtime invocation (JWT auth)
│   ├── test_e2e.py                   # Full E2E test suite (5 scenarios)
│   ├── test_cedar.py                 # Cedar policy enforcement tests
│   ├── test_local.py                 # Local dev invocation helper
│   └── lint.sh                       # py_compile + ruff checks
├── docs/
│   ├── ARCHITECTURE.md               # System design and data flows
│   ├── deployment.md                 # Step-by-step deploy, verify, teardown
│   ├── decisions/                    # Architectural decision records (ADR-0001..0010)
│   └── CONFIGURATION.md             # All config surfaces reference
└── tests/
    └── sample-claim-email.txt        # Email for E2E test 5 (uses POL-67890)
```

---

## Build, Test, Deploy

### Deploy everything
```bash
./deploy.sh [region]          # defaults to us-west-2
```

This runs: configure target → npm install (CDK) → uv sync (agent) → `agentcore validate` → cdk bootstrap → `agentcore deploy --target dev` → seed DynamoDB → prints test commands.

### Manual AgentCore / CDK operations
```bash
agentcore validate                       # validate agentcore.json
agentcore deploy --target dev --yes      # deploy everything
agentcore destroy --target dev --yes     # tear down

# Drive the underlying TypeScript CDK directly:
cd agentcore/cdk && npm install && npx cdk diff
```

### Invoke the agent (requires deployed stack)
```bash
python3 scripts/test_invoke.py --region us-west-2
python3 scripts/test_invoke.py --region us-west-2 --prompt 'File a claim for POL-12345. $5000 storm damage.'
```

### Run E2E tests
```bash
python3 scripts/test_e2e.py --region us-west-2
python3 scripts/test_e2e.py --region us-west-2 --test 2   # Cedar block test
```

### Lint
```bash
./scripts/lint.sh
# or manually:
find app/ lambdas/ scripts/ -name "*.py" -exec python3 -m py_compile {} \;
```

---

## Key Invariants

1. **Lambda handlers return `json.dumps({...})` directly** — no `{statusCode, body}` envelope. The Gateway strips the HTTP wrapper.
2. **Agent routing controls claim status** — the `create_claim` Lambda accepts `status` and `decision` as optional parameters from the agent. Do not add routing logic to the Lambda itself.
3. **Tool schemas live in `lambdas/schemas/`** — each file maps to a Gateway target in the CDK stack via `ToolSchema.from_local_asset(...)`. Keep schemas in sync with Lambda parameters.
4. **Container build, not CodeZip** — runtime deps go in `app/claimsagent/requirements.txt`. The Dockerfile installs from this file.
5. **`agentcore/agentcore.json` is the source of truth for AgentCore resources** (Runtime, Gateway, Memory, PolicyEngine, OnlineEval). Supplementary AWS infra is in `agentcore/cdk/lib/infra-construct.ts`; `cdk-stack.ts` wires the two together (patches Lambda ARNs + the Gateway CUSTOM_JWT authorizer, injects runtime env vars). Don't hand-edit generated CDK output.

---

## Environment Variables

### Runtime container (set by CDK)
| Variable | Purpose |
|---|---|
| `AGENTCORE_GATEWAY_URL` | MCP Gateway HTTPS endpoint |
| `AGENTCORE_GATEWAY_TOKEN_ENDPOINT` | Cognito OAuth2 token URL |
| `AGENTCORE_GATEWAY_OAUTH_SCOPES` | `agentcore/invoke` |
| `AGENTCORE_GATEWAY_CLIENT_ID` | Cognito app client ID |
| `AGENTCORE_GATEWAY_CLIENT_SECRET` | Cognito app client secret |

### Lambda functions (set by CDK)
| Variable | Lambda(s) | Value |
|---|---|---|
| `CLAIMS_TABLE` | create_claim, list_pending, resolve_claim | `ClaimsAgent-Claims` |
| `POLICIES_TABLE` | policy_lookup | `ClaimsAgent-Policies` |
| `REVIEWS_TABLE` | human_review, resolve_claim | `ClaimsAgent-Reviews` |
| `REVIEW_SNS_TOPIC_ARN` | human_review | SNS topic ARN |
| `SENDER_EMAIL` | notification | SES verified sender |

### Trigger Lambda (set by CDK)
| Variable | Purpose |
|---|---|
| `AGENTCORE_RUNTIME_ARN` | Runtime ARN for HTTPS invocation |
| `COGNITO_USER_POOL_ID` | For M2M token retrieval |
| `COGNITO_CLIENT_ID` | M2M client |
| `COGNITO_CLIENT_SECRET` | M2M secret |
| `COGNITO_TOKEN_ENDPOINT` | OAuth2 token URL |

---

## Test Policies (seeded by `seed_dynamodb.py`)

| Policy Number | Holder | Type | Coverage | Status |
|---|---|---|---|---|
| `POL-12345` | John Smith | auto | $50,000 | active |
| `POL-67890` | Jane Doe | home | $250,000 | active |
| `POL-11111` | Bob Johnson | auto | $75,000 | active |

---

## Cedar Policies

Two policies (in `agentcore/agentcore.json` under `policyEngines`) enforce authorization at the Gateway:
- **AllowAllTools** — `permit(principal, action, resource is AgentCore::Gateway)`
- **BlockExcessiveClaims** — `forbid` when `context.toolName == "create-claim"` and `context.input.estimated_amount >= 100000`

Both use `IGNORE_ALL_FINDINGS` validation mode (required for the permit-all policy).
