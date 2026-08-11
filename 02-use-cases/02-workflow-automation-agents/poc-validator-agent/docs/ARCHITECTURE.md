# Architecture

Full component and data-flow detail behind the diagram in the main [README](../README.md).
Regenerate `architecture.png` with `python3 diagrams.py` (`brew install graphviz && pip
install diagrams`) — see [../diagrams.py](../diagrams.py).

## Two independently deployable layers

**The agent core** (`app/pocvalidator/`, `agentcore/`) is the only layer required to use
this sample. It is entirely CLI/`agentcore invoke`-driven and needs no web front end.

**The web layer** (`web/`) is optional. It exists so a reviewer who doesn't want a
terminal can upload a Scope of Work in a browser and get a link back that a third party
can open without any login. It talks to the agent core the same way `agentcore invoke`
does — over `bedrock-agentcore:InvokeAgentRuntime` — so it adds a front door, not a second
implementation.

## Agent core

```
Caller (agentcore invoke, or the web layer's Lambda)
  │  bedrock-agentcore:InvokeAgentRuntime
  ▼
AgentCore Runtime — app/pocvalidator/main.py, 5-phase entrypoint
  │
  ├─ Phase 1  Diagram intake
  │            diagram_text + recognised extension (.mmd/.drawio) → core/diagrams.py,
  │            deterministic, no model, no confirmation gate.
  │            diagram_base64 (image) → Sonnet vision via a Strands agent, THEN
  │            "awaiting_confirmation" is returned and nothing else runs until the
  │            caller resubmits with extraction_confirmed: true.
  │
  ├─ AgentCore Memory (session.py) — SEMANTIC + SUMMARIZATION for cross-session
  │  recall, plus USER_PREFERENCE for durable per-reviewer preferences (namespace
  │  pocvalidator/{actorId}/preferences), attached to the vision-extraction agent.
  │  Degrades gracefully (logged, not raised) if Memory is unavailable. Only
  │  meaningful when actor_id is a real, stable identity per caller — the CLI path
  │  derives it from partner_id/user_id in the payload; the web layer generates a
  │  per-browser id client-side (localStorage) precisely so USER_PREFERENCE has
  │  something real to attach to instead of every visitor sharing one identity.
  │
  ├─ AgentCore Gateway — reached via MCPClient over streamablehttp_client, CUSTOM_JWT
  │  authorizer (Cognito M2M, client_credentials, minted via
  │  @requires_access_token(auth_flow="M2M")). One target: a Lambda running AWS Labs'
  │  own awslabs.aws-documentation-mcp-server, so any "AWS recommends X" the agent
  │  produces is grounded in a live documentation fetch, not model memory. Every
  │  Gateway tool call is checked by a Cedar Policy Engine in ENFORCE mode
  │  (read-only tools only — a validator that could mutate the account is a
  │  different, far more dangerous product).
  │
  ├─ Phase 4a  SOW scoring (before validation, so it can feed the report)
  │             sow.score_heuristic() runs unconditionally and deterministically.
  │             A Haiku grading pass then refines the bands; if that call fails for
  │             any reason (quota, access, transient error) the heuristic floor is
  │             kept and the response says so explicitly — never a hard failure.
  │
  ├─ Phases 2, 3, 5  Validation, pricing, recommendations — core/engine.py,
  │                   core/pricing.py, core/resources.py. No model. Findings,
  │                   cost totals and recommendation URLs are exactly what a
  │                   reviewer would want to double-check by hand, so nothing
  │                   here is generated — it's computed and looked up.
  │
  ├─ Phase 6a (optional) What-if pricing — only if the caller sends
  │  `what_if_question`. tools/what_if_pricing.py: Haiku authors a
  │  compute(lines) function against the real cost line items, submitted via
  │  a typed tool call (never free text); that exact code runs in AgentCore
  │  Code Interpreter's AWS-managed sandbox (aws.codeinterpreter.v1) — never
  │  eval()'d in-process, never a number the model just states. See ADR 0010
  │  for why this needs no custom Code Interpreter resource, and why the
  │  authoring step (not the sandbox call) is the one blocked by this
  │  account's Marketplace restriction.
  │
  └─ Phase 6b (optional) FAQ knowledge search — only if the caller sends
     `faq_query`. tools/faq_search.py calls bedrock-agent-runtime:Retrieve
     directly against a curated AgentCore Knowledge Base (FMKB,
     `PocValidatorFaqKB`) — plain vector search, not RetrieveAndGenerate, so
     it carries no generation-model dependency. See ADR 0011 for why a
     shared Knowledge Base fits recurring findings better than a per-actor
     Memory namespace.
```

`core/` imports nothing AWS-specific and nothing Strands-specific — it's plain Python over
YAML data files (`data/`, `rules/`), which is why `scripts/local_review.py` and the
Streamlit UI (`ui/app.py`) can exercise the whole deterministic pipeline with zero AWS
account, and why the test suite (69 tests) runs in about a second with no network access.

