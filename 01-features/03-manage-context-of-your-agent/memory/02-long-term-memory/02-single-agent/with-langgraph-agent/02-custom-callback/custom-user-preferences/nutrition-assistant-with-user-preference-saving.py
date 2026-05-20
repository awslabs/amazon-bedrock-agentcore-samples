#!/usr/bin/env python

# # LangGraph with AgentCore Memory Hooks (Long-term Memory)
#
# ## Introduction
#
# This notebook demonstrates how to integrate Amazon Bedrock AgentCore Memory capabilities with a conversational AI agent using LangGraph framework. We'll focus on **long-term memory** retention across multiple conversation sessions - allowing an agent to extract and recall user preferences, dietary restrictions, and contextual information from past interactions.
#
# ## Tutorial Details
#
# | Information         | Details                                                                          |
# |:--------------------|:---------------------------------------------------------------------------------|
# | Tutorial type       | Long-term Conversational                                                        |
# | Agent usecase       | Nutrition Assistant                                                              |
# | Agentic Framework   | LangGraph                                                                        |
# | LLM model           | Anthropic Claude Haiku 4.5                                                     |
# | Tutorial components | AgentCore Long-term Memory, Custom Memory Strategies, Pre/Post Model Hooks     |
# | Example complexity  | Intermediate                                                                     |
#
# You'll learn to:
# - Create AgentCore Memory with UserPreference custom-override strategy
# - Implement pre/post model hooks for automatic memory storage and retrieval
# - Build a nutrition assistant that remembers user preferences across sessions
# - Use semantic search to retrieve relevant user context
# - Configure custom memory extraction and consolidation prompts
#
# ### Scenario Context
#
# In this example, we'll create a **Nutrition Assistant** that can remember user context across multiple conversations, including dietary restrictions, favorite foods, cooking preferences, and health goals. The agent will automatically extract and store user preferences from conversations, then retrieve relevant context for future interactions to provide personalized nutrition advice.
#
# ## Architecture
#
# <div style="text-align:left">
#     <img src="architecture.png" width="65%" />
# </div>
#
# ## Prerequisites
#
# - Python 3.10+
# - AWS account with appropriate permissions
# - AWS IAM role with appropriate permissions for AgentCore Memory
# - Access to Amazon Bedrock models
#
# Let's get started by setting up our environment!


# Install necessary libraries from https://github.com/langchain-ai/langchain-aws


import os
import logging
import json as json_module
import boto3
from botocore.exceptions import ClientError

# Import LangGraph and LangChain components
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore
import uuid


region = os.getenv("AWS_REGION", "us-east-1")
logging.getLogger("math-agent").setLevel(logging.DEBUG)


# Import the AgentCoreMemoryStore that we will use as a store
from langgraph_checkpoint_aws import AgentCoreMemoryStore  # noqa: E402

# For this example, we will just use an InMemorySaver to save context.
# In production, we highly recommend the AgentCoreMemorySaver as a checkpointer which works seamlessly alongside the memory store
# from langgraph_checkpoint_aws import AgentCoreMemorySaver
from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from bedrock_agentcore.memory import MemoryClient  # noqa: E402
from bedrock_agentcore.memory.constants import StrategyType  # noqa: E402

from custom_memory_prompts import consolidation_prompt, extraction_prompt  # noqa: E402


memory_name = "NutritionAssistant"
client = MemoryClient(region_name=region)
MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"


