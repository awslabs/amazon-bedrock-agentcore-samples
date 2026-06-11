"""Sanitize fetched web content to mitigate indirect prompt injection.

Strips HTML comments, removes invisible unicode characters, and redacts
known prompt injection patterns before content is passed to the LLM.
Works alongside Amazon Bedrock Guardrail for defense-in-depth.
"""

import re
import unicodedata


# Patterns commonly used in prompt injection attempts
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above\s+instructions",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?(your\s+)?instructions",
    r"you\s+are\s+now\s+a",
    r"new\s+instructions?\s*:",
    r"system\s*:",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[INST\]",
    r"\[/INST\]",
    r"<<SYS>>",
    r"<</SYS>>",
    r"Human\s*:",
    r"Assistant\s*:",
]

_INJECTION_RE = re.compile(
    "|".join(_INJECTION_PATTERNS), re.IGNORECASE
)

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

_INVISIBLE_CATEGORIES = {"Cf", "Cc", "Co"}
_KEEP_CHARS = {"\n", "\r", "\t", " "}


def sanitize_web_content(text: str) -> str:
    """Clean fetched web text to reduce prompt injection risk.

    Applies three layers of protection:
    1. Strips HTML comments (attackers often hide instructions in them)
    2. Removes invisible unicode characters (zero-width chars bypass regex)
    3. Redacts known prompt injection patterns
    """
    text = _HTML_COMMENT_RE.sub("", text)

    text = "".join(
        ch for ch in text
        if ch in _KEEP_CHARS or unicodedata.category(ch) not in _INVISIBLE_CATEGORIES
    )

    text = _INJECTION_RE.sub("[REDACTED]", text)

    return text.strip()
