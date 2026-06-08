<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Threat Model

This document is the security analysis for the OpenCode on Amazon Bedrock AgentCore sample. It enumerates trust boundaries, data flows, STRIDE threats per component, GenAI-specific threats, and the residual risks the sample accepts by design. Pair it with [docs/ARCHITECTURE.md](ARCHITECTURE.md) for the component walkthrough and [docs/HARDENING.md](HARDENING.md) for the concrete controls a production adopter is expected to add.

---

## Purpose and scope

This threat model exists to:

- Make the security posture of the sample reviewable in one document.
- Map every credible threat to a concrete control, a residual-risk acknowledgement, or a customer responsibility.
- Give production adopters a starting checklist rather than a hand-wave.

In scope: everything synthesized by the nine CDK stacks plus the container image built from [`container/`](../container/). Out of scope: the AWS services that the sample integrates with (Amazon Bedrock AgentCore, Amazon Bedrock, AWS KMS, Amazon Cognito, AWS Secrets Manager, Amazon DynamoDB, Amazon CloudWatch, Amazon S3, Amazon ECR, AWS Lambda, Amazon API Gateway, Amazon VPC) are assumed to operate as documented. GitHub is a third-party dependency.

## Assumptions

The threat model is only as good as the assumptions under it. These are the assumptions we rely on; each one is an explicit invitation for reviewers to push back.

1. **AWS infrastructure is trustworthy.** AWS services enforce the controls AWS documents. KMS encrypts what we tell it to encrypt, CloudTrail logs what we tell it to log, and so on.
2. **The customer's AWS account is not compromised.** The root of trust is the account boundary. A compromised account operator can bypass every control the sample adds.
3. **The deployer reviews and approves the template before `cdk deploy`.** This is a sample repository, not a managed service. Customers read the code.
4. **Upstream package and binary integrity is out of scope.** Python packages from PyPI via `container/requirements.txt`, OpenCode from the upstream installer, and base container images from the public Docker registry are trusted to be what they claim. Production adopters are expected to pin exact versions (already called out in HARDENING.md) and layer on whatever supply-chain controls they need.
5. **Cognito users are provisioned by a trusted operator.** `self_sign_up_enabled=False` and the user pool is operator-managed. We do not model the case where a malicious user is admitted.
6. **The MCP client is trusted.** If the client is compromised, nothing about this sample's defences protects the user. Clients are documented with config guidance in [docs/MCP-CLIENTS.md](MCP-CLIENTS.md).
7. **GitHub enforces its own access controls.** Repo-level access is enforced by the git provider via the user's OAuth token, not by this sample.

## System overview

See [docs/ARCHITECTURE.md](ARCHITECTURE.md) for the full component walkthrough and sequence diagrams. For the threat model, the relevant top-level flow is:

```
MCP Client
   │   (Cognito JWT, Authorization header)
   ▼
Amazon Bedrock AgentCore Gateway
   │   (JWT validated by Gateway; Cedar policy evaluated)
   │   (REQUEST interceptor extracts user_id; strips inbound Authorization header)
   │   (SigV4 signed with GATEWAY_IAM_ROLE)
   ▼
Amazon Bedrock AgentCore Runtime (per-session Firecracker microVM)
   │   FastMCP server :8000
   │   5-step pipeline: credential resolve → clone → OpenCode → scan → push
   │
   ├──► Amazon Bedrock (LLM inference)
   ├──► GitHub (clone, push, create PR; over NAT Gateway)
   ├──► Amazon DynamoDB (audit records; KMS-encrypted)
   ├──► AWS Secrets Manager (AgentCore Identity token vault; KMS-encrypted)
   └──► Amazon CloudWatch Logs (KMS-encrypted)

OAuth 3LO flow (out-of-band):
User's browser ─► GitHub ─► API Gateway HTTP API ─► Callback Lambda ─► AgentCore Identity
                                   │
                                   └─ HttpLambdaAuthorizer validates query-string shape
```

## Data inventory and sensitivity

