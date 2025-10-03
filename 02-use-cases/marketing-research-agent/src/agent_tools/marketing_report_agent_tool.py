import logging
from strands.tools import tool
from ..reporting_agent import ReportingAgent
from ..config import config

logger = logging.getLogger(__name__)

@tool
def marketing_report_agent(instructions: str) -> str:
    """Generate and return a marketing research report as text response.

    Args:
        instructions: Task instructions including all research findings and report requirements
    
    Returns:
        A comprehensive marketing research report as formatted text
    """
    try:
        agent = ReportingAgent(config)
        results = agent(instructions)
        return str(results)

    except Exception as e:
        logger.error(f"Error creating reporting agent: {str(e)}")
        return f"An error occurred while setting up the reporting agent: {str(e)}"