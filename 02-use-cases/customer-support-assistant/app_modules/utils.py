import re


def make_urls_clickable(text):
    """Convert URLs in text to clickable HTML links."""
    url_pattern = r"https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?"

    def replace_url(match):
        url = match.group(0)
        return f'<a href="{url}" target="_blank" style="color:#4fc3f7;text-decoration:underline;">{url}</a>'

    return re.sub(url_pattern, replace_url, text)


def create_safe_markdown_text(text, message_placeholder):
    """Create safe markdown text with proper encoding"""
    safe_text = text.encode("utf-16", "surrogatepass").decode("utf-16")
    message_placeholder.markdown(
        safe_text.replace("\\n", "<br>"), unsafe_allow_html=True
    )
