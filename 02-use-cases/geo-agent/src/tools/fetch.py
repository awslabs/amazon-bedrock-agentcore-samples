"""Shared utility for fetching and extracting text content from web pages.

Uses trafilatura for clean text extraction when available, with a
fallback HTML tag-stripping parser for environments without it.
"""

import requests
from urllib.parse import urlparse

DEFAULT_UA = "Mozilla/5.0 (compatible; GEOAgent/1.0)"
BOT_UA = "Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)"

_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "169.254.169.254", "[::1]"}


def _validate_url(url: str) -> None:
    """Validate that a URL is safe to fetch (not internal/private)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise ValueError(f"Blocked: unsupported scheme '{parsed.scheme}'")
    host = parsed.hostname or ""
    if host in _BLOCKED_HOSTS or host.startswith(("10.", "172.", "192.168.")):
        raise ValueError(f"Blocked: disallowed host '{host}'")


def fetch_page_text(url: str, include_links: bool = False, user_agent: str = DEFAULT_UA) -> str:
    """Fetch a web page and return its text content.

    Uses trafilatura for clean text extraction if available,
    falls back to simple HTML tag stripping.

    Args:
        url: The full URL to fetch.
        include_links: Whether to preserve links in extracted text (for llms.txt).
        user_agent: Custom User-Agent string for the request.
    """
    _validate_url(url)
    headers = {"User-Agent": user_agent}
    resp = requests.get(url, headers=headers, timeout=30)  # URL validated above via _validate_url
    resp.raise_for_status()

    try:
        import trafilatura
        text = trafilatura.extract(
            resp.text,
            include_links=include_links,
            with_metadata=True,
        )
        if text:
            return text
    except ImportError:
        pass

    # Fallback: strip HTML tags
    from html.parser import HTMLParser

    class _TextExtractor(HTMLParser):
        """Simple HTML parser that extracts visible text, skipping script/style blocks."""

        def __init__(self):
            super().__init__()
            self.parts = []
            self._skip = False

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "noscript"):
                self._skip = True

        def handle_endtag(self, tag):
            if tag in ("script", "style", "noscript"):
                self._skip = False

        def handle_data(self, data):
            if not self._skip:
                self.parts.append(data)

    extractor = _TextExtractor()
    extractor.feed(resp.text)
    return " ".join(extractor.parts).strip()
