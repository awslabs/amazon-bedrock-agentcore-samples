# Architecture Guide — Event-Driven Claims Processing Agent

## Overview

This document explains the requirements, architectural decisions, and rationale behind the event-driven insurance claims processing agent built on Amazon Bedrock AgentCore.

---

## Requirements

### From Stakeholder (Akarsha Sehwag, May 2026)

1. **Event-driven architecture** — Claims arrive via email (no frontend), processed asynchronously
2. **Deployment-ready** — Single command deploys everything, PR-ready for `agentcore-samples`
3. **All AgentCore primitives** — Runtime, Gateway, Memory, Identity, Observability, Evaluation, Policy Engine
4. **Dual-agent architecture** — Agent 1 (Claims Processor) + Agent 2 (Validation Agent)
5. **Human-in-the-loop** — Confidence-based routing: auto-approve vs. human review
6. **Email integration** — Claims arrive via email, responses sent via email
7. **Confidence-based routing** — Agent 2 scores confidence (≥80 auto-approve, <80 human review)
8. **Identity** — Cognito via Gateway (best practice)
9. **Cedar Policy Engine** — Authorization policies controlling tool access

---

## Architecture Decisions

### 1. CDK L2 Constructs (not AgentCore CLI)

**Decision:** Use `aws_cdk.aws_bedrockagentcore` (stable) + `aws_cdk.aws_bedrock_agentcore_alpha` (policy engine only)

**Rationale:**
- One `cdk deploy` creates everything (76 resources)
- No separate `agentcore deploy` step
- No `agentcore.json` configuration files
- CDK handles IAM wiring automatically (Runtime → Gateway, Gateway → Lambda targets)
- WorkloadIdentity auto-created by CDK for runtime-to-gateway auth
- Infrastructure as Code — fully reproducible, version-controlled
- Better for a code sample: shows AWS's own CDK constructs

**Trade-off:** Policy Engine is still ALPHA in CDK — could break with future CDK versions

### 2. Event-Driven Flow: S3 + EventBridge (not SES → Lambda directly)

**Decision:** Email → SES → S3 bucket → EventBridge rule → Trigger Lambda → Agent Runtime

**Rationale:**
- **Audit trail** — Emails persisted in S3 (compliance requirement for insurance)
- **Retry** — Re-process any claim by re-triggering from the S3 object
- **Idempotent** — Same S3 key = same claim (no duplicates)
- **Decoupled** — Can add more consumers later (analytics, fraud detection)
- **Content filtering** — EventBridge filters by S3 prefix (`claims-inbox/`)
- **Event replay** — Can reprocess historical claims from EventBridge archive

**Alternatives considered:**
- SES → Lambda directly: No audit trail, no retry, no dedup
- SES → SQS → Lambda: Ordering guarantees not needed, adds complexity
- SES → SNS → Lambda: Fire-and-forget, no persistence

### 3. Dual-Agent Architecture

**Decision:** Two sequential agents within a single AgentCore Runtime

**Rationale:**
- **Separation of concerns** — Processor makes decisions, Validator reviews them
- **Defense in depth** — Two independent assessments reduce error rate
- **Confidence scoring** — Validator assigns confidence independently of Processor
- **Fraud detection** — Validator cross-references data and flags inconsistencies
- **Human-in-the-loop** — Low confidence triggers human review automatically

**How it works:**
```
Phase 1: Claims Processor → ACCEPT/REJECT with reasoning
Phase 2: Validation Agent → CONFIDENCE score + ROUTING decision
Phase 3: Execution → create_claim + send_notification (or human_review)
```

### 4. Gateway Auth: Cognito M2M (not AWS_IAM, not NONE)

**Decision:** Gateway uses default Cognito M2M (auto-created by CDK Gateway construct)

**Rationale:**
- **Security** — MCP Gateway approves/creates insurance claims — cannot be unprotected
- **WorkloadIdentity** — CDK auto-wires runtime-to-gateway auth via Cognito client_credentials
- **Demonstrates Identity** — Shows full JWT + OAuth flow as required by stakeholder
- **Production-ready** — Real auth, not a demo shortcut

