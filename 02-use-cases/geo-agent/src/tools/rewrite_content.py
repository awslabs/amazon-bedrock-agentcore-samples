"""Tool to rewrite content for Generative Engine Optimization (GEO).

Uses a dedicated Strands sub-agent with the shared GEO rewrite prompt
to transform raw content into a GEO-optimized format.
"""

from strands import tool
from tools.prompts import GEO_REWRITE_PROMPT

REWRITE_SYSTEM_PROMPT = GEO_REWRITE_PROMPT + """

Output the fully rewritten content. Do not explain what you changed — just output the optimized version."""


@tool
def rewrite_content_for_geo(content: str) -> str:
    """Rewrite and optimize content for Generative Engine Optimization (GEO).

    Takes raw content and rewrites it following GEO best practices to maximize
    visibility, inclusion, and citation in AI-generated responses. Applies clear
    structure, data enrichment, E-E-A-T signals, and Q&A formatting.

    Args:
        content: The raw content text to be rewritten and optimized for GEO.
    """
    from model.load import load_model
    from strands import Agent

    model = load_model()
    rewriter = Agent(model=model, system_prompt=REWRITE_SYSTEM_PROMPT, tools=[])
    result = rewriter(content)
    return f"=== REWRITTEN CONTENT START ===\n{str(result)}\n=== REWRITTEN CONTENT END ==="