| Data | Where it lives | Sensitivity | Encrypted at rest | Encrypted in transit |
|------|----------------|-------------|-------------------|----------------------|
| Cognito ID tokens (JWTs) | MCP client config, HTTP headers | Medium (24 h TTL) | Client's responsibility | TLS (client → Gateway) |
| OAuth app credentials (GitHub client secret) | AWS Secrets Manager | High | Customer-managed CMK | TLS (Secrets Manager SDK) |
| User OAuth refresh tokens | AgentCore Identity Vault (`bedrock-agentcore-identity*` secrets) | High | AWS-owned key by default; CMK configurable | TLS (AgentCore Identity SDK) |
| User OAuth access tokens (in-flight) | Runtime microVM memory, `GIT_ASKPASS` sidecar file (mode `0o400`) | High | In-memory only; sidecar removed in `finally` block | N/A (local) |
| Coding task description | HTTP request, Runtime memory, Bedrock prompts, DynamoDB is not written with this (only status fields) | Medium (may contain user PII or repo info) | AgentCore session encryption (Bedrock) | TLS |
| Cloned repository contents | Runtime microVM ephemeral filesystem (managed session storage in supported regions) | High (customer code) | AgentCore session storage default encryption | TLS (git over HTTPS) |
| LLM output (generated code + commentary) | Runtime microVM memory; pushed to GitHub after credential scan | Medium | N/A (transient) | TLS (git push) |
| DynamoDB audit records | `opencode-jobs` table | Low/Medium (user_id, job_id, status, timestamps, runtime_session_id; no task description, no repo contents) | Customer-managed CMK | TLS |
| CloudWatch Logs (Runtime, Gateway interceptor, Lambdas) | `/opencode/*` log groups | Medium (may contain user_id, repo URL, error traces) | Customer-managed CMK | TLS |
| CloudTrail events (optional) | Customer-managed S3 bucket | High (audit log) | Customer-managed CMK | TLS |

## Trust boundaries

