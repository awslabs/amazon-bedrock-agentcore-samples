"""What-if pricing — AgentCore Code Interpreter (optional Phase 6).

A reviewer can ask a plain-language "what if" question about the cost
estimate (e.g. "what if we used Reserved Instances instead of on-demand" or
"what if traffic doubled"). Rather than let a model state a recomputed
number from memory — the one thing core/pricing.py exists specifically to
avoid, see its own module docstring — the model authors a short Python
function against the *real* CostEstimate line items, and that function runs
in AgentCore's managed Code Interpreter sandbox, not eval()'d in-process.
The reviewer gets back the code that ran, not just a number to trust.

Uses the AWS-managed public sandbox (`aws.codeinterpreter.v1`) — no custom
Code Interpreter resource to provision or tear down. See docs/decisions/0010.

Like SOW grading and diagram vision, the code-authoring step is a model
call and is wrapped in the same graceful-degradation pattern used
everywhere else in this project: on failure (including this account's
standing Bedrock Marketplace restriction) the caller gets a clear
"unavailable" result with a reason, never a hard failure of the rest of
the review.
"""

from __future__ import annotations

import json
import re

from bedrock_agentcore.tools.code_interpreter_client import code_session
from config import FAST_MODEL_ID, REGION
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

_last_whatif_code: str = ""


def get_last_whatif_code() -> str:
    return _last_whatif_code


def reset_whatif_state() -> None:
    global _last_whatif_code
    _last_whatif_code = ""


def record_whatif_code(code: str) -> str:
    """Plain implementation behind the submit_whatif_code tool, separated
    so it can be unit-tested without constructing an Agent — same pattern
    as tools/structured_output.py."""
    global _last_whatif_code
    _last_whatif_code = code
    return "Code recorded."


@tool
def submit_whatif_code(code: str) -> str:
    """Submit the Python code that answers the what-if pricing question.

    Call this ONCE. Write a `compute(lines)` function — `lines` is a list of
    dicts (node_name, driver, driver_label, quantity, unit_rate,
    monthly_cost, is_premium) that will be injected as a variable named
    `lines` before your code runs. Do not invent line items or rates that
    are not in `lines` — recompute using only what's given; if the question
    needs a rate you don't have, say so in the explanation instead of
    guessing. Finish your code with
    `print(json.dumps(compute(lines)))` so the result can be parsed back out.

    Args:
        code: Complete Python source: the compute() function definition,
            plus a trailing `print(json.dumps(compute(lines)))` call.
    """
    return record_whatif_code(code)


WHATIF_PROMPT = """You translate a plain-language "what if" pricing question \
into a short, self-contained Python function that recomputes a cost total \
from real AWS cost line items — never state a number yourself.

You will be given the current cost line items as JSON and a question. Write \
Python that operates ONLY on the given `lines` list (each item has \
node_name, driver, driver_label, quantity, unit_rate, monthly_cost, \
is_premium) to compute the answer. Do not fetch external data, do not \
import network or filesystem modules, do not fabricate a rate that isn't \
in `lines` — if the question needs information you don't have, return an \
explanation saying so instead of guessing a number.

You MUST finish by calling the submit_whatif_code tool exactly once.
"""


def _extract_json_tail(text: str):
    """Same trailing-JSON scan used elsewhere in this project (e.g. the web
    layer's Lambda) for output that mixes prose/print statements with a
    final JSON object."""
    trimmed = text.rstrip()
    decoder = json.JSONDecoder()
    for match in reversed(list(re.finditer(r"\{", trimmed))):
        try:
            obj, end = decoder.raw_decode(trimmed, match.start())
        except json.JSONDecodeError:
            continue
        if end == len(trimmed):
            return obj
    return None


def run_what_if(question: str, cost_lines: list[dict]) -> dict:
    """Answer a what-if pricing question. Always returns a JSON-serialisable
    dict with a `status` key (`ok` or `unavailable`) — callers never need to
    guard against an exception escaping this function.
    """
    reset_whatif_state()
    try:
        author = Agent(
            model=BedrockModel(model_id=FAST_MODEL_ID),
            system_prompt=WHATIF_PROMPT,
            tools=[submit_whatif_code],
        )
        author(
            "Cost line items:\n"
            + json.dumps(cost_lines, indent=2)
            + "\n\nQuestion: "
            + question
        )
        code = get_last_whatif_code()
        if not code.strip():
            return {
                "status": "unavailable",
                "question": question,
                "reason": "Model did not produce a code submission.",
            }
    except Exception as exc:  # noqa: BLE001 — model access is expected to be blocked in this account
        return {
            "status": "unavailable",
            "question": question,
            "reason": f"Code-authoring model call failed: {exc}",
        }

    try:
        with code_session(REGION) as sandbox:
            response = sandbox.execute_code(
                code=f"lines = {cost_lines!r}\n\n" + code,
                language="python",
            )
        # InvokeCodeInterpreter's output is an EventStream (confirmed against
        # the real API, not assumed from the API reference doc alone — a
        # plain dict response has no `result` key at all, it's nested one
        # level down inside each streamed event). Collect the last event
        # carrying a `result`, then read structuredContent.{stdout,stderr}.
        structured = {}
        for event in response.get("stream", []):
            result = event.get("result")
            if result:
                structured = result.get("structuredContent", {}) or {}
        stdout = structured.get("stdout", "")
        stderr = structured.get("stderr", "")
        computed = _extract_json_tail(stdout) if stdout else None
        return {
            "status": "ok",
            "question": question,
            "code": code,
            "stdout": stdout,
            "stderr": stderr,
            "computed": computed,
        }
    except Exception as exc:  # noqa: BLE001 — sandbox may be unavailable in this account/region
        return {
            "status": "unavailable",
            "question": question,
            "code": code,
            "reason": f"Code Interpreter sandbox call failed: {exc}",
        }
