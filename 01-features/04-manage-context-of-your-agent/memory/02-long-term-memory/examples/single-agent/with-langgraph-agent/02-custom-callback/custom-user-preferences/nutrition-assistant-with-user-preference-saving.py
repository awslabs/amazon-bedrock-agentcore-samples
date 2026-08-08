#!/usr/bin/env python

# # LangGraph with AgentCore Memory Middlewares (Long-term Memory)
#
# ## Introduction
#
# This example demonstrates how to integrate Amazon Bedrock AgentCore Memory capabilities with a conversational AI agent using **LangGraph** framework with the **middleware system**. We'll focus on **long-term memory** retention across multiple conversation sessions - allowing an agent to extract and recall user preferences, dietary restrictions, and contextual information from past interactions.
#
# ## Tutorial Details
#
# | Information         | Details                                                                          |
# |:--------------------|:---------------------------------------------------------------------------------|
# | Tutorial type       | Long-term Conversational                                                        |
# | Agent usecase       | Nutrition Assistant                                                              |
# | Agentic Framework   | LangGraph (with Middlewares)                                                    |
# | LLM model           | Anthropic Claude Haiku 4.5                                                     |
# | Tutorial components | AgentCore Long-term Memory, Memory Strategies, `@before_agent`/`@after_agent` Middlewares |
# | Example complexity  | Intermediate                                                                     |
#
# You'll learn to:
# - Create AgentCore Memory with UserPreference and Semantic strategies
# - Implement **`@before_agent` and `@after_agent` middlewares** for automatic memory storage and retrieval (once per agent call, more efficient!)
# - Build a nutrition assistant that remembers user preferences across sessions
# - Use semantic search to retrieve relevant user context
#
# ## Architecture
#
# <div style="text-align:left">
#     <img src="architecture.png" width="55%" />
# </div>
#
# ### Scenario Context
#
# In this example, we'll create a **Nutrition Assistant** that can remember user context across multiple conversations, including dietary restrictions, favorite foods, cooking preferences, and health goals. The agent will automatically extract and store user preferences from conversations, then retrieve relevant context for future interactions to provide personalized nutrition advice.
#
# ## Prerequisites
#
# - Python 3.10+
# - AWS account with appropriate permissions
# - Access to Amazon Bedrock models
#
# Let's get started by setting up our environment!


import os
import logging
from typing import Any

# Import LangGraph components
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain.agents.middleware import before_agent, after_agent, AgentState
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime


region = os.getenv("AWS_REGION", "us-east-1")
logging.getLogger("nutrition-agent").setLevel(logging.DEBUG)
logging.getLogger("bedrock_agentcore_starter_toolkit").setLevel(logging.WARNING)


# Import Memory components
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from bedrock_agentcore.memory import MemoryClient  # noqa: E402
from bedrock_agentcore.memory.constants import StrategyType  # noqa: E402

# Using MemoryManager from starter toolkit (simpler API)
from bedrock_agentcore_starter_toolkit.operations.memory.manager import (  # noqa: E402
    MemoryManager,
)


# ## Step 1: Create the Memory Resource
#
# Memory configuration using **built-in strategies**, which do not require an IAM execution role.


memory_name = "Nutrition_Assistant"
MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

# Using MemoryManager for simpler memory creation (no IAM role required for built-in strategies)
memory_manager = MemoryManager(region_name=region)

memory = memory_manager.get_or_create_memory(
    name=memory_name,
    strategies=[
        # Strategy 1: User Preferences (food preferences, dietary restrictions)
        {
            StrategyType.USER_PREFERENCE.value: {
                "name": "NutritionPreferences",
                "description": "Captures user food preferences and dietary behavior",
                "namespaces": ["nutrition/{actorId}/preferences"],
            }
        },
        # Strategy 2: Semantic Memory (factual information from conversations)
        {
            StrategyType.SEMANTIC.value: {
                "name": "NutritionFacts",
                "description": "Stores factual information from conversations",
                "namespaces": ["nutrition/{actorId}/facts"],
            }
        },
    ],
)

