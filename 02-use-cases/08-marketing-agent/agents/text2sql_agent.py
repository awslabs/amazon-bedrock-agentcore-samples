import logging
from strands import Agent, tool

logger = logging.getLogger(__name__)

# --- Agent Definition ---
system_prompt = """
You are an NL2SQL agent that converts natural language questions into SQL queries.

Your task is to:
1. Understand the user's question
2. Generate a valid SQL query that answers the question
3. If provided with an error message, correct your SQL query
4. If you are unable to retrieve the schema fully, call get_schema with bool flag=True

When generating SQL:
- Use standard SQL syntax compatible with Amazon Athena
- Include appropriate table joins when needed
- Use column names exactly as they appear in the schema

Example response format:
Query: "SELECT customer_id, name FROM customers WHERE account_status = 'active'"
Results:
customer_id | name
1 | Jane Doe
2 | John Doe

If you receive an error, carefully analyze it and fix your query.
"""

# --- Tool Definition ---

@tool
def create_nl2sql_agent(query: str) -> str:
    """
    Create and configure the NL2SQL agent with appropriate tools and system prompt.
    
    Returns:
        Agent: Configured Strands agent instance
    """
    
    # Create the agent with tools and system prompt

    agent = Agent(
        system_prompt=system_prompt,
        messages=[]
    )

    response = agent(query)

    print("\n\n")
    
    return response