# Deployment Guide

## Quick Deploy (One Command)

```bash
./deploy.sh us-west-2
```

This runs all steps below automatically and seeds test data. When complete, you'll see:

```
✅ Done! Claims Agent deployed to us-west-2

📋 Test with:
   python3 scripts/test_invoke.py --region us-west-2

🛡️  Test Cedar policy (should block $100k+ claims):
   python3 scripts/test_invoke.py --region us-west-2 --prompt 'File a claim for POL-12345. Car totaled. $150000 damage.'

🧪 Local dev:
   agentcore dev --no-browser
```

If the deploy fails at any step, see [Troubleshooting](#troubleshooting) below.

---

## Manual Step-by-Step Deployment

### 1. Clone and Navigate

```bash
git clone <repository-url>
cd event-driven-claims-agent
```

### 2. Configure AWS Targets

Create `agentcore/aws-targets.json` with your account and region:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=us-west-2

cat > agentcore/aws-targets.json <<EOF
[
  {
    "name": "dev",
    "account": "$ACCOUNT_ID",
    "region": "$REGION"
  }
]
EOF
```

### 3. Install CDK Dependencies

```bash
cd agentcore/cdk
npm install
cd ../..
```

### 4. Install Agent Dependencies

```bash
cd app/claimsagent
uv venv
uv sync
cd ../..
```

If `uv` is not available:
```bash
cd app/claimsagent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ../..
```

### 5. Validate Configuration

```bash
agentcore validate
```

This checks `agentcore/agentcore.json` for syntax and schema errors.

### 6. Bootstrap CDK (First-Time Only)

```bash
cdk bootstrap aws://<account-id>/<region>
```

Example:
```bash
cdk bootstrap aws://123456789012/us-west-2
```

### 7. Deploy

**Option A: Using AgentCore CLI (Recommended)**

```bash
agentcore deploy --target dev --yes
```

This deploys both the AgentCore resources (Runtime, Gateway, Memory, PolicyEngine, OnlineEval) and the supplementary infrastructure (DynamoDB, Lambda, SNS, S3, Cognito, EventBridge) via CDK.

**Option B: Using deploy.sh**

```bash
./deploy.sh us-west-2
```

Sets environment variables, validates, bootstraps, deploys, and seeds data.

### 8. Seed DynamoDB with Test Data

```bash
python3 scripts/seed_dynamodb.py --region us-west-2
```

Creates three test policies:
- `POL-12345` — John Smith, auto, $50,000 coverage
- `POL-67890` — Jane Doe, home, $250,000 coverage
- `POL-11111` — Bob Johnson, auto, $75,000 coverage

### 9. Verify Deployment

**Test with a simple claim:**

```bash
python3 scripts/test_invoke.py --region us-west-2
```

Expected output (abbreviated):

```
🔑 Authenticating...
✅ Connected to claimsagent
📝 I need to file a claim. My policy is POL-12345. Fender bender yesterday, $2000 damage.

━━━ Agent Response ━━━

## Phase 1: Claims Processing
[Agent calls lookup_policy, verifies POL-12345 is active with $50k auto coverage]
DECISION: ACCEPT
AMOUNT: 2000
POLICY: POL-12345
...

---
## Phase 2: Validation & Routing
CONFIDENCE: 92
ROUTING: AUTO_APPROVE
...

---
## Phase 3: Execution
**Auto-approved** (confidence: 92/100)
[Agent calls create_claim and send_notification]

━━━━━━━━━━━━━━━━━━━━━
```

> **Note:** The exact wording varies between runs (LLM output is non-deterministic), but the structure (3 phases, DECISION, CONFIDENCE, ROUTING) is consistent.

**Test Cedar policy enforcement (should block — $150k exceeds the $100k threshold):**

```bash
python3 scripts/test_invoke.py --region us-west-2 --prompt 'File a claim for POL-12345. Car totaled. $150000 damage.'
```

Expected: The agent will try to call `create_claim` but receive an authorization error from the Cedar policy engine. It will then route to human review instead of creating the claim directly.

**Test with a custom prompt:**

```bash
python3 scripts/test_invoke.py --region us-west-2 --prompt 'File a claim for POL-12345. Storm damage. $5000.'
```

**Run full E2E test suite:**

```bash
python3 scripts/test_e2e.py --region us-west-2
```

This runs 5 test scenarios:
1. Auto-approved claim (high confidence) — expects `create_claim` called successfully
2. Cedar-blocked claim (>=$100k) — expects authorization denied on `create_claim`
3. Human review claim (low confidence) — expects `request_human_review` called
4. Rejected claim (policy not found) — expects `send_notification` with rejection
5. Email-format claim (S3 + EventBridge path) — expects full event-driven pipeline

Run a single test:

```bash
python3 scripts/test_e2e.py --region us-west-2 --test 2
```

### 10. Teardown

**Destroy all resources:**

```bash
agentcore destroy --target dev --yes
```

Or manually:

```bash
cd agentcore/cdk
cdk destroy --all --force
```

**Note:** S3 buckets and DynamoDB tables are configured with `removalPolicy: DESTROY` and `autoDeleteObjects: true` for development. They will be deleted on stack teardown.

---

## Local Development

Run the agent locally while tools, auth, and data stay in the cloud.

### What runs where

| Component | Local | Cloud |
|-----------|-------|-------|
| Agent logic (main.py) | ✅ Local process on :8080 | — |
| MCP Gateway + Cedar | — | ✅ Deployed stack |
| Lambda tools | — | ✅ Deployed stack |
| DynamoDB tables | — | ✅ Deployed stack |
| Cognito auth | — | ✅ Deployed stack |

**Key insight:** You must deploy the stack first. Local dev runs only your agent code — tool calls still go to the cloud Gateway.

### Setup

1. Deploy the full stack (if not already done):
   ```bash
   ./deploy.sh us-west-2
   ```

2. Get connection values from the deployed stack:
   ```bash
   aws cloudformation describe-stacks \
     --stack-name AgentCore-ClaimsAgent-dev \
     --query 'Stacks[0].Outputs' \
     --region us-west-2 \
     --output table
   ```

3. Create your `.env` file:
   ```bash
   cp .env.example .env
   ```
   Fill in values from the CloudFormation outputs:
   ```
   AGENTCORE_GATEWAY_URL=https://xxx.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp
   AGENTCORE_GATEWAY_TOKEN_ENDPOINT=https://claims-agent-XXXXXX.auth.us-west-2.amazoncognito.com/oauth2/token
   AGENTCORE_GATEWAY_CLIENT_ID=<from outputs>
   AGENTCORE_GATEWAY_CLIENT_SECRET=<from outputs>
   AGENTCORE_GATEWAY_OAUTH_SCOPES=agentcore/invoke
   ```

4. Start the local dev server:
   ```bash
   agentcore dev --no-browser
   ```
   Expected output:
   ```
   🚀 Starting local development server...
   ✅ Runtime available at http://localhost:3000
   👀 Watching for file changes...
   ```

5. Test against local:
   ```bash
   python3 scripts/test_local.py
   ```
   Or use curl directly:
   ```bash
   curl -X POST http://localhost:3000/invocations \
     -H "Content-Type: application/json" \
     -d '{"prompt": "File a claim for POL-12345. $3000 windshield damage."}'
   ```

### Iterating on prompts

The fastest way to tune agent behavior without redeploying:

1. Edit `PROCESSOR_PROMPT` or `VALIDATOR_PROMPT` in `app/claimsagent/main.py`
2. The dev server detects the change and reloads automatically
3. Re-run your test command
4. Observe the behavior change in the response
5. Repeat until satisfied
6. When ready, deploy: `agentcore deploy --target dev --yes`

No container rebuild needed during local dev — only when deploying to the cloud.

### When to redeploy vs. iterate locally

| Change | Local iteration | Requires redeploy |
|--------|----------------|-------------------|
| Agent prompts | ✅ | — |
| Routing logic (main.py) | ✅ | — |
| New Python dependency | — | ✅ (Dockerfile rebuild) |
| New Lambda tool | — | ✅ (CDK creates Lambda) |
| Cedar policy change | — | ✅ (agentcore.json) |
| DynamoDB schema change | — | ✅ (CDK infra) |

---

## Troubleshooting

### CDK Bootstrap Failed

If `cdk bootstrap` fails with "Stack already exists":

```bash
cdk bootstrap aws://<account>/<region> --force
```

### Container Build Failed

Check Docker/Finch is running:

```bash
docker info
# or
finch version
```

Set the container runtime explicitly:

```bash
export CDK_DOCKER=finch
./deploy.sh us-west-2
```

### Bedrock Model Access Denied

Enable Claude Sonnet in Bedrock console:
1. Go to **Bedrock console** → **Model access**
2. Click **Manage model access**
3. Enable **Claude Sonnet (Anthropic)**
4. Click **Save changes**

### Lambda Function Not Found

If tools fail with "Function not found", verify IAM permissions on Lambda ARNs in the Gateway configuration. Re-deploy:

```bash
agentcore deploy --target dev --yes
```

### SES Email Not Sending

In SES sandbox mode, verify sender and recipient emails:

```bash
aws ses verify-email-identity --email-address your@email.com --region us-west-2
```

Check the verification link in the email, then redeploy with a verified sender (the notification Lambda reads `SENDER_EMAIL`, set from the `SENDER_EMAIL` shell variable at deploy time):

```bash
export SENDER_EMAIL=your@email.com
agentcore deploy --target dev --yes
```

To exit sandbox mode, request production access in the SES console.

---

## Multi-Region Deployment

Deploy to a different region:

```bash
./deploy.sh us-east-1
```

Or manually:

```bash
export AWS_REGION=us-east-1
export CDK_DEFAULT_REGION=us-east-1
agentcore deploy --target dev --yes
```

**Note:** Ensure the Bedrock model (`global.anthropic.claude-sonnet-4-6`) is available in your target region. The global inference profile automatically routes to the nearest available region.