## Web layer

```
Browser
  │  HTTPS, Basic Auth (native browser prompt)
  ▼
CloudFront (1 distribution, 1 domain)
  │  viewer-request: CloudFront Function checks Authorization header,
  │  strips it before forwarding (see below), 401s + WWW-Authenticate on mismatch
  │
  ├─ default, /share/*  ──────────────────────────►  S3 (OAC, bucket not public)
  │                                                    index.html (upload UI)
  │                                                    share/view.html (read-only shell)
  │
  └─ /api/invoke, /share/*.json  ─────────────────►  Lambda (OAC-signed, SigV4)
       (registered in that exact order — see ADR 0008    │
        for why /share/*.json must precede /share/*)      ├─ POST /api/invoke
                                                            │   validates X-Demo-Key header
                                                            │   (shared secret; safe to embed
                                                            │   in the page's own JS because
                                                            │   Basic Auth already gated
                                                            │   viewing that JS)
                                                            │   → bedrock-agentcore:
                                                            │     InvokeAgentRuntime
                                                            │     (IAM role scoped to the
                                                            │     one runtime ARN)
                                                            │   → on completion, writes
                                                            │     share/<uuid>.json to S3
                                                            │     (tagged AutoExpire=true)
                                                            │     and seeds a DynamoDB item
                                                            │     {share_id, view_count: 0,
                                                            │      ttl: now+30d}
                                                            │
                                                            └─ GET /share/<id>.json
                                                                atomic conditional UpdateItem
                                                                (view_count < 3) against
                                                                DynamoDB, THEN reads the S3
                                                                object if allowed — see
                                                                ADR 0008
```

**Why CloudFront signs the Lambda call instead of a public Function URL.** The first
attempt used `AuthType: NONE` on the Lambda Function URL — this account's own guardrails
reject anonymous invocation even with a correct public resource policy. Switching to
`AuthType: AWS_IAM` with CloudFront Origin Access Control turned out to be strictly
better anyway: there is no public, unauthenticated HTTP endpoint anywhere in this
architecture. CloudFront is the only principal that can invoke the Lambda at all.

**Why the CloudFront Function deletes the `Authorization` header after checking it.**
`/api/invoke` and `/share/*.json` are OAC-signed by CloudFront itself — that signing
process sets its own `Authorization` header (SigV4) on the request forwarded to the
Lambda origin. If the viewer's own Basic-Auth `Authorization` header were still present
when the origin-request policy forwards headers, it collides with CloudFront's signature
and every request 403s with `SignatureDoesNotMatch`. This was a real bug hit during
build-out, not a hypothetical.

**Why POST bodies need an `x-amz-content-sha256` header from the browser.** CloudFront's
OAC signing requires the payload hash up front for PUT/POST — Lambda doesn't accept
unsigned payloads. The page's JS computes this with `crypto.subtle.digest("SHA-256", ...)`
before every `/api/invoke` call.

**Why the entrypoint's response needs SSE reassembly, not a single JSON parse.**
`invoke_agent_runtime`'s non-streaming response is Server-Sent Events — one `data: "<chunk>"`
line per value the entrypoint `yield`s, each chunk itself a JSON-encoded string. The Lambda
concatenates and unescapes these before scanning from the end for the trailing JSON object
the entrypoint's final `yield` produces.

## Cost

Everything in both layers is billed per-request or per-storage-byte; nothing runs
continuously.

| Component | Pricing model | Typical cost at sample volumes |
|---|---|---|
| AgentCore Runtime + Bedrock (Sonnet vision + Haiku grading) | Per invocation | $0.02–0.08/review |
| AgentCore Memory, Gateway | Per invocation / near-zero idle | Cents/month |
| AgentCore Code Interpreter (Phase 6a, optional) | Per-second active-resource consumption — $0.0895/vCPU-hour, $0.00945/GB-hour, 1-second minimum, billed only while a sandbox session is open | Fractions of a cent per what-if question (a few seconds of compute); zero when the feature isn't used |
| AgentCore Knowledge Base (Phase 6b, optional) | Consumption-based — size of indexed data stored plus number of retrievals, no minimum commitment | Cents/month at this sample's scale (9 short FAQ docs); see the [Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/) for current per-GB/per-retrieval rates, not repeated here to avoid going stale |
| Lambda (web layer) | Per request + duration | Within the 1M-request free tier at demo volumes |
| DynamoDB (view-counter table) | On-demand (pay-per-request) | Pennies/month at hundreds of shares |
| S3 (static page + share results) | Per GB stored + per request | Fractions of a cent |
| CloudFront | Per GB transferred + per request | Fractions of a cent per page/share view |

Build a detailed estimate for your own expected volume at the
[AWS Pricing Calculator](https://calculator.aws/#/estimate) — add Bedrock (Claude Sonnet +
Haiku, on-demand), Lambda, DynamoDB (on-demand), S3, and CloudFront.
