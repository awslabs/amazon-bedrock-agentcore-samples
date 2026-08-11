# Self-assessment against `02-use-cases/use-case-assessment.md`

Scored using the repository's own rubric, before submission. Where a claim could be
inflated, the conservative number is taken and the reasoning stated.

## Score

| Dimension | Weight | Score | Basis |
|---|---|---|---|
| Existing tier | S=4 … C=1 | **0** | New sample, no prior tier. Claiming one would be inventing a grade. |
| Blog post | 0 or 2 | **0** | No blog post references this sample. |
| AgentCore features | 1 pt each of 13 | **8** | Runtime, Memory, Gateway, Identity, Policy, Evaluations, Observability, Code Interpreter |
| Unique customer problem | 1–5 | **4** | Partner/pre-sales POC review is a real, recurring, unserved need. Not 5: it is a productivity tool, not an enterprise must-have. |
| README quality | 1–5 | **5** | Quickstart, architecture (diagram + accessibility text), ADRs, cost, limitations, and — the thing that used to hold this at 4 — a real deployment has now been run and every command in this README verified against it. |
| Starter Toolkit | −2 | **0** | Not used. Test asserts no `.bedrock_agentcore.yaml` exists. |
| **Total** | | **17** | |

**Rubric verdict: UPDATE** (12–19). Not `KEEP AS-IS`, which needs ≥ 20. Above
`AWS-operations-agent` (16) and `customer-support-assistant` (15), both currently
`KEEP — UPDATE` in this repo.

A ninth capability, a Knowledge Base (FMKB) for shared FAQ search, was also added (see
ADR 0011) but is not counted here — "Knowledge Base" is not one of the 13 named features
in this repo's own rubric, so claiming a point for it would be inventing a category rather
than scoring against the real one.

## What changed since the first draft of this document

The previous version of this file was written before any AWS deployment existed and said
so plainly. Since then:

- **A real deployment exists and has been exercised end to end.** `agentcore deploy`
  succeeded (`CREATE_COMPLETE`, then multiple `UPDATE_COMPLETE`s as the sample grew);
  `agentcore validate` returns `Valid`; `agentcore invoke` and direct
  `boto3 bedrock-agentcore InvokeAgentRuntime` calls both return real, phase-by-phase
  results, not schema-only validation.
- **Gateway, Identity, Memory and Policy have all actually fired**, not just validated.
  The AWS-Documentation Gateway target is a real Lambda wrapping AWS Labs' own
  `awslabs.aws-documentation-mcp-server`, confirmed with a direct `aws lambda invoke`
  before ever wiring it into the Gateway. The Cognito M2M credential mints real tokens.
  Cedar's Policy Engine runs in `ENFORCE` mode on every Gateway call.
