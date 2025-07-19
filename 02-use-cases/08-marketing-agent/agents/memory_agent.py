from strands import Agent, tool
from strands_tools import mem0_memory
from typing import Dict, Any, List
import json

# --- Agent Definition ---

system_prompt = f"""You are an intelligent memory manager that automatically identifies and stores valuable information from user conversations.

Your primary role is to:
1. Analyze user input to identify information worth remembering
2. Extract and store meaningful context, preferences, facts, and insights
3. Retrieve relevant memories when needed

What to remember:
- User preferences (likes, dislikes, favorites)
- Business context (company info, products, focus areas)
- Personal details that affect recommendations
- Important facts mentioned in conversation
- Goals and objectives stated by the user
- Constraints or requirements mentioned
- Past decisions and their reasoning

What NOT to remember:
- Temporary queries or one-time requests
- Generic information available elsewhere
- Sensitive personal data unless explicitly relevant

Key Rules:
- Always include the correct user_id in tool calls
- Store information in clear, searchable format
- Be selective - only store genuinely useful information
- Extract the essence, not verbatim quotes
- Focus on actionable insights and context
"""

# --- Tool Definition ---

@tool
def create_memory_agent() -> Agent:
    agent = Agent(system_prompt=system_prompt, tools=[mem0_memory])
    return agent

def analyze_and_store_if_valuable(agent: Agent, user_input: str, user_id: str) -> bool:
    """
    Analyzes user input and automatically stores valuable information.
    Returns True if something was stored, False otherwise.
    """
    analysis_prompt = f"""
    Analyze this user input and determine if it contains information worth remembering for future interactions:
    
    User input: "{user_input}"
    
    STORE if the input contains:
    - Business context ("our company sells X", "we focus on Y", "our target market is Z")
    - Personal preferences ("I prefer X", "I like Y", "my favorite is Z")
    - Goals or objectives ("we want to achieve X", "our goal is Y")
    - Constraints or requirements ("we need X", "we can't do Y", "budget is Z")
    - Important facts about the user/company that affect future recommendations
    - Decisions made and their reasoning
    
    DO NOT STORE if the input is:
    - A simple question or request for information
    - A one-time task ("analyze this data", "create a report")
    - Generic queries without personal context
    - Temporary instructions
    
    If you decide to store something, use mem0_memory tool with action="store" and extract the key information clearly.
    If nothing should be stored, respond with exactly "NOTHING_TO_STORE".
    
    Examples:
    - "Our company sells desks and chairs but focuses more on desks" → STORE: "Company sells desks and chairs with primary focus on desks"
    - "I prefer detailed reports with charts" → STORE: "User prefers detailed reports with visual charts"
    - "What are the latest AI trends?" → NOTHING_TO_STORE
    """
    
    try:
        response = agent(analysis_prompt)
        response_text = str(response).upper()
        
        # If the agent used the mem0_memory tool, something was stored
        if "NOTHING_TO_STORE" not in response_text:
            return True
        else:
            # Add a newline after NOTHING_TO_STORE to separate from any following output
            print("\n")  # Clean separation
        return False
    except Exception as e:
        print(f"\nMemory analysis failed: {e}\n")
        return False

def store_memory(agent: Agent, content: str, user_id: str):
    """Direct memory storage for explicit requests."""
    agent.tool.mem0_memory(
        action="store",
        content=content,
        user_id=user_id 
    )

def retrieve_memories(agent: Agent, query: str, user_id: str) -> List[Dict]:
    """Retrieve relevant memories for a query."""
    memories = agent.tool.mem0_memory(
        action="retrieve",
        query=query,
        user_id=user_id
    )

    memories_list = json.loads(memories["content"][0]['text'])
    return memories_list

