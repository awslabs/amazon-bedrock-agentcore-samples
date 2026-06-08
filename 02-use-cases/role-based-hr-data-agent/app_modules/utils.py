"""Utility helpers for the Streamlit frontend."""

import re


def make_urls_clickable(text: str) -> str:
    """Wrap bare URLs in <a> tags."""
    pattern = r"(https?://[^\s\)\]\"']+)"
    return re.sub(pattern, r'<a href="\1" target="_blank">\1</a>', text)


def create_safe_markdown_text(text: str) -> str:
    """Convert newlines to <br> for safe HTML rendering."""
    return text.replace("\n", "<br>")
