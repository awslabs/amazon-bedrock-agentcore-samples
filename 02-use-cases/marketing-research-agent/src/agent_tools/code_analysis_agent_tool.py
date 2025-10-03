import logging
from strands.tools import tool
from ..code_generator_agent import CodeGeneratorAgent
from ..config import config

logger = logging.getLogger(__name__)

@tool
def code_analysis_agent(instructions: str) -> str:
    """Launch a code analysis agent to generate Python code for data analysis operations.

    Args:
        instructions: Task instructions for code generation and data analysis requirements
    
    Returns:
        Generated code and analysis results as text
    """
    try:
        agent = CodeGeneratorAgent(config)
        results = agent(instructions)
        return str(results)

    except Exception as e:
        logger.error(f"Error creating code analysis agent: {str(e)}")
        return f"An error occurred while setting up the code analysis agent: {str(e)}"