def create_memory_execution_role():
    """Create IAM role for AgentCore Memory custom strategies with required permissions."""
    iam_client = boto3.client("iam", region_name=region)
    sts_client = boto3.client("sts", region_name=region)
    account_id = sts_client.get_caller_identity()["Account"]
    role_name = "AgentCoreMemoryExecutionRole"
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "",
                "Effect": "Allow",
                "Principal": {"Service": ["bedrock-agentcore.amazonaws.com"]},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                    },
                },
            }
        ],
    }
    permissions_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/*",
                    "arn:aws:bedrock:*:*:inference-profile/*",
                ],
                "Condition": {"StringEquals": {"aws:ResourceAccount": account_id}},
            }
        ],
    }
    try:
        iam_client.get_role(RoleName=role_name)
        logging.info(f"IAM role already exists: {role_arn}")
        return role_arn
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise
    iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json_module.dumps(trust_policy),
        Description="Execution role for AgentCore Memory custom strategies",
    )
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName="AgentCoreMemoryBedrockAccess",
        PolicyDocument=json_module.dumps(permissions_policy),
    )
    logging.info(f"Created IAM role: {role_arn}")
    return role_arn


MEMORY_EXECUTION_ROLE_ARN = create_memory_execution_role()

memory = client.create_or_get_memory(
    name=memory_name,
    description="Nutrition assistant",
    memory_execution_role_arn=MEMORY_EXECUTION_ROLE_ARN,
    strategies=[
        {
            StrategyType.CUSTOM.value: {
                "name": "NutritionPreferences",
                "description": "Captures customer food preferences and behavior",
                "namespaces": ["/{actorId}/preferences/"],
                "configuration": {
                    "userPreferenceOverride": {
                        "extraction": {
                            "appendToPrompt": extraction_prompt,
                            "modelId": MODEL_ID,
                        },
                        "consolidation": {
                            "appendToPrompt": consolidation_prompt,
                            "modelId": MODEL_ID,
                        },
                    }
                },
            }
        },
    ],
)
memory_id = memory["id"]


# ### Memory Configuration Overview
#
# Our AgentCore Memory setup includes:
#
# - **Custom Strategy**: Extracts nutrition preferences from conversations
# - **Namespaces**: Organizes memories by user (`{actorId}/preferences/`)
# - **Custom Prompts**: Specialized extraction and consolidation logic for food preferences
# - **Model Integration**: Uses Claude 3.7 Sonnet for memory processing
#
# The memory system will automatically process conversations to extract lasting user preferences while filtering out temporary or irrelevant information.
#
# ## Step 3: Initialize Memory Store and LLM
#
# Now we'll initialize the AgentCore Memory Store and our language model.


# Initialize the store to enable long term memory saving and retrieval
store = AgentCoreMemoryStore(memory_id=memory_id, region_name=region)

# Initialize Bedrock LLM
llm = init_chat_model(MODEL_ID, model_provider="bedrock_converse", region_name=region)


# ## Step 4: Implement Memory Hooks
#
# We'll create pre and post model hooks to automatically handle memory storage and retrieval:
#
# - **Pre-model hook**: Retrieves relevant user preferences (based on semantic search) and adds context before LLM invocation
# - **Post-model hook**: Saves the conversation messages for long-term memory extraction
#
# ### How Memory Processing Works
#
# 1. Messages are saved to AgentCore Memory with actor_id and session_id
# 2. The custom strategy processes conversations to extract nutrition preferences
# 3. Extracted preferences are stored in the `{actorId}/preferences/` namespace
# 4. Future conversations can search and retrieve relevant preferences for context
#
# **Note**: LangChain message types are converted under the hood by the store to AgentCore Memory message types so that they can be properly extracted to long term memories.


def pre_model_hook(state, config: RunnableConfig, *, store: BaseStore):
    """Hook that runs pre-LLM invocation to save the latest human message"""
    actor_id = config["configurable"]["actor_id"]
    thread_id = config["configurable"]["thread_id"]
    # Saving the message to the actor and session combination that we get at runtime
    namespace = (actor_id, thread_id)

    messages = state.get("messages", [])
    # Save the last human message we see before LLM invocation
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            store.put(namespace, str(uuid.uuid4()), {"message": msg})
            break
    # Retrieve user preferences based on the last message and append to state
    user_preferences_namespace = (actor_id, "preferences/")
    preferences = store.search(user_preferences_namespace, query=msg.content, limit=5)

    # Construct another AI message to add context before the current message
    if preferences:
        context_items = [pref.value for pref in preferences]
        context_message = AIMessage(
            content=f"[User Context: {', '.join(str(item) for item in context_items)}]"
        )
        # Insert the context message before the last human message
        return {"messages": messages[:-1] + [context_message, messages[-1]]}

    return {"llm_input_messages": messages}


def post_model_hook(state, config: RunnableConfig, *, store: BaseStore):
    """Hook that runs post-LLM invocation to save the latest human message"""
    actor_id = config["configurable"]["actor_id"]
    thread_id = config["configurable"]["thread_id"]

    # Saving the message to the actor and session combination that we get at runtime
    namespace = (actor_id, thread_id)

    messages = state.get("messages", [])
    # Save the LLMs response to AgentCore Memory
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            store.put(namespace, str(uuid.uuid4()), {"message": msg})
            break

    return {"messages": messages}


# ## Step 5: Create the LangGraph Agent
#
# Now we'll create our nutrition assistant agent using LangGraph's `create_react_agent` with our memory hooks integrated. The tool node will contain just our long term memory retrieval tool and the pre and post model hooks are specified as arguments.
#
# **Note**: for custom agent implementations the Store and tools can be configured to run as needed for any workflow following this pattern. Pre/post model hooks can be used, the whole conversation could be saved at the end, etc.


graph = create_react_agent(
    llm,
    store=store,
    tools=[],  # No additional tools needed for this example
    checkpointer=InMemorySaver(),  # For conversation state management
    pre_model_hook=pre_model_hook,  # Retrieves user preferences before LLM call
    post_model_hook=post_model_hook,  # Saves conversation after LLM response
)


# ## Step 6: Configure Agent Runtime
#
# We need to configure the agent with unique identifiers for the user and session. These IDs are crucial for memory organization and retrieval.
#
# ### Graph Invoke Input
# We only need to pass the newest user message in as an argument `inputs`. This could include other state variables as well but for the simple `create_react_agent`, we only need messages.
#
# ### LangGraph RuntimeConfig
# In LangGraph, config is a `RuntimeConfig` that contains attributes that are necessary at invocation time, for example user IDs or session IDs. For the `AgentCoreMemorySaver`, `thread_id` and `actor_id` must be set in the config. For instance, your AgentCore invocation endpoint could assign this based on the identity or user ID of the caller. You can read additional [documentation here](https://langchain-ai.github.io/langgraphjs/how-tos/configuration/)
#
#


actor_id = "user-1"
config = {
    "configurable": {
        "thread_id": "session-1",  # REQUIRED: This maps to Bedrock AgentCore session_id under the hood
        "actor_id": actor_id,  # REQUIRED: This maps to Bedrock AgentCore actor_id under the hood
    }
}


# ## Step 7: Test the Agent
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
# For this implementation with pre/post model hooks, two messages were stored here. The first message from the user and the response from the AI model were both stored as conversational events in AgentCore Memory. It may take a few moments for the long term memories to be extracted, so retry after a few seconds if nothing is found the first try.
#
# These messages were then extracted to AgentCore long term memory in our fact and user preferences namespaces. In fact, we can check the store ourselves to verify what has been stored there so far:


# Search our user preferences namespace
search_namespace = (actor_id, "preferences/")
result = store.search(search_namespace, query="food", limit=3)
print(f"Preferences namespace result: {result}")


# ### Agent access to the store
#
# **Note** - since AgentCore memory processes these events in the background, it may take a few seconds for the memory to be extracted and embedded to long term memory retrieval.
#
# Great! Now we have seen that long term memories were extracted to our namespaces based on the earlier messages in the conversation.
#
# Now, let's start a new session and ask about recommendations for what to cook for dinner. The agent can use the store to access the long term memories that were extracted to make a recommendation that the user will be sure to like.


config = {
    "configurable": {
        "thread_id": "session-2",  # New session ID
        "actor_id": actor_id,  # Same actor ID
    }
}

run_agent("Today's a new day, what should I make for dinner tonight?", config)


# ### Wrapping up
#
# As you can see, the agent received both pre-model hook context from the user preferences namespace search and was able to search on its own for long term memories in the fact namespace to create a comprehensive answer for the user.
#
# The AgentCoreMemoryStore is very flexible and can be implemented in a variety of ways, including pre/post model hooks or just tools themselves with store operations. Used alongside the AgentCoreMemorySaver for checkpointing, both full conversational state and long term insights can be combined to form a complex and intelligent agent system.
