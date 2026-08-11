# 0010 — What-if pricing runs in Code Interpreter, not in the model's head

## Status
Accepted. Deploys cleanly; the model-authoring step is unverifiable
end-to-end in this account (see Consequences).

## Context

`core/pricing.py` exists specifically so no arithmetic in this project comes
from a model — see its own module docstring: "All arithmetic happens here,
in Python. No language model computes money." A reviewer's natural next
question after seeing a cost estimate is a "what if" — what if we used
Reserved Instances, what if traffic doubled, what if Multi-AZ was dropped
for the non-production database. Answering that honestly means recomputing
against the real line items, not asking a model to state a plausible-sounding
new total from memory, which is exactly the failure mode `core/pricing.py`
was built to avoid in the first place.

AgentCore Code Interpreter gives a sandboxed, real Python execution
environment reachable from the runtime container. Two integration paths
exist:

1. `agentcore add tool --type agentcore_code_interpreter --harness <name>` —
   but this requires a **Harness**, a separate declarative agent-hosting
   resource (`agentcore add harness`) that is not otherwise part of this
   sample. Standing one up just to reach Code Interpreter would mean adding a
   second agent-execution model alongside the existing Strands-based
   `BedrockAgentCoreApp` runtime, for no reason this sample needs.
2. The `bedrock_agentcore.tools.code_interpreter_client` SDK, called directly
   from Python — the same pattern already used for Memory
   (`AgentCoreMemorySessionManager`, no separate harness either).

## Decision

Use the SDK client directly, targeting AWS's public managed sandbox
identifier `aws.codeinterpreter.v1` (`code_session()` /
`CodeInterpreter.start()` with no `identifier` override) — no custom Code
Interpreter resource to provision, version, or tear down.

The flow, in `app/pocvalidator/tools/what_if_pricing.py`:

1. A Haiku-backed Strands agent (`FAST_MODEL_ID`, same cost-routing rationale
   as SOW banding) is given the *real* `CostEstimate` line items and the
   reviewer's plain-language question, and asked to author a `compute(lines)`
   Python function — submitted via a `submit_whatif_code` tool, the same
   typed-tool-call pattern as `submit_extraction`/`submit_sow_assessment` in
   `tools/structured_output.py`, so the model can't return prose instead of
   code.
2. That exact code runs inside the Code Interpreter sandbox against the real
   `lines`, not `eval()`'d in-process.
3. The response includes the code that ran (`what_if.code`) alongside the
   result, so a reviewer sees the computation, not just a number to trust.

## Rationale

This mirrors the diagram-extraction and SOW-grading design already in this
sample: the model's job is narrow (author code, read a diagram, band a
criterion), and the thing a reviewer would take at face value (a dollar
figure) is either computed in plain Python or, here, computed in a real
Python interpreter running exactly the code the model wrote — auditable, not
opaque.

The managed-sandbox identifier was chosen over `create_code_interpreter`
because a what-if scratch calculation has no reason to need a custom
network configuration or a long-lived resource; AWS's own getting-started
guidance treats `aws.codeinterpreter.v1` as the default for exactly this
shape of use.

## Consequences

- **IAM is a manual grant, not a CDK-declared resource.** There is no
  `agentcore.json` field for Code Interpreter outside the harness path this
  sample doesn't use, so `scripts/grant_code_interpreter_access.sh` attaches
  a scoped inline policy (`StartCodeInterpreterSession`,
  `InvokeCodeInterpreter`, `StopCodeInterpreterSession` against
  `arn:aws:bedrock-agentcore:<region>:aws:code-interpreter/aws.codeinterpreter.v1`
  — confirmed against AWS's own `InvokeCodeInterpreter` API reference and
  getting-started guide, not guessed) directly to the runtime execution role
  after every deploy. This is the same category of manual fix as the
  CloudFront↔Lambda dual-auth gap worked around elsewhere in this project —
  documented, scripted, and idempotent rather than a one-off `aws iam` call
  typed once and forgotten.
- **The code-authoring step is a model call**, and like SOW grading and
  diagram vision, it is expected to fail in this specific deployment account
  under the same standing Bedrock Marketplace payment-instrument
  restriction documented elsewhere in this sample (see the main README's
  Known Limitations and `docs/self-assessment.md` item 4/6). `run_what_if()`
  degrades to `{"status": "unavailable", "reason": ...}` on that failure,
  exactly like the SOW grading pass degrades to its heuristic floor — never
  a hard failure of the rest of the review. That means this feature is
  **structurally correct and deploys cleanly, but not verifiable
  end-to-end in this account** until the Marketplace restriction lifts. A
  reader deploying into an unrestricted account should see it run for real.
- Only the code-authoring call is model-gated; the sandbox execution itself
  (`bedrock-agentcore:InvokeCodeInterpreter`) has no such dependency. See
  "Verified independent of the Marketplace gate" below for what was actually
  exercised directly, outside the full agent flow.

## Verified independent of the Marketplace gate

Called `StartCodeInterpreterSession` → `InvokeCodeInterpreter` →
`StopCodeInterpreterSession` directly against the deployed IAM grant, with a
hand-written `compute(lines)` snippet standing in for the model-authored one
— entirely bypassing the code-authoring model call, to isolate the sandbox
path. It worked, and caught one real bug before it ever reached the full
agent flow:

**`InvokeCodeInterpreter`'s response is an EventStream, not a plain dict.**
AWS's own API reference page documents the response body as a flat
`{"result": {"content": [...], "structuredContent": {...}}}` object,
matching `arn:aws:bedrock-agentcore:*` request/response conventions used
elsewhere in this sample (e.g. `InvokeAgentRuntime`'s SSE framing). It is not
that — `invoke_code_interpreter`'s output shape marks `stream` as
`eventstream: True` in botocore's own service model, and the first version
of `run_what_if()` read `response["result"]` directly, which silently
returned an empty dict with no exception raised (a boto3 `EventStream`
object is truthy and dict-like enough that `.get("result", {})` doesn't
error, it just returns nothing useful). Confirmed the real shape by printing
the raw response, then iterating `response["stream"]` for the event
carrying `result.structuredContent.{stdout,stderr,exitCode}` — this is what
`app/pocvalidator/tools/what_if_pricing.py` does now. Caught by running the
sandbox call directly rather than assuming the SDK's own `execute_code()`
wrapper (which does the same iteration internally, correctly) meant a
hand-rolled equivalent would too.

With that fix, a direct sandbox call recomputing a Multi-AZ removal against
a hand-written `lines` list returned the expected
`{"new_total_delta": -566.0, "explanation": "..."}` — the sandbox execution
half of this feature is real and exercised, independent of whether the
code-authoring model call succeeds in this account.