memory_id = memory.get("id")
print(f"✅ Memory resource is ACTIVE with ID: {memory_id}")


# ### Memory Configuration Overview
#
# Our AgentCore Memory setup uses **built-in strategies** (no IAM role required):
#
# - **USER_PREFERENCE Strategy**: Automatically extracts user preferences from conversations
# - **SEMANTIC Strategy**: Stores factual information mentioned in conversations
# - **Namespaces**:
#   - `nutrition/{actorId}/preferences` - User food preferences
#   - `nutrition/{actorId}/facts` - Factual information
#
# The memory system will automatically process conversations to extract lasting user preferences while filtering out temporary or irrelevant information.
#
# > 💡 **Tip**: For custom extraction/consolidation prompts, use `StrategyType.CUSTOM` with `MemoryClient` (requires `memory_execution_role_arn`).
#
# ## Step 2: Initialize Memory Client and LLM
#
# Now we'll initialize the AgentCore Memory client and our language model.


# Initialize Bedrock LLM
llm = init_chat_model(MODEL_ID, model_provider="bedrock_converse", region_name=region)

# Optional: Initialize checkpointer for short-term memory (conversation continuity within session)
# from langgraph_checkpoint_aws import AgentCoreMemorySaver
# checkpointer = AgentCoreMemorySaver(memory_id=memory_id, region_name=region)

print(f"✅ LLM initialized: {MODEL_ID}")


# ## Step 3: Implement Memory Middlewares
#
# We'll create middlewares to automatically handle memory storage and retrieval:
#
# - **`@before_agent`**: Retrieves relevant user preferences (based on semantic search) and adds context **once per agent call** (more efficient than per-model call)
# - **`@after_agent`**: Saves the conversation messages for long-term memory extraction **once per agent call**
#
# > 💡 **Why `@before_agent`/`@after_agent` instead of `@before_model`/`@after_model`?**
# > Agent-level middlewares run once per agent invocation, while model-level middlewares run every time the
# > LLM is called (which can happen multiple times in a single agent call when using tools). For memory
# > retrieval and saving, once per agent call is sufficient and more efficient.
#
# ### How Memory Processing Works
#
# 1. Messages are saved to AgentCore Memory with actor_id and session_id
# 2. The strategies process conversations to extract nutrition preferences and facts
# 3. Extracted preferences are stored in the `{actorId}/preferences` namespace
# 4. Future conversations can search and retrieve relevant preferences for context
#
# **Note**: LangChain message types are converted under the hood by the store to AgentCore Memory message types so that they can be properly extracted to long term memories.


# Initialize MemoryClient for direct memory operations
memory_client = MemoryClient(region_name=region)

# Global variables for memory context (set before agent invocation)
ACTOR_ID = "default_user"
SESSION_ID = "default_session"

BASE_PROMPT = """You are a helpful nutrition assistant. You remember user preferences and provide personalized advice."""


def configure_memory_context(actor_id: str, session_id: str):
    """Configure the memory context for middlewares."""
    global ACTOR_ID, SESSION_ID
    ACTOR_ID = actor_id
    SESSION_ID = session_id