1. **Account boundary** - everything inside the customer's AWS account. Actor: customer operator. Boundary controls: AWS account authentication, IAM.
2. **Inbound MCP boundary** - between the untrusted public internet and the Gateway. Boundary controls: Amazon Bedrock AgentCore Gateway's JWT authorizer (`CustomJwtAuthorizer`), Cedar Policy Engine (LOG_ONLY by default, switchable to ENFORCE), TLS.
3. **Gateway → Runtime boundary** - between the Gateway and the Runtime microVM. Boundary controls: SigV4 with `GATEWAY_IAM_ROLE`, REQUEST interceptor Lambda ([`lambda/interceptor/index.py`](../lambda/interceptor/index.py)) strips inbound `Authorization` header, injects `_user_id` from the validated JWT `sub` claim.
4. **Per-session microVM boundary** - each Runtime invocation runs in its own Firecracker microVM with an ephemeral filesystem. Boundary controls: AgentCore Runtime session isolation.
5. **OpenCode subprocess boundary** - the OpenCode binary runs as a child process of the FastMCP server inside the microVM. Boundary controls: process isolation, explicit environment sanitization, validated absolute path to the binary ([`container/tools/run_opencode_acp.py`](../container/tools/run_opencode_acp.py) `_validate_opencode_binary`), startup-time fail-fast.
6. **OAuth callback boundary** - between the user's browser (coming back from GitHub) and the callback Lambda. Boundary controls: HTTP API Gateway with an `HttpLambdaAuthorizer` ([`stacks/callback_api_stack.py`](../stacks/callback_api_stack.py)) that validates `session_id` shape and `state`-JSON structure; TLS.
7. **VPC egress boundary** - Runtime outbound traffic leaves the VPC through the NAT Gateway (or through VPC endpoints for AWS services). Boundary controls: security group egress limited to TCP/443; VPC endpoints for AWS services; **FQDN-level egress filtering is a documented residual risk** (see [docs/HARDENING.md#known-limitations](HARDENING.md#known-limitations)).
8. **Bedrock inference boundary** - LLM prompts and responses cross into the Bedrock service plane. Boundary controls: IAM scoped to specific model ARNs in [`stacks/agentcore_stack.py`](../stacks/agentcore_stack.py); Bedrock's upstream content filters and safety controls.

## Actors and assets

| Actor | Trust | Primary assets they touch |
|-------|-------|----------------------------|
| End user (via MCP client) | Semi-trusted (authenticates via Cognito, scoped by Cedar) | Coding task description, OAuth consent, git repo they own |
| Customer operator | Trusted (root in the account) | All AWS resources, CMK, Cedar policies, Cognito users |
| MCP client (Kiro, Claude Desktop, Cursor) | As trusted as the user running it | JWT, MCP traffic |
| GitHub (third party) | External (assumed to enforce its own access controls) | Clone payloads, push targets, OAuth tokens |
| Amazon Bedrock model (LLM) | Semi-trusted (pre-approved model, but output must be treated as untrusted) | Task descriptions (prompts), generated code (output) |
| OpenCode binary | Semi-trusted (installed at build time from upstream; executes LLM output in a microVM) | File system in `work_dir`, LLM-generated edit instructions |
| Attacker on the public internet | Hostile | May attempt: Gateway endpoint enumeration, OAuth callback replay, token theft via phishing |
| Attacker in a compromised MCP client | Hostile | Has the user's JWT; model this as the user |

## STRIDE analysis

Per-component threat → control mapping. The control either (a) mitigates the threat, (b) is a residual risk with an explicit acknowledgement, or (c) is a customer responsibility called out here and in HARDENING.md.

### 1. MCP Client → Gateway

| ID | STRIDE | Threat | Control |
|----|--------|--------|---------|
| MC-S | Spoofing | Attacker presents a forged JWT | Gateway validates JWT signature/issuer/audience via `CustomJwtAuthorizer` bound to the Cognito user pool. Cognito uses RS256; forgery requires the private key held by AWS. |
| MC-T | Tampering | Attacker modifies MCP request in transit | TLS between client and Gateway. Gateway validates the full request before forwarding. |
| MC-R | Repudiation | User denies submitting a task | Every tool call is attributed to the JWT `sub` claim (`_user_id` injected by the interceptor) and recorded in DynamoDB with timestamps. Optional CloudTrail captures the API-level event. |
| MC-I | Information disclosure | JWT is exfiltrated from the client | JWT TTL is 24 h. Client-side storage is documented in MCP-CLIENTS.md; "Option A" (auto-refresh wrapper) avoids on-disk storage. **Residual risk**: if the client is compromised, the attacker can act as the user for 24 h. Mitigated operationally by rotating Cognito user credentials. |
| MC-D | Denial of service | Attacker floods the Gateway | AgentCore Gateway handles service-level rate limiting. **Customer responsibility**: add WAF rules if the Gateway is exposed to the public internet. |
| MC-E | Elevation of privilege | Low-privilege role invokes a high-privilege tool | Cedar policies bound to `opencode___{tool}` action ARNs; `readonly` role cannot invoke `run_coding_task` or `cancel_task`. **Residual risk**: Cedar engine runs in `LOG_ONLY` mode by default. **Customer responsibility**: flip to `ENFORCE` before production, per HARDENING.md. |

### 2. Gateway REQUEST interceptor ([`lambda/interceptor/index.py`](../lambda/interceptor/index.py))

| ID | STRIDE | Threat | Control |
|----|--------|--------|---------|
| GI-S | Spoofing | Interceptor forwards a request with a fake `_user_id` | The interceptor only injects `_user_id` from a JWT the Gateway has already validated. If no valid JWT is present the tool call is not decorated with a user identifier. |
| GI-T | Tampering | Client smuggles a pre-set `_user_id` in tool arguments | The interceptor overwrites the `_user_id` in tool arguments with the JWT `sub`; any client-supplied value is clobbered. |
| GI-I | Information disclosure | JWT is logged to CloudWatch | The interceptor reads the JWT claims but does not log the raw token. Forwarded headers exclude `Authorization` (required for correctness anyway - see MC-S below). |
| GI-E | Elevation of privilege | Inbound JWT overrides outbound SigV4 signature | The interceptor strips the inbound `Authorization` header before returning `transformedGatewayRequest.headers`, so the Gateway's SigV4 signature reaches the Runtime unchallenged. This is critical for `GATEWAY_IAM_ROLE` correctness; see [docs/ARCHITECTURE.md#architectural-decisions](ARCHITECTURE.md#architectural-decisions). |

### 3. Cedar Policy Engine ([`stacks/policy_stack.py`](../stacks/policy_stack.py))

| ID | STRIDE | Threat | Control |
|----|--------|--------|---------|
| CP-T | Tampering | Attacker edits Cedar policies | Policies are created post-deploy via [`scripts/create-policies.py`](../scripts/create-policies.py) using IAM-authenticated API calls. Only principals with `bedrock-agentcore:CreatePolicy/UpdatePolicy` can modify them. |
| CP-R | Repudiation | A denied call is not recorded | `LOG_ONLY` mode writes evaluation records to CloudWatch. `ENFORCE` mode adds a hard deny plus the same log entry. |
| CP-E | Elevation of privilege | A missing policy allows an unintended action | The default policy set is permissive by design (`readonly` denies + `*-production` deny). **Customer responsibility**: add organization-specific permits/forbids; verify coverage in `LOG_ONLY` before switching to `ENFORCE`. |

### 4. Gateway → Runtime (SigV4)

| ID | STRIDE | Threat | Control |
|----|--------|--------|---------|
| GR-S | Spoofing | Someone other than the Gateway signs a request to the Runtime | Runtime validates SigV4 against `GATEWAY_IAM_ROLE`. Forging requires the Gateway's role credentials. |
| GR-T | Tampering | Request body is modified in flight | SigV4 covers method, URL, headers, and body hash. Any tampering breaks the signature. |
| GR-I | Information disclosure | Runtime responses leak to a third party | Runtime → Gateway traffic is over TLS inside the AWS network. |

### 5. Runtime microVM (FastMCP server, [`container/code_mcp_server.py`](../container/code_mcp_server.py))

| ID | STRIDE | Threat | Control |
|----|--------|--------|---------|
| RT-S | Spoofing | One session acts as another | Each session runs in its own Firecracker microVM with its own `session_id`. Tool calls carry `_user_id` from the interceptor. DynamoDB records are partitioned by `user#{user_id}`. |
| RT-T | Tampering | An attacker with in-process access modifies `_running_tasks` or `_cancel_flags` | In-process attack requires prior code execution inside the microVM - covered by OC-* and PL-* below. |
| RT-R | Repudiation | Runtime denies a job ever ran | DynamoDB RUNNING → terminal state transitions are idempotent and timestamped. AgentCore managed session storage retains work directories across microVM stop/resume in supported regions. |
| RT-I | Information disclosure | Logs or metrics leak sensitive data | CloudWatch log groups are encrypted with the customer-managed CMK. OTEL metrics do not include request bodies. **Residual risk**: task descriptions and repo URLs appear in error logs; document as "medium sensitivity". |
| RT-D | Denial of service | Async task never terminates | Each async task has a configurable per-call timeout (`timeout_minutes_default=10`, `timeout_minutes_max=30`). OpenCode subprocess terminates via SIGTERM → SIGKILL escalation with a 5-second grace period. |
| RT-E | Elevation of privilege | Tool call elevates beyond its declared action | Every tool signature validates inputs (`_validate_repo_url`, `_validate_git_ref` in [`container/pipeline.py`](../container/pipeline.py)). The execution role uses SigV4 scoped actions; see IR-* below. |

### 6. OpenCode subprocess ([`container/tools/run_opencode_acp.py`](../container/tools/run_opencode_acp.py))

| ID | STRIDE | Threat | Control |
|----|--------|--------|---------|
| OC-T | Tampering | `OPENCODE_BINARY` env var points at an attacker binary | `_validate_opencode_binary` (called at FastMCP startup) requires an absolute path, a regular file, and executable bit. If the file is swapped between startup and first invocation, the microVM's root filesystem ACLs apply. |
| OC-T2 | Tampering | LLM output modifies files outside `work_dir` | OpenCode operates inside a per-session `work_dir` under AgentCore managed session storage. **Residual risk**: the microVM does not enforce a chroot on OpenCode; a model prompting OpenCode to `rm -rf /` would affect only that session's microVM, which is discarded at session end. |
| OC-I | Information disclosure | LLM output leaks credentials into PRs | `scan_and_strip_credentials.py` runs after OpenCode and before `git push`. Patterns covered today: AWS access keys (`AKIA`, `ASIA`), `sk-` API keys, GitHub tokens (`gh[pousr]_`, `github_pat_`), GitLab PATs (`glpat-`), PEM private keys, and high-entropy `secret=` / `password=` / `token=` / `key=` assignments. **Residual risk**: the scanner is regex-based. Credentials in formats it does not recognize pass through. Extending the regex set is called out in HARDENING.md. |
| OC-E | Elevation of privilege | Environment leakage gives OpenCode undesired credentials | `_build_spawn_env` in [`container/tools/run_opencode_acp.py`](../container/tools/run_opencode_acp.py) assembles the subprocess environment explicitly. AWS credentials are resolved per task via `_resolve_aws_credentials_into_env` from the container's IAM role and passed only into this subprocess. |

### 7. Pipeline ([`container/pipeline.py`](../container/pipeline.py))

| ID | STRIDE | Threat | Control |
|----|--------|--------|---------|
| PL-T | Tampering | `repo_url` or branch name carries argv-flag smuggling (e.g. `--upload-pack=...`) | `_validate_repo_url` rejects non-`https://`/`git@` schemes, NULs, whitespace, and oversize values. `_validate_git_ref` rejects leading `-` (argv-flag confusion), embedded whitespace, and oversize values. Subprocess invocation uses list-form argv throughout, so there is no shell-injection vector regardless of input. |
| PL-T2 | Tampering | Task description carries prompt-injection payload | **Residual risk**: task descriptions are forwarded to Bedrock verbatim. The system relies on the upstream model's safety training plus Cedar policies plus the credential scanner on output. See "GenAI-specific threats" below. |
| PL-I | Information disclosure | OAuth token written to a tempfile readable by other processes | `container/lib/git_askpass.py` uses `os.open(..., mode=0o400)` on the sidecar token file and `os.chmod(..., 0o500)` on the askpass script itself. Both are removed in `finally` blocks. Tests lock this invariant ([`tests/unit/test_git_askpass_permissions.py`](../tests/unit/test_git_askpass_permissions.py)). |
| PL-R | Repudiation | A job's terminal state is not attributable | Terminal-state writes to DynamoDB are guarded by the `user_id` from the JWT-derived `_user_id`, not from the request body. Idempotent within a job. |

### 8. Runtime execution role ([`stacks/agentcore_stack.py`](../stacks/agentcore_stack.py))

| ID | STRIDE | Threat | Control |
|----|--------|--------|---------|
| IR-E | Elevation of privilege | Overly broad role lets a compromised container do more than intended | Role is scoped to: specific DynamoDB table ARN + index wildcard; specific Bedrock model ARNs; specific AgentCore resource ARNs in the account/region; Secrets Manager prefix `bedrock-agentcore-identity*` (AgentCore Identity naming convention); AWS service APIs that mandate `Resource: '*'` (CloudWatch Metrics, X-Ray, ECR `GetAuthorizationToken`). Every wildcard has a cdk-nag suppression explaining whether it is service-forced or prefix-scoped. |
| IR-I | Information disclosure | Role reads secrets beyond its scope | Secrets Manager access is restricted to `bedrock-agentcore-identity*`. The sample's own secrets (webhook signing, GitHub OAuth app) live under the `opencode/*` prefix and are read only by the callback Lambda, not by the Runtime. |

### 9. OAuth 3LO callback ([`stacks/callback_api_stack.py`](../stacks/callback_api_stack.py), [`lambda/oauth_callback/index.py`](../lambda/oauth_callback/index.py))

| ID | STRIDE | Threat | Control |
|----|--------|--------|---------|
| CB-S | Spoofing | Attacker replays an old callback URL | The `HttpLambdaAuthorizer` ([`stacks/callback_api_stack.py`](../stacks/callback_api_stack.py)) validates `session_id` shape (regex) and requires `state` to be JSON with a `user_id` key. AgentCore Identity validates `session_id` is one it issued; the `CompleteResourceTokenAuth` call fails for unknown sessions. |
| CB-T | Tampering | Attacker modifies query-string params in flight | The callback URL is served over TLS by API Gateway. |
| CB-R | Repudiation | No audit trail of OAuth consents | API Gateway access logs are written to a KMS-encrypted CloudWatch log group with request-id, source IP, and timestamp. |
| CB-I | Information disclosure | Authorization code is leaked | The `HttpLambdaAuthorizer` runs synchronously before the callback Lambda; an unauthorized caller never reaches the Lambda that would forward the code to AgentCore Identity. |
| CB-E | Elevation of privilege | Callback registers a token for a different user | `state` carries the originating `user_id`; AgentCore Identity associates the resulting token with that user. |

### 10. Amazon Cognito user pool ([`stacks/security_stack.py`](../stacks/security_stack.py))

| ID | STRIDE | Threat | Control |
|----|--------|--------|---------|
| CG-S | Spoofing | Attacker registers a rogue user | `self_sign_up_enabled=False`. Users are admin-provisioned. |
| CG-I | Information disclosure | Weak password allows guessing | Password policy requires min length 12, lower + upper + digit + symbol. Standard threat protection is enabled (`StandardThreatProtectionMode.FULL_FUNCTION`). |
| CG-E | Elevation of privilege | Credential-stuffing attack succeeds | **Residual risk**: MFA is not enforced on the sample pool. **Customer responsibility**: enable Cognito MFA before routing real users through this pool; documented in HARDENING.md. |

### 11. DynamoDB audit records ([`stacks/job_store_stack.py`](../stacks/job_store_stack.py), [`container/lib/dynamodb_helpers.py`](../container/lib/dynamodb_helpers.py))

| ID | STRIDE | Threat | Control |
|----|--------|--------|---------|
| DB-T | Tampering | Attacker rewrites an existing record | Table uses the customer-managed CMK. IAM restricts writes to the Runtime execution role. Records are partitioned by `user#{user_id}`. |
| DB-I | Information disclosure | Cross-user record read | Queries use `PK = user#{user_id}` sourced from the JWT-derived `_user_id`, not from request body fields. |
| DB-D | Denial of service | GSI1 hot partition | GSI1 has 4 partition-key values (one per terminal state). **Residual risk**: at high volume this hits per-partition RCU/WCU limits. Sharding strategy is documented in the stack file. |

### 12. VPC egress

| ID | STRIDE | Threat | Control |
|----|--------|--------|---------|
| EG-I | Information disclosure | Runtime exfiltrates data to an attacker-controlled host | Security-group egress is restricted to TCP/443. AWS service traffic uses VPC endpoints. **Residual risk**: non-AWS traffic (git hosts, but also any public HTTPS endpoint the OpenCode binary or a compromised model prompt chooses) is unfiltered through the NAT Gateway. **Customer responsibility for production**: add AWS Network Firewall FQDN rules or a forward proxy; documented in HARDENING.md. |

---

## GenAI-specific threats

The LLM and its subprocess tooling introduce threats that do not fit cleanly under a single STRIDE letter. These are called out explicitly so reviewers can evaluate the mitigation strategy on its own terms.

| ID | Threat | Mitigation |
|----|--------|------------|
| AI-1 | Prompt injection: a crafted task description coerces the model into exfiltrating secrets, editing out-of-scope files, or chaining attacks against the git provider | Task descriptions are forwarded to Amazon Bedrock verbatim. Mitigations in layers: Bedrock's upstream safety filters on the selected model; Cedar policies scoped to `opencode___{tool}` action ARNs (so the model cannot reach tools it was not authorized for); microVM per-session isolation (blast radius is one session's work directory); credential scanner on pushed output. **Residual risk**: no dedicated prompt-injection filter (e.g. Amazon Bedrock Guardrails). Documented in HARDENING.md. **Customer responsibility**: layer a Bedrock Guardrail for production. |
| AI-2 | Output contains sensitive data from the source repo | Credential scanner runs between OpenCode output and `git push`. Covered patterns: AWS access keys, `sk-` API keys, GitHub tokens, GitLab PATs, PEM private keys, high-entropy `secret=`/`password=`/`token=`/`key=` assignments. **Residual risk**: formats outside the regex set pass through. **Customer responsibility**: extend patterns or add secondary scanning (e.g. GitGuardian, gitleaks) on GitHub. |
| AI-3 | Model outputs malicious code that compromises the reviewer's machine on clone | PRs land in the user's own repo; review is the user's responsibility. The credential scanner does not claim to detect malicious code. **Customer responsibility**: treat LLM-authored PRs the same as PRs from an external contributor: CI + human review before merge. |
| AI-4 | Customer data is used for model training or retained by AWS | Amazon Bedrock is pre-approved for this workload; the Anthropic Claude models on Bedrock do not train on customer prompts per the Bedrock service terms. Repository contents are transient inside the per-session microVM and are discarded at session end. |
| AI-5 | Third-party AI tool (OpenCode) is backdoored upstream | OpenCode is MIT-licensed and installed from the upstream installer script at container build time. Container image is rebuilt and pushed to ECR on every `cdk deploy`. **Customer responsibility**: pin the OpenCode version (called out in HARDENING.md) and add supply-chain verification (sigstore, reproducible-build verification, or an internal mirror) for production. |
| AI-6 | Biased or unsafe model outputs | The sample does not add bias/fairness controls beyond those provided by the upstream model. This is a code-generation agent, not a decision-making agent in a safety-critical domain. |

---

## Residual risks (accepted by design)

These are the risks the sample explicitly accepts because of its scope (it is a sample, not a production service). Each is either called out in HARDENING.md or flagged above.

1. **Cedar policies default to `LOG_ONLY`.** Production adopters are expected to flip to `ENFORCE`.
2. **Cognito MFA is not enforced.** Production adopters are expected to enable MFA.
3. **Outbound traffic is not FQDN-restricted beyond port 443.** Production adopters are expected to add Network Firewall or a forward proxy.
4. **NAT Gateway is single-AZ by default** (cost optimization). Production adopters are expected to scale to one NAT per AZ.
5. **No dedicated prompt-injection filter.** Production adopters are expected to layer a Bedrock Guardrail.
6. **Credential scanner is regex-based.** Production adopters are expected to extend patterns or add a secondary scanner.
7. **GSI1 has 4 partition keys.** At high volume, sharding is required.
8. **OpenCode version is not pinned in the Dockerfile.** Production adopters are expected to pin the version.
9. **No AWS Budget alert is created.** The `daily_cost_budget_usd` context value is a reference; production adopters create the budget out-of-band.
10. **AgentCore-managed secrets (`bedrock-agentcore-identity*`) use AWS-owned keys** by default. Customer-managed keys can be configured if the threat model requires them.

## Out-of-scope threats

Explicitly not modelled here:

- AWS account takeover (we assume the account operator is trusted).
- Denial of service from a logged-in authenticated user (rate limiting is the customer's operational responsibility).
- Side-channel attacks across Firecracker microVMs (AWS platform responsibility).
- Physical/infrastructure attacks on AWS data centres (AWS platform responsibility).
- Client-side attacks on the MCP client itself (client vendor responsibility; the user's device is the trust root for the user actor).

## Review cadence

This threat model is reviewed when:

1. A new AWS service is added to the stack graph.
2. A new tool is added to the FastMCP server.
3. The credential scanner's regex set is changed.
4. The Cedar policy set is re-scoped.
5. `aws_cdk.aws_bedrock_agentcore_alpha` is upgraded to a stable module (or forked).

The maintainer is responsible for updating HARDENING.md and this document in the same change set when any of those conditions trigger.
