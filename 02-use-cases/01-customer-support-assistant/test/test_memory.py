from bedrock_agentcore.memory import MemoryClient
from strands import Agent
from strands_tools import calculator
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from memory_hook_provider import MemoryHookProvider
from scripts.utils import get_ssm_parameter

# Load memory ID from SSM
memory_id = get_ssm_parameter("/app/customersupport/agentcore/memory_id")
client = MemoryClient()

# Session & actor configuration
ACTOR_ID = "default"
SESSION_ID = "test"

# Setup memory hooks
memory_hooks = MemoryHookProvider(
    memory_id=memory_id,
    client=client,
    actor_id=ACTOR_ID,
    session_id=SESSION_ID,
)

# Initialize agent with memory and tools
agent = Agent(
    hooks=[memory_hooks],
    tools=[calculator],
    system_prompt="You are a helpful personal math assistant.",
)

# Interactive prompt loop
print("🧮 Interactive Math Agent")
print("Type your question (or 'q' to quit):")

while True:
    user_input = input("You > ").strip()
    if user_input.lower() in {"q", "quit"}:
        print("👋 Exiting session.")
        break

    try:
        print(f"Agent >")
        response = agent(user_input)
    except Exception as e:
        print(f"❌ Error: {e}")
