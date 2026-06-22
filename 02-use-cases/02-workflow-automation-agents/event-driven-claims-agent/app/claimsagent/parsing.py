"""Pure text-parsing fallbacks for the dual-agent pipeline.

These functions extract structured fields from the agents' free-text output when
the structured-output tools (``tools.structured_output``) were not called. They
are intentionally dependency-free (stdlib ``re`` only) so they can be unit-tested
without the AgentCore/Strands runtime — see ``tests/test_parsing.py``.
"""

import re


def parse_confidence(text: str) -> int:
    """Extract the validator's confidence score (0-100) from its output.

    Returns 50 (→ human review) when no score is found, a safe default that
    routes ambiguous cases to a human rather than auto-approving.
    """
    match = re.search(r"CONFIDENCE:\s*(\d+)", text)
    if match:
        return int(match.group(1))
    return 50


def parse_decision(text: str) -> str:
    """Extract the processor's ACCEPT/REJECT decision from its output.

    Falls back to REJECT (the conservative default) when no clear decision is
    found, so an unparseable response never results in an unintended approval.
    """
    match = re.search(r"DECISION[:\s*\*]*\s*(ACCEPT|REJECT)", text, re.IGNORECASE)
    if not match:
        match = re.search(r"DECISION.*?(ACCEPT|REJECT)", text[:500], re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).upper()
    # Fallback: standalone ACCEPT with no REJECT nearby avoids false positives
    if re.search(r"\bACCEPT\b", text[:500]) and not re.search(r"\bREJECT\b", text[:500]):
        return "ACCEPT"
    return "REJECT"
