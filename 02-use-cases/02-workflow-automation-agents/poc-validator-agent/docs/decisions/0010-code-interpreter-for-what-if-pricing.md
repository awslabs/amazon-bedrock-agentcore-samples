# 0010 — What-if pricing runs in Code Interpreter, not in the model's head

## Status
Accepted. The sandbox execution path is deployed and verified directly. The
code-authoring step depends on model access currently blocked in this
account (see Consequences).

## Context

`core/pricing.py` computes every dollar figure in this sample; no model
produces a cost number directly. A reviewer's natural follow-up to a cost
estimate is a what-if question — Reserved Instances instead of on-demand,
double the traffic, drop Multi-AZ on a non-production database. Answering
that from model memory would reintroduce the failure mode `core/pricing.py`
exists to prevent: an unverifiable dollar figure.

AgentCore Code Interpreter provides a sandboxed Python execution
environment reachable from the runtime container. Two integration paths
were evaluated:

1. `agentcore add tool --type agentcore_code_interpreter --harness <name>`.
   This requires a Harness, a separate agent-hosting resource
   (`agentcore add harness`) not otherwise used in this sample. Adopting it
   solely to reach Code Interpreter would introduce a second
   agent-execution model alongside the existing Strands-based
   `BedrockAgentCoreApp` runtime.
2. The `bedrock_agentcore.tools.code_interpreter_client` SDK, called
   directly from application code — the same integration pattern already
   used for Memory (`AgentCoreMemorySessionManager`).

## Decision

Call the SDK client directly against AWS's managed sandbox identifier
`aws.codeinterpreter.v1` (`code_session()` / `CodeInterpreter.start()` with
no `identifier` override). No custom Code Interpreter resource is
provisioned.

Implementation, in `app/pocvalidator/tools/what_if_pricing.py`:

1. A Haiku-backed Strands agent (`FAST_MODEL_ID`, consistent with the
   cost-routing used for SOW banding) receives the actual `CostEstimate`
   line items and the reviewer's question, and authors a `compute(lines)`
   function. The function is submitted through a `submit_whatif_code` tool
   call — the same typed-tool-call pattern as `submit_extraction` and
   `submit_sow_assessment` in `tools/structured_output.py` — so the model
   cannot return free text in place of code.
2. The submitted code is executed inside the Code Interpreter sandbox
   against the real line items, not evaluated in-process.
3. The response returns the executed code alongside the result, so the
   computation is auditable rather than opaque.

## Rationale

This follows the pattern already established for diagram extraction and
SOW grading: the model performs a narrow, judgment-bound task, and the
output a reviewer would rely on is either computed in Python directly or,
here, computed by a real interpreter running code the model authored.

The managed sandbox identifier was selected over `create_code_interpreter`
because a what-if calculation requires no custom network configuration or
long-lived resource. AWS's own getting-started guidance treats
`aws.codeinterpreter.v1` as the default for this use case.

## Consequences

- **IAM is granted by script, not declared in CDK.** No `agentcore.json`
  field exists for Code Interpreter outside the Harness path this sample
  does not use. `scripts/grant_code_interpreter_access.sh` attaches a
  scoped inline policy — `StartCodeInterpreterSession`,
  `InvokeCodeInterpreter`, `StopCodeInterpreterSession` against
  `arn:aws:bedrock-agentcore:<region>:aws:code-interpreter/aws.codeinterpreter.v1`,
  confirmed against AWS's `InvokeCodeInterpreter` API reference — to the
  runtime execution role after every deploy. This follows the same pattern
  as the CloudFront–Lambda dual-auth fix elsewhere in this sample: scripted
  and idempotent, not a manual one-time command.
- **The code-authoring call is model-gated.** Consistent with SOW grading
  and diagram vision, it is expected to fail in this deployment account
  under the standing Bedrock Marketplace payment-instrument restriction
  documented in the main README's Known Limitations. `run_what_if()`
  degrades to `{"status": "unavailable", "reason": ...}` on that failure,
  the same degradation pattern used for SOW grading. The feature is
  structurally correct and deploys cleanly, but the authoring step is not
  verifiable end-to-end in this account until the restriction is lifted.
- **The sandbox execution call carries no such dependency.** See
  "Verification independent of the Marketplace restriction" below.

## Verification independent of the Marketplace restriction

`StartCodeInterpreterSession`, `InvokeCodeInterpreter`, and
`StopCodeInterpreterSession` were called directly against the deployed IAM
grant, using a hand-written `compute(lines)` snippet in place of the
model-authored one, isolating the sandbox path from the authoring step.
This surfaced one defect before it reached the full agent flow:

**`InvokeCodeInterpreter`'s response is an event stream, not a flat dict.**
The AWS API reference documents the response body as
`{"result": {"content": [...], "structuredContent": {...}}}`. The actual
boto3 response marks `stream` as `eventstream: True` in the service model;
the initial implementation read `response["result"]` directly, which
returned an empty dict without raising an exception. The fix iterates
`response["stream"]` for the event carrying
`result.structuredContent.{stdout,stderr,exitCode}`, matching what the
SDK's own `execute_code()` wrapper does internally.

With the fix applied, a direct sandbox call recomputing a Multi-AZ removal
against a hand-written line-item list returned
`{"new_total_delta": -566.0, "explanation": "..."}` as expected. The
sandbox execution path is confirmed functional independent of the
code-authoring model call's availability in this account.
