"""
HRResponseLength — Code-Based Evaluator (TRACE level)

Uses the SDK 1.6 @custom_code_based_evaluator() decorator.
Checks that the agent's response is between MIN_LENGTH and MAX_LENGTH characters.
Strips thinking blocks (<thinking>...</thinking>) before measuring.

Returns:
    value       — 1.0 (PASS) if within range, 0.0 (FAIL) otherwise
    label       — "PASS" or "FAIL"
    explanation — actual length and acceptable range
"""
import re

from bedrock_agentcore.evaluation import (
    EvaluatorInput,
    EvaluatorOutput,
    custom_code_based_evaluator,
)

MIN_LENGTH = 50
MAX_LENGTH = 600

_THINKING_RE = re.compile(r"<thinking>.*?</thinking>", re.DOTALL)


def _extract_final_response(spans: list) -> str:
    """Extract final visible response text from the invoke_agent span."""
    for span in spans:
        name = (span.get("name") or "").lower()
        if "invoke_agent" not in name:
            continue
        for se in span.get("span_events", []):
            body = se.get("body", {})
            if not isinstance(body, dict):
                continue
            for msg in body.get("output", {}).get("messages", []):
                content = msg.get("content", {})
                if isinstance(content, dict):
                    text = content.get("message", "")
                    if text:
                        cleaned = _THINKING_RE.sub("", text).strip()
                        if cleaned:
                            return cleaned
    return ""


@custom_code_based_evaluator()
def lambda_handler(input: EvaluatorInput, context) -> EvaluatorOutput:
    spans = input.session_spans

    # For TRACE level, target_trace_id identifies which trace to evaluate.
    # The decorator already sets input.target_trace_id from the event payload.
    if input.evaluation_level == "TRACE" and input.target_trace_id:
        spans = [s for s in spans
                 if s.get("traceId") == input.target_trace_id
                 or s.get("trace_id") == input.target_trace_id]

    output_text = _extract_final_response(spans)

    if not output_text:
        # Fallback: try any span_events with a non-empty content message
        for span in reversed(spans):
            for se in span.get("span_events", []):
                body = se.get("body", {})
                if not isinstance(body, dict):
                    continue
                for msg in (body.get("output", {}) or {}).get("messages", []):
                    content = msg.get("content", {})
                    text = (content.get("message") or "") if isinstance(content, dict) else ""
                    cleaned = _THINKING_RE.sub("", text).strip()
                    if cleaned and not cleaned.startswith("[{"):
                        output_text = cleaned
                        break
                if output_text:
                    break
            if output_text:
                break

    if not output_text:
        return EvaluatorOutput(
            label="FAIL",
            errorCode="NoResponseFound",
            errorMessage=(
                f"No agent response text found in {len(spans)} spans. "
                "Expected invoke_agent span with span_events containing output message."
            ),
        )

    length = len(output_text)

    if MIN_LENGTH <= length <= MAX_LENGTH:
        return EvaluatorOutput(
            value=1.0,
            label="PASS",
            explanation=(
                f"Response length {length} chars is within the acceptable range "
                f"[{MIN_LENGTH}, {MAX_LENGTH}]."
            ),
        )
    elif length < MIN_LENGTH:
        return EvaluatorOutput(
            value=0.0,
            label="FAIL",
            explanation=(
                f"Response length {length} chars is too short (minimum {MIN_LENGTH}). "
                f'Preview: "{output_text[:60]}..."'
            ),
        )
    else:
        return EvaluatorOutput(
            value=0.0,
            label="FAIL",
            explanation=(
                f"Response length {length} chars exceeds maximum {MAX_LENGTH}. "
                "Consider a more concise answer."
            ),
        )