@before_agent
def retrieve_from_memory(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """
    BEFORE agent middleware: Retrieve memories and inject into context (runs once per agent call).
    """
    messages = state.get("messages", [])

    # Get last user message for semantic search
    last_user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    if not last_user_msg:
        return None

    # Search memories using MemoryClient
    memory_context = []

    # Search preferences namespace
    try:
        prefs = memory_client.retrieve_memories(
            memory_id=memory_id,
            namespace=f"nutrition/{ACTOR_ID}/preferences",
            query=last_user_msg,
        )
        for p in prefs[:3]:
            if isinstance(p, dict):
                content = p.get("content", {})
                text = content.get("text", str(content)) if isinstance(content, dict) else str(content)
                memory_context.append(f"Preference: {text}")
    except Exception as e:
        logging.debug(f"Preference retrieval error: {e}")

    # Search facts namespace
    try:
        facts = memory_client.retrieve_memories(
            memory_id=memory_id,
            namespace=f"nutrition/{ACTOR_ID}/facts",
            query=last_user_msg,
        )
        for f in facts[:3]:
            if isinstance(f, dict):
                content = f.get("content", {})
                text = content.get("text", str(content)) if isinstance(content, dict) else str(content)
                memory_context.append(f"Fact: {text}")
    except Exception as e:
        logging.debug(f"Fact retrieval error: {e}")

    # Inject memories into system prompt
    if memory_context:
        logging.info(f"📚 Found {len(memory_context)} memories for {ACTOR_ID}")
        enhanced_prompt = BASE_PROMPT + "\n\nWhat you know about this user:\n" + "\n".join(memory_context)
        new_msgs = [SystemMessage(content=enhanced_prompt)] + [
            m for m in messages if not isinstance(m, SystemMessage)
        ]
        return {"messages": new_msgs}
    else:
        logging.info(f"📭 No memories found for {ACTOR_ID}")

    return None


@after_agent
def save_to_memory(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """
    AFTER agent middleware: Save conversation to memory (runs once per agent call).
    """
    messages = state.get("messages", [])

    # Extract latest conversation turn
    human_msg, ai_msg = None, None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and ai_msg is None:
            ai_msg = msg.content
        elif isinstance(msg, HumanMessage) and human_msg is None:
            human_msg = msg.content
        if human_msg and ai_msg:
            break

    # Save to AgentCore Memory
    if human_msg and ai_msg:
        try:
            memory_client.create_event(
                memory_id=memory_id,
                actor_id=ACTOR_ID,
                session_id=SESSION_ID,
                messages=[
                    (human_msg, "USER"),
                    (ai_msg, "ASSISTANT"),
                ],
            )
            logging.info(f"💾 Saved conversation to memory for {ACTOR_ID}")
        except Exception as e:
            logging.error(f"Memory save error: {e}")

    return None


print("✅ Middlewares created: retrieve_from_memory, save_to_memory")


# ## Step 4: Create the LangGraph Agent
#
# Now we'll create our nutrition assistant agent using **LangGraph's `create_agent`** with our memory middlewares integrated.
#
# **Note**: For custom agent implementations, the middlewares can be composed and extended as needed for any workflow following this pattern.


# Create agent with LangGraph create_agent and middlewares
graph = create_agent(
    llm,
    tools=[],  # No additional tools needed for this example
    middleware=[retrieve_from_memory, save_to_memory],  # Middleware pattern
    checkpointer=InMemorySaver(),  # For conversation state management
)


# ## Step 5: Configure Agent Runtime
#
# We need to configure the agent with unique identifiers for the user and session. These IDs are crucial for memory organization and retrieval.
#
# ### Graph Invoke Input
# We only need to pass the newest user message in as an argument `inputs`. This could include other state variables as well but for the simple `create_agent`, we only need messages.
#
# ### LangGraph RuntimeConfig
# In LangGraph, config is a `RuntimeConfig` that contains attributes that are necessary at invocation time, for example user IDs or session IDs. For the `AgentCoreMemorySaver`, `thread_id` and `actor_id` must be set in the config. For instance, your AgentCore invocation endpoint could assign this based on the identity or user ID of the caller. You can read additional [documentation here](https://langchain-ai.github.io/langgraphjs/how-tos/configuration/)


actor_id = "test-user"
session_id = "test-session"

# Configure memory context for middlewares
configure_memory_context(actor_id, session_id)

config = {
    "configurable": {
        "thread_id": session_id,  # REQUIRED: This maps to Bedrock AgentCore session_id under the hood
        "actor_id": actor_id,  # REQUIRED: This maps to Bedrock AgentCore actor_id under the hood
    }
}

print(f"✅ Configured for actor={actor_id}, session={session_id}")


# ## Step 6: Test the Agent
#
# Let's test our nutrition assistant by having a conversation about food preferences. The agent will automatically extract and store user preferences for future use.


# Helper function to pretty print agent output while running
def run_agent(query: str, config: RunnableConfig):
    printed_ids = set()
    events = graph.stream(
        {"messages": [{"role": "user", "content": query}]},
        config,
        stream_mode="values",
    )
    for event in events:
        if "messages" in event:
            for msg in event["messages"]:
                # Check if we've already printed this message
                if id(msg) not in printed_ids:
                    msg.pretty_print()
                    printed_ids.add(id(msg))


prompt = """
Hey there! Im cooking one of my favorite meals tonight, salmon with rice and veggies (healthy). Has
great macros for my weightlifting competition that is coming up. What can I add to this dish to make it taste better
and also improve the protein and vitamins I get?
"""

run_agent(prompt, config)


# ### What was stored?
# As you can see, the model does not yet have any insight into our preferences or dietary restrictions.
#
# For this implementation with `@before_agent` and `@after_agent` middlewares, two messages were stored here. The first message from the user and the response from the AI model were both stored as conversational events in AgentCore Memory. It may take a few moments for the long term memories to be extracted, so retry after a few seconds if nothing is found the first try.
#
# These messages were then extracted to AgentCore long term memory in our fact and user preferences namespaces. In fact, we can check the store ourselves to verify what has been stored there so far:


# Check what's been stored in memory
print(f"🔍 Checking memories for: {actor_id}")
print("=" * 60)

print("\n📋 PREFERENCES:")
prefs = memory_client.retrieve_memories(
    memory_id=memory_id,
    namespace=f"nutrition/{actor_id}/preferences",
    query="food preferences",
)
for p in prefs[:5]:
    text = p.get("content", {}).get("text", str(p)) if isinstance(p, dict) else str(p)
    print(f"  • {text}")
if not prefs:
    print("  (none yet - memories take ~30s to extract)")

print("\n📚 FACTS:")
facts = memory_client.retrieve_memories(
    memory_id=memory_id,
    namespace=f"nutrition/{actor_id}/facts",
    query="user facts",
)
for f in facts[:5]:
    text = f.get("content", {}).get("text", str(f)) if isinstance(f, dict) else str(f)
    print(f"  • {text}")
if not facts:
    print("  (none yet - memories take ~30s to extract)")


# ### Agent access to the store
#
# **Note** - since AgentCore memory processes these events in the background, it may take a few seconds for the memory to be extracted and embedded to long term memory retrieval.
#
# Great! Now we have seen that long term memories were extracted to our namespaces based on the earlier messages in the conversation.
#
# Now, let's start a new session and ask about recommendations for what to cook for dinner. The agent can use the store to access the long term memories that were extracted to make a recommendation that the user will be sure to like.


# New session with same user
session_id = "session-2"

# Update memory context for new session
configure_memory_context(actor_id, session_id)

config = {
    "configurable": {
        "thread_id": session_id,  # New session ID
        "actor_id": actor_id,  # Same actor ID
    }
}

print(f"✅ New session: {session_id}")
run_agent("Today's a new day, what should I make for dinner tonight?", config)


# ### Wrapping up
#
# As you can see, the agent received context from the `@before_agent` middleware (user preferences namespace search) and was able to search on its own for long term memories in the fact namespace to create a comprehensive answer for the user.
#
# The AgentCoreMemoryStore is very flexible and can be implemented in a variety of ways, including `@before_agent`/`@after_agent` middlewares or just tools themselves with store operations. Used alongside the AgentCoreMemorySaver for checkpointing, both full conversational state and long term insights can be combined to form a complex and intelligent agent system.
