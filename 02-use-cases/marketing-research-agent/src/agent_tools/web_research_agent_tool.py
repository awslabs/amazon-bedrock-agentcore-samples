import logging
from strands.tools import tool
from ..research_agent import ResearchAgent
from ..config import config

logger = logging.getLogger(__name__)

@tool
def web_research_agent(instructions: str) -> str:
    """Launch a web research agent to handle complex, multi-step research tasks.

    Args:
        instructions: Detailed task instructions for the research agent to execute autonomously
    
    Returns:
        Research results and findings as text
    """
    try:
        agent = ResearchAgent(config)
        results = agent(instructions)
        return str(results)

    except Exception as e:
        logger.error(f"Error creating research agent: {str(e)}")
        return f"An error occurred while setting up the research environment: {str(e)}"