**Alternatives considered:**
- `NONE` — Insecure for a claims-processing gateway (rejected for security)
- `AWS_IAM` — Would work but doesn't demonstrate the Identity primitive
- `CUSTOM_JWT` with manual token plumbing — Complex, requires Trigger Lambda changes

### 5. Runtime Auth: Cognito JWT (inbound)

**Decision:** Runtime accepts JWT bearer tokens from Cognito User Pool

**Rationale:**
- **External callers** need authentication before invoking the agent
- **Trigger Lambda** gets M2M token from Cognito (client_credentials flow)
- **Demonstrates Identity** — Shows how to protect agent invocation
- **Standard OAuth 2.0** — Compatible with any OIDC provider

**Important:** Cannot use boto3 SDK with JWT-configured runtimes. Must use HTTPS with Bearer token.

### 6. Policy Engine: ALPHA CDK Construct (not post-deploy script)

**Decision:** Use `aws_cdk.aws_bedrock_agentcore_alpha.PolicyEngine` in CDK stack

**Rationale:**
- Everything in one `cdk deploy` — no post-deploy scripts
- Cedar policies reference `gateway.gateway_arn` directly (CDK resolves it)
- Shows the proper CDK integration pattern

**Cedar Policies:**
- `AllowAllTools` — Permits all tool actions on the gateway (with `IGNORE_ALL_FINDINGS` validation mode due to platform constraint)
- `BlockExcessiveClaims` — Forbids `create-claim` when `estimated_amount >= 100000`

**Known limitation:** `IGNORE_ALL_FINDINGS` validation mode is required for permit-all policies with specific gateway ARN. The platform rejects "overly permissive" policies without it.

### 7. Container Runtime: Finch (not Docker Desktop)

**Decision:** Use Amazon Finch for container builds (`CDK_DOCKER=finch`)

**Rationale:**
- Docker Desktop requires organization license (Amazon policy)
- Finch is open-source, free, and CDK-compatible
- ARM64 target platform (Graviton) built natively on Apple Silicon

### 8. Memory: SEMANTIC + SUMMARIZATION

**Decision:** Two built-in memory strategies

**Rationale:**
- **SEMANTIC** — Recalls relevant past interactions by meaning
- **SUMMARIZATION** — Maintains conversation summaries for context
- Both are built-in (no custom models needed)

### 9. Notification: SES with Branded HTML

**Decision:** Real email notifications via SES with styled HTML templates

**Rationale:**
- Professional presentation for a code sample
- Demonstrates real-world email integration
- SES sandbox is sufficient for demos (verified sender/recipient)

---

## Component Map