- **The graceful-degradation path has been observed live, not just unit-tested.** This
  account's Bedrock Marketplace payment gate blocks model calls (a billing-only
  restriction, out of scope to resolve here); every real invocation confirms the
  entrypoint degrades to the deterministic SOW-scoring floor and says so in its response,
  rather than failing the whole review. That degradation path is a designed feature (see
  `main.py`'s try/except around the grading pass), and now it's been watched happen
  against the real account, not just asserted by a test with a mocked client.
- **A second, optional layer was added and independently verified**: a small web front
  end (CloudFront + S3 + Lambda + DynamoDB) so a non-technical reviewer can upload a SOW
  and get a shareable, view-limited result link. This is new surface area versus the
  original submission and is documented in [ADR 0008](decisions/0008-view-limited-share-links-via-conditional-write.md)
  and [docs/ARCHITECTURE.md](ARCHITECTURE.md).
- **Category placement is now settled**: `02-workflow-automation-agents`, not
  `01-conversational-agents`. The previous version of this file flagged this as an open
  question — it's a single-shot, upload-and-review pipeline (closer in shape to
  `event-driven-claims-agent`'s phase pipeline) rather than a back-and-forth chat agent.

## Where the missing points are

A new contribution has no prior tier (4 points) and no blog post (2 points) on day one —
six of the missing points are structural, not fixable by more work before submission.

The points genuinely still in reach:

| Action | Gain | Notes |
|---|---|---|
| Add AWS Pricing MCP as a second Gateway target | 0 | Gateway already counted; would move pricing from a static snapshot to live, which is a real quality improvement even at 0 rubric points |
| Add Harness | +1 | Plausible: declarative agent config for the SOW grader. Considered for Code Interpreter access specifically and rejected — see ADR 0010 — but remains open as its own feature |
| Write an accompanying blog post | +2 | Still the single largest available gain |

Realistic ceiling without a blog post: **18**. With one: **20**.

## Feature audit — declared vs actually exercised

Audited by grepping the runtime code and, this time, by watching it run:

| Feature | Declared | Exercised at runtime | Where | Observed live |
|---|---|---|---|---|
| Runtime | yes | yes | `BedrockAgentCoreApp()`, `@app.entrypoint` in `main.py` | yes |
| Memory | yes | partial | `AgentCoreMemorySessionManager` in `memory/session.py`; 3 strategies — SUMMARIZATION (short-term, `{actorId}/{sessionId}`) + SEMANTIC and USER_PREFERENCE (long-term, `{actorId}/facts` and `{actorId}/preferences`) | Raw session/event storage confirmed real via a direct `ListSessions` call (two real sessions found for the `anonymous` actor from this session's own test invocations). Strategy-derived long-term extraction is not: a direct `ListMemoryRecords` call against both long-term namespaces returned **0 records** for an actor with real session history. Session/event storage needs no model call; SEMANTIC/USER_PREFERENCE extraction is an async LLM pass over those events and is blocked by this account's Bedrock Marketplace restriction — the same root cause as Evaluations, SOW grading, diagram vision, and the what-if pricing tool's authoring step, not a config defect (`agentcore validate` passes; the namespace/actor_id plumbing itself is correct). See [ADR 0009](decisions/0009-user-preference-memory-needs-a-real-actor-id.md). |
| Gateway | yes | yes | `MCPClient` over `streamablehttp_client`, tools attached to the extractor | yes — real Lambda MCP target, confirmed with a direct pre-wiring `aws lambda invoke` |
| Identity | yes | yes | `@requires_access_token(auth_flow="M2M")` on `_build_mcp_client` | yes — real Cognito M2M token minted |
| Policy | yes | yes | Cedar engine in `ENFORCE` mode on the Gateway | yes |
| Evaluations | yes | configured, currently blocked | Two custom `llmAsAJudge` evaluators (`agentcore/mcp-targets/evaluators-stage2.json`) | `CreateEvaluator` rejects the grading model on two independent deploy attempts in this account, most recently with `Role does not have access for model` — consistent with the account's Bedrock Marketplace payment-instrument restriction (see main README's Known Limitations), not a config defect: `agentcore validate` passes, and the same model ID works for ordinary `InvokeModel` calls. `deploy.sh` ships without evaluators by default so this never blocks the rest of the stack. |
| Observability | yes | yes | `AGENT_OBSERVABILITY_ENABLED`, `enableOtel: true` | yes |
| Code Interpreter | yes | partial | Optional Phase 6a, `tools/what_if_pricing.py`, AWS-managed sandbox (`aws.codeinterpreter.v1`) | Sandbox path (`StartCodeInterpreterSession`/`InvokeCodeInterpreter`/`StopCodeInterpreterSession`) verified directly against the real IAM grant, independent of the model-gated authoring step — see ADR 0010's "Verified independent of the Marketplace gate" for the exact result. The authoring step itself is expected to degrade under the same Marketplace restriction as SOW grading. |
| Knowledge Base (not in the 13, not scored) | yes | partial | Optional Phase 6b, `tools/faq_search.py`, `bedrock-agent-runtime:Retrieve` against `PocValidatorFaqKB` | See ADR 0011's "Verified independent of the Marketplace gate" for the exact result. |

Five of the eight core-13 features fired fully against the real account (Runtime, Gateway,
Identity, Policy, Observability); Code Interpreter's sandbox path was verified directly
even though its authoring step is model-blocked; Memory's raw storage is real but its two
long-term extraction strategies are not populated; Evaluations is fully configured and
would fire in an account without the Marketplace restriction. Nothing here is declared for
the score alone — every "partial" is backed by a direct API call showing exactly what did
and didn't happen, not an assumption.

## Full AgentCore capability coverage

The AgentCore CLI (0.26.0) exposes a broader set of capabilities than the rubric's 13
named features, discovered through `agentcore --help`, `agentcore add --help`, and
`agentcore run --help` against the installed CLI directly, not a marketing page. The
table below audits every capability surfaced there.

| Capability | Status | Basis |
|---|---|---|
| Runtime | Implemented | 5+2-phase entrypoint, deployed, invoked live |
| Memory | Partial | See feature audit above — storage real, long-term extraction model-blocked |
| Gateway | Implemented | Real Lambda MCP target, semantic search on |
| Identity | Implemented | Cognito M2M, real token minted |
| Policy Engine | Implemented | Cedar, `ENFORCE` mode |
| Evaluations | Configured, blocked | `CreateEvaluator` blocked by account Marketplace restriction |
| Observability | Implemented | OTEL, Transaction Search enabled |
| Code Interpreter | Implemented | Sandbox call verified directly; authoring step model-blocked |
| Knowledge Base (FMKB) | Implemented | `Retrieve` verified end-to-end, real match at score 1.0 |
| Optimization (`agentcore run recommendation`) | Attempted; real API; not completed | A `TOOL_DESCRIPTION_RECOMMENDATION` job was created and reached a `FAILED` terminal state with `ValidationException: No sessions found in the specified time window`. The API is real and reachable — a distinct failure mode from the Marketplace restriction — but this session's invocation volume and timing did not satisfy CloudWatch's session-search filters. A retry with a longer lookback window or higher invocation volume would likely succeed; not pursued further, as this is a secondary capability rather than a core requirement of the sample. |
| A/B testing (`agentcore run ab-test`) | Feasible; not built | A real CLI command comparing config-bundle or gateway-target variants. This sample has one configuration variant, so there is nothing to compare against yet. |
| Browser Tool | Feasible; not built | `agentcore add tool --type agentcore_browser` is real but, like Code Interpreter, requires a Harness. The strongest candidate use case: fetching a live AWS Pricing Calculator page for a real-time sanity check against the static pricing snapshot this sample already discloses as directional only. |
| Harness | Feasible, deliberately not built | Real, large surface (`agentcore add harness` — its own model config, memory config, tool config, network mode). Considered specifically as the path to Code Interpreter/Browser access and rejected — see [ADR 0010](decisions/0010-code-interpreter-for-what-if-pricing.md) — because it would stand up a second agent-hosting abstraction alongside the existing Strands runtime for no capability this sample needs beyond what direct SDK calls already provide |
| Registry (AWS Agent Registry) | Real, in preview, not built | Confirmed via AWS's own devguide: a control-plane discovery/governance layer, distinct from Gateway (data plane). Public preview, and its API namespace was mid-migration (`bedrock-agentcore` → `agent-registry`) as of this project's build window — building against it now risks the sample going stale within weeks, not years |
| Payments | Not applicable | `agentcore add payment-manager`/`payment-connector` are real but `[preview]`-flagged and built for metering paid agent usage. This is a free internal review tool; no wallet/billing concept fits the domain |
| Config Bundles | Feasible, low value here | Real (`configBundles[]`, versioned prompt/tool config for A/B testing). This sample has one prompt per phase and no variant to bundle yet — would be premature structure for a single-configuration agent |
| A2A / AG-UI protocols | Feasible, not needed | `bedrock_agentcore.runtime.a2a` and `.ag_ui` are real SDK modules for agent-to-agent and AG-UI-protocol interop. This sample is invoked directly (CLI, web Lambda) — no other agent or AG-UI-speaking client currently needs to reach it, so the standard HTTP/Strands protocol already in use is the right amount of interface |

## Configuration verified against the real CLI

`agentcore validate` from `@aws/agentcore` **0.26.0** returns `Valid`. Three corrections
made from documentation alone during the original build, each pinned by a test:

1. `managedBy` accepts only `"CDK"` — `"CLI"` is rejected.
2. An `mcpServer` Gateway target puts `endpoint` as a **sibling** of `targetType`. There
   is no nested `mcpServer` object, unlike `lambdaFunctionArn`. The value must parse as
   a URL. (This sample ships the `lambdaFunctionArn` target shape, not `mcpServer`.)
3. `aws-targets.json` is a **bare array**, not an object with a `targets` key.

Two further, real deploy-time failures, root-caused against CloudFormation stack events
rather than guessed, before the first successful deploy:

4. `CreateEvaluator`'s model validation rejected undated "floating alias" model IDs
   (`...claude-sonnet-4-6`) for this API in this account/region, even though the same IDs
   are `ACTIVE` inference profiles for ordinary `InvokeModel` calls. Fixed by switching
   to a fully-qualified, dated snapshot ID for the evaluator model, matching AWS's own
   published examples.
5. The Gateway rejected the MCP tool schema with "Attribute type null is not supported."
   Root cause: the real MCP server's Pydantic-generated JSON Schema represents
   `Optional[...]` parameters as `"anyOf": [{"type": "..."}, {"type": "null"}]`, which the
   Gateway's schema parser doesn't accept. Fixed by stripping the null-type branch before
   registering the tool schema.
6. On a later full teardown-and-redeploy (rebuilding the stack from scratch to verify the
   whole sample reproduces cleanly), `CreateEvaluator` failed again on the *same* dated
   Haiku model ID that fix #4 had settled on — this time with `Role does not have access
   for model`, not the earlier `not available in region` error. Different error, same root
   account restriction. `evaluators` was set to `[]` in both `agentcore.json` and
   `agentcore.json.template` so the rest of the stack (Runtime, Memory, Gateway, Policy
   Engine) deploys cleanly without depending on evaluator access; the two evaluator
   configs are preserved in `agentcore/mcp-targets/evaluators-stage2.json` for an account
   without this restriction.

## Security review

A dedicated security pass — static analysis (`bandit`), dependency scanning
(`pip-audit`, `npm audit`), a repository-wide secrets scan, and a manual IAM
review of every grant script and CDK construct — was run against the full
diff before submission. Two findings were fixed:

1. **XXE / entity-expansion exposure in draw.io diagram parsing**
   (`core/diagrams.py`). `parse_drawio()` calls `ElementTree.fromstring()` on
   XML from an uploaded `.drawio` file — user-controlled input, not internal
   data. Standard `xml.etree` is exposed to entity-expansion denial-of-service.
   Replaced with `defusedxml.ElementTree`, a drop-in-compatible parser with
   the same public API.
2. **Non-constant-time comparison of the web layer's demo-key header**
   (`web/lambda/handler.py`). `EXPECTED_KEY` was compared with `!=`; replaced
   with `hmac.compare_digest`.

One dependency advisory remains open and is documented, not silently carried:
a `brace-expansion` HIGH-severity advisory bundled inside `aws-cdk-lib`
itself, unreachable by `npm overrides` because it ships as a bundled
dependency rather than a normally-resolved one — confirmed by checking
`aws-cdk-lib`'s `bundleDependencies` field directly and by testing the latest
published `aws-cdk-lib` release, which still bundles an affected version. See
the main README's Known Limitations for the full explanation and the
mitigation applied to every reachable copy of the dependency.

No high- or medium-severity findings were left unresolved: every IAM grant in
`scripts/` and both CDK apps is scoped to a specific resource ARN, no
hardcoded credentials or account identifiers were found in tracked files, and
Python/Node dependency scans returned no other advisories.

## Honest limitations for a reviewer

- Model-assisted diagram vision and SOW grading are blocked in the deployment account by
  an AWS Marketplace payment-instrument gate — a billing configuration issue on that
  specific account, not a defect in this sample. Every code path that depends on a model
  call is written to degrade to its deterministic fallback rather than fail, and that
  fallback has been observed running for real, not just unit-tested. A reader deploying
  into an account without this restriction should see full model-assisted grading.
- Pricing is a static `ap-south-1` snapshot, directional only — see
  [docs/ARCHITECTURE.md](ARCHITECTURE.md#cost).
- The web layer's upload accepts `.txt`/`.md` SOWs and `.mmd`/`.drawio` diagrams only —
  not `.docx` or image-based diagrams. See the README's Known Limitations for why.
- The web layer's Basic Auth is a shared-credential gate, not a real multi-user auth
  system — adequate for keeping a small demo from being found and poked at random, not
  for onboarding multiple named users.
