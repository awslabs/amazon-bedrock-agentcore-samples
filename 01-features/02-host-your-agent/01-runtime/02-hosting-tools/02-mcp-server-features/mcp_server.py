"""
MCP Server with Advanced Features — Tools, Resources, and Prompts.

Demonstrates the full range of MCP server capabilities supported
by AgentCore Runtime.
"""

import json
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

# stateless_http=True and json_response=True required for AgentCore Runtime compatibility
mcp = FastMCP("advanced-tools", host="0.0.0.0", stateless_http=True, json_response=True)  # nosec B104


# ── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool()
def search_documents(query: str, max_results: int = 5) -> str:
    """Search a document database.

    Args:
        query: Search query string.
        max_results: Maximum number of results to return.

    Returns:
        JSON string with search results.
    """
    # Mock search results
    results = [
        {
            "id": f"doc-{i}",
            "title": f"Document about {query} (#{i})",
            "score": 0.95 - i * 0.1,
        }
        for i in range(min(max_results, 5))
    ]
    return json.dumps(results, indent=2)


@mcp.tool()
def analyze_sentiment(text: str) -> str:
    """Analyze the sentiment of a text.

    Args:
        text: The text to analyze.

    Returns:
        JSON with sentiment analysis results.
    """
    # Mock sentiment analysis
    word_count = len(text.split())
    return json.dumps(
        {
            "sentiment": "positive" if word_count > 5 else "neutral",
            "confidence": 0.87,
            "word_count": word_count,
        }
    )


@mcp.tool()
def get_timestamp() -> str:
    """Get the current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


# ── Resources ────────────────────────────────────────────────────────────────


@mcp.resource("config://app")
def get_app_config() -> str:
    """Application configuration settings."""
    return json.dumps(
        {
            "version": "2.1.0",
            "environment": "production",
            "features": {
                "search": True,
                "sentiment_analysis": True,
                "caching": False,
            },
        },
        indent=2,
    )


@mcp.resource("data://system-status")
def get_system_status() -> str:
    """Current system status and health metrics."""
    return json.dumps(
        {
            "status": "healthy",
            "uptime_hours": 142.5,
            "active_connections": 23,
            "last_check": datetime.now(timezone.utc).isoformat(),
        },
        indent=2,
    )


# ── Prompts ──────────────────────────────────────────────────────────────────


@mcp.prompt()
def code_review(code: str, language: str = "python") -> str:
    """Generate a code review prompt for the given code.

    Args:
        code: The source code to review.
        language: Programming language of the code.
    """
    return (
        f"Please review the following {language} code for:\n"
        f"1. Correctness and potential bugs\n"
        f"2. Performance considerations\n"
        f"3. Security vulnerabilities\n"
        f"4. Code style and readability\n\n"
        f"```{language}\n{code}\n```"
    )


@mcp.prompt()
def summarize_document(document: str, max_length: str = "200 words") -> str:
    """Generate a summarization prompt.

    Args:
        document: The document text to summarize.
        max_length: Maximum length for the summary.
    """
    return (
        f"Summarize the following document in {max_length} or less. "
        f"Focus on key points and actionable insights.\n\n"
        f"Document:\n{document}"
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