```
┌─────────────────────────────────────────────────────────────────┐
│                        CDK Stack (76 resources)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │ S3 Inbox │───▶│ EventBridge  │───▶│ Trigger Lambda (JWT)  │  │
│  └──────────┘    └──────────────┘    └───────────┬───────────┘  │
│                                                   │               │
│                                    ┌──────────────▼──────────┐   │
│                                    │   AgentCore Runtime     │   │
│                                    │   (Cognito JWT Auth)    │   │
│                                    │                          │   │
│                                    │  ┌─────────────────┐    │   │
│                                    │  │ Agent 1:        │    │   │
│                                    │  │ Claims Processor│    │   │
│                                    │  └────────┬────────┘    │   │
│                                    │           │              │   │
│                                    │  ┌────────▼────────┐    │   │
│                                    │  │ Agent 2:        │    │   │
│                                    │  │ Validator       │    │   │
│                                    │  └────────┬────────┘    │   │
│                                    │           │              │   │
│                                    │  ┌────────▼────────┐    │   │
│                                    │  │ Phase 3:        │    │   │
│                                    │  │ Execution       │    │   │
│                                    │  └─────────────────┘    │   │
│                                    └──────────────┬───────────┘   │
│                                                   │               │
│                          ┌────────────────────────▼──────────┐   │
│                          │   MCP Gateway (Cognito M2M Auth)  │   │
│                          │   + Policy Engine (Cedar)          │   │
│                          ├───────────────────────────────────┤   │
│                          │ ┌────────────┐ ┌──────────────┐   │   │
│                          │ │ policy-    │ │ create-claim │   │   │
│                          │ │ lookup     │ │              │   │   │
│                          │ └────────────┘ └──────────────┘   │   │
│                          │ ┌────────────┐ ┌──────────────┐   │   │
│                          │ │ human-     │ │ notification │   │   │
│                          │ │ review     │ │    (SES)     │   │   │
│                          │ └────────────┘ └──────────────┘   │   │
│                          │ ┌────────────┐ ┌──────────────┐   │   │
│                          │ │ list-      │ │ resolve-     │   │   │
│                          │ │ pending    │ │ claim        │   │   │
│                          │ └────────────┘ └──────────────┘   │   │
│                          └───────────────────────────────────┘   │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐   │
│  │ DynamoDB │  │ Cognito  │  │   SNS    │  │   Memory      │   │
│  │ (3 tables)│ │ User Pool│  │ (Review) │  │ (Semantic+Sum)│   │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘   │
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────────────────────────┐ │
│  │ Online Evaluation │  │ Custom Evaluator (LLM-as-Judge)     │ │
│  │ (3 built-in)      │  │ (on-demand only)                    │ │
│  └──────────────────┘  └──────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## AgentCore Primitives Demonstrated

| Primitive | Implementation | Status |
|-----------|---------------|--------|
| **Runtime** | Strands Agents, dual-agent, Cognito JWT, Graviton ARM64 | Stable CDK L2 |
| **Gateway** | MCP protocol, 6 Lambda targets, Cognito M2M, SEMANTIC search | Stable CDK L2 |
| **Identity** | Cognito JWT (inbound), WorkloadIdentity (outbound), M2M client_credentials | Stable CDK L2 |
| **Policy Engine** | Cedar: AllowAll + BlockExcessiveClaims ($100k threshold) | Alpha CDK L2 |
| **Memory** | SEMANTIC + SUMMARIZATION built-in strategies | Stable CDK L2 |
| **Observability** | X-Ray tracing, CloudWatch APPLICATION_LOGS | Stable CDK L2 |
| **Evaluation** | 3 built-in (Helpfulness, Correctness, Tool Selection) + custom LLM-as-judge | Stable CDK L2 |

---

## Known Limitations & Platform Behaviors

1. **Policy Engine name retention** — Deleted policy engines reserve their name for 24-48h
2. **Memory name retention** — Same behavior as policy engines
3. **Gateway auth immutability** — `authorizerType` cannot be changed after gateway creation
4. **Cedar permit-all requires IGNORE_ALL_FINDINGS** — Platform rejects "overly permissive" policies
5. **Runtime JWT auth requires HTTPS invocation** — Cannot use boto3 SDK (SigV4 incompatible)
6. **Container image required** — `from_asset()` needs Finch/Docker for ARM64 builds
7. **Streaming response format** — SSE chunks require client-side parsing
8. **Lambda timeout** — Agent processing takes 40-60s; Trigger Lambda needs 120s timeout

---

## Deployment

```bash
# Prerequisites: AWS CLI, CDK, Finch, Python 3.12+
./deploy.sh us-west-2
```

Single command creates all 76 resources. See README.md for full instructions.

---

## Testing

```bash
# Full E2E test suite (5 scenarios)
python3 scripts/test_e2e.py --region us-west-2

# Interactive agent invocation
python3 scripts/test_invoke.py --region us-west-2 --prompt 'Your claim here'
```

---

## Security Model

```
External Caller → [JWT Bearer Token] → Runtime
                                          ↓
Runtime → [Cognito M2M client_credentials] → Gateway
                                                ↓
Gateway → [Cedar Policy Engine] → Lambda Tools
```

- **Inbound auth:** Cognito JWT validates caller identity
- **Outbound auth:** WorkloadIdentity + M2M token for gateway access
- **Authorization:** Cedar policies control which tool calls are permitted
- **Data protection:** DynamoDB encryption at rest, S3 bucket policies, IAM least-privilege
