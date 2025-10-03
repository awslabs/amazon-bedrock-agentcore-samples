import logging
from strands.tools import tool
from ..database_agent import DatabaseAgent
from ..config import config

logger = logging.getLogger(__name__)

@tool
def database_query_agent(instructions: str) -> str:
    """Launch a database query agent to handle DynamoDB data retrieval operations.

    Args:
        instructions: Task instructions for database queries and data retrieval
    
    Returns:
        Database query results and retrieved data as text
    """
    try:
        agent = DatabaseAgent(config)
        results = agent(instructions)
        return str(results)

    except Exception as e:
        logger.error(f"Error creating database query agent: {str(e)}")
        return f"An error occurred while setting up the database query agent: {str(e)}"