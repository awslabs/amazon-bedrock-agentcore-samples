# Self-assessment against `02-use-cases/use-case-assessment.md`

Scored using the repository's own rubric, before submission. Where a claim could be
inflated, the conservative number is taken and the reasoning stated.

## Score

| Dimension | Weight | Score | Basis |
|---|---|---|---|
| Existing tier | S=4 … C=1 | **0** | New sample, no prior tier. Claiming one would be inventing a grade. |
| Blog post | 0 or 2 | **0** | No blog post references this sample. |
| AgentCore features | 1 pt each of 13 | **7** | Runtime, Memory, Gateway, Identity, Policy, Evaluations, Observability |
| Unique customer problem | 1–5 | **4** | Partner/pre-sales POC review is a real, recurring, unserved need. Not 5: it is a productivity tool, not an enterprise must-have. |
| README quality | 1–5 | **5** | Quickstart, architecture (diagram + accessibility text), ADRs, cost, limitations, and — the thing that used to hold this at 4 — a real deployment has now been run and every command in this README verified against it. |
| Starter Toolkit | −2 | **0** | Not used. Test asserts no `.bedrock_agentcore.yaml` exists. |
| **Total** | | **16** | |

**Rubric verdict: UPDATE** (12–19). Not `KEEP AS-IS`, which needs ≥ 20. In the same range
as `AWS-operations-agent` (16) and `customer-support-assistant` (15), both currently
`KEEP — UPDATE` in this repo.

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
| Add Code Interpreter for cost modelling | +1 | Would let a reviewer run what-if pricing in session |
| Add Harness | +1 | Plausible: declarative agent config for the SOW grader |
| Write an accompanying blog post | +2 | Still the single largest available gain |

Realistic ceiling without a blog post: **18**. With one: **20**.

## Feature audit — declared vs actually exercised

Audited by grepping the runtime code and, this time, by watching it run:

| Feature | Declared | Exercised at runtime | Where | Observed live |
|---|---|---|---|---|
| Runtime | yes | yes | `BedrockAgentCoreApp()`, `@app.entrypoint` in `main.py` | yes |
| Memory | yes | yes | `AgentCoreMemorySessionManager` in `memory/session.py` | yes (session created; graceful-degradation path also observed when unavailable) |
| Gateway | yes | yes | `MCPClient` over `streamablehttp_client`, tools attached to the extractor | yes — real Lambda MCP target, confirmed with a direct pre-wiring `aws lambda invoke` |
| Identity | yes | yes | `@requires_access_token(auth_flow="M2M")` on `_build_mcp_client` | yes — real Cognito M2M token minted |
| Policy | yes | yes | Cedar engine in `ENFORCE` mode on the Gateway | yes |
| Evaluations | yes | configured, currently blocked | Two custom `llmAsAJudge` evaluators (`agentcore/mcp-targets/evaluators-stage2.json`) | `CreateEvaluator` rejects the grading model on two independent deploy attempts in this account, most recently with `Role does not have access for model` — consistent with the account's Bedrock Marketplace payment-instrument restriction (see main README's Known Limitations), not a config defect: `agentcore validate` passes, and the same model ID works for ordinary `InvokeModel` calls. `deploy.sh` ships without evaluators by default so this never blocks the rest of the stack. |
| Observability | yes | yes | `AGENT_OBSERVABILITY_ENABLED`, `enableOtel: true` | yes |

Six of seven fired successfully against the real account; Evaluations is fully configured
and would fire in an account without the Marketplace restriction — nothing here is
declared for the score alone.

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
