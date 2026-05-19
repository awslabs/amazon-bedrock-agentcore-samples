from langgraph.graph import StateGraph, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph_checkpoint_aws import AgentCoreMemorySaver, AgentCoreMemoryStore
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from tools import get_stock_data, search_news
import os
from tools import (
    parse_broker_profile_from_message,
    generate_market_summary_for_broker,
    get_broker_card_template,
    collect_broker_preferences_interactively,
)
from tools import get_memory_from_ssm, create_memory_tools
import logging

# Enable LangChain / LangGraph OpenTelemetry instrumentation so AgentCore
# Observability captures tool-call spans, gen_ai.prompt.*, gen_ai.completion.*,
# and trace structure. AgentCore Runtime boots agents under the ADOT
# auto-instrumentor, but framework-level instrumentors still need to be
# registered explicitly. See:
# https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html
try:
    from opentelemetry.instrumentation.langchain import LangchainInstrumentor

    LangchainInstrumentor().instrument()
except Exception:  # pragma: no cover — never block agent startup on instrumentation
    logging.getLogger(__name__).exception(
        "LangchainInstrumentor failed to load; continuing without framework-level tracing."
    )

app = BedrockAgentCoreApp()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Region for AgentCore services
REGION = os.getenv("AWS_REGION", "us-east-1")


def create_market_trends_agent():
    """Create LangGraph agent with AgentCore Memory checkpointer and store"""
    from langchain_aws import ChatBedrock

    # Get memory from SSM (created during deployment)
    memory_client, memory_id = get_memory_from_ssm()

    # AgentCoreMemorySaver: persists full conversation state across invocations
    checkpointer = AgentCoreMemorySaver(memory_id, region_name=REGION)

    # AgentCoreMemoryStore: long-term memory for preferences and semantic search
    store = AgentCoreMemoryStore(memory_id=memory_id, region_name=REGION)

    # LLM with Claude Haiku 4.5
    llm = ChatBedrock(
        model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0",
        model_kwargs={"temperature": 0.1},
    )

    # Create long-term memory tools (broker profiles, financial interests)
    default_actor_id = "unknown-user"
    session_id = "default"  # Will be overridden by checkpointer's thread_id
    memory_tools = create_memory_tools(memory_client, memory_id, session_id, default_actor_id)

    # All tools: market data + broker card + long-term memory
    tools = [
        get_stock_data,
        search_news,
        parse_broker_profile_from_message,
        generate_market_summary_for_broker,
        get_broker_card_template,
        collect_broker_preferences_interactively,
    ] + memory_tools
    llm_with_tools = llm.bind_tools(tools)

    # System prompt — merges original behavioral guidance with checkpointer-aware additions
    system_message = """You're an expert market intelligence analyst with deep expertise in financial markets, business strategy, and economic trends. You have advanced long-term memory capabilities to store and recall financial interests for each broker you work with.

    IMPORTANT: Your conversation history is automatically persisted across messages in the same session. You do NOT need to manually recall conversation history — previous messages are already in your context. If a broker identified themselves earlier in this session, you already have that context. Do NOT ask the user to identify themselves if they already did so in this conversation.

    PURPOSE:
    - Provide real-time market analysis and stock data
    - Maintain long-term financial profiles for each broker/client
    - Store and recall investment preferences, risk tolerance, and financial goals
    - Deliver personalized investment insights based on stored broker profiles
    - Build ongoing professional relationships through comprehensive memory

    AVAILABLE TOOLS:

    Real-Time Market Data:
    - get_stock_data(symbol): Retrieves current stock prices, changes, and market data
    - search_news(query, news_source): Searches multiple news sources (Bloomberg, Reuters, CNBC, WSJ, Financial Times, Dow Jones) for business news and market intelligence

    Broker Profile Collection (Conversational):
    - parse_broker_profile_from_message(user_message): Parse structured broker profile from user input
    - generate_market_summary_for_broker(broker_profile, market_data): Generate tailored market summary
    - get_broker_card_template(): Provide template for broker profile format
    - collect_broker_preferences_interactively(preference_type): Guide collection of specific preferences

    Long-Term Memory (persists across sessions):
    - get_broker_financial_profile(actor_id): Retrieve stored financial interests for a broker
    - update_broker_financial_interests(interests_update, actor_id): Store new financial interests
    - identify_broker(user_message): Extract broker identity and get their actor_id
    - list_conversation_history(): Retrieve conversation history from memory

    MULTI-STRATEGY LONG-TERM MEMORY CAPABILITIES:
    - You maintain persistent financial profiles for each broker using multiple memory strategies:
      * USER_PREFERENCE: Captures broker preferences, risk tolerance, and investment styles
      * SEMANTIC: Stores financial facts, market analysis, and investment insights
    - Use identify_broker() to intelligently extract broker identity using LLM analysis
    - Always check get_broker_financial_profile() for returning brokers to personalize service
    - Use update_broker_financial_interests() when brokers share new preferences or interests
    - Build comprehensive investment profiles over time across multiple memory dimensions
    - LLM-based identity extraction ensures consistent broker identification across varied introductions
    - Memory strategies work together to provide rich, contextual financial intelligence

    BROKER PROFILE MANAGEMENT WORKFLOW:

    **CRITICAL: MANDATORY BROKER IDENTIFICATION FIRST**

    1. **MANDATORY First Step - Identify Broker**:
       - IMMEDIATELY use identify_broker(user_message) when ANY user message contains:
         * Names, introductions, or "I'm [name]"
         * Broker cards or profile information
         * Company names or roles
         * ANY identity information whatsoever
       - This returns the correct actor_id and checks for existing profiles
       - Use the returned actor_id for ALL subsequent memory operations
       - DO NOT proceed with any other actions until broker identification is complete
       - If a broker was already identified earlier in this conversation (check your message history), use their actor_id directly — do not re-identify

    2. **Check Existing Profile**:
       - After identification, use get_broker_financial_profile(actor_id) with the identified actor_id
       - If profile exists, acknowledge their stored preferences and personalize responses
       - If no profile exists, proceed to collect new profile information

    3. **Profile Collection**:
       - **For broker cards (Name: X, Company: Y, etc.)**:
         * FIRST: identify_broker(user_message) to get actor_id
         * THEN: parse_broker_profile_from_message() to extract structured data
         * FINALLY: update_broker_financial_interests(parsed_profile, actor_id) to store
       - For missing info: use collect_broker_preferences_interactively()
       - For template: use get_broker_card_template()
       - ALWAYS store collected info with update_broker_financial_interests(info, actor_id)

    4. **Memory Operations**:
       - ALWAYS pass the identified actor_id to memory functions
       - get_broker_financial_profile(actor_id_from_identify_broker)
       - update_broker_financial_interests(info, actor_id_from_identify_broker)
       - This ensures consistent broker identity across all sessions

    5. **Market Analysis**:
       - Provide real-time stock data using get_stock_data()
       - Search for relevant market news using search_news() with appropriate news sources
       - Connect market events specifically to each broker's stored financial interests
       - Prioritize analysis of stocks/sectors in their profile

    6. **Professional Standards**:
       - Deliver institutional-quality analysis tailored to each broker's stored risk tolerance
       - Reference their specific investment goals and time horizons from their profile
       - Provide recommendations aligned with their stored investment style and preferences
       - Maintain professional relationships through consistent, personalized service

    **IMMEDIATE ACTION REQUIRED FOR EVERY MESSAGE:**
    Before doing ANYTHING else, check if the user message contains:
    - Names (Name: X, I'm X, My name is X)
    - Broker cards or profile information
    - Company/role information
    - Any identity markers

    If YES: IMMEDIATELY call identify_broker(user_message) as your FIRST action
    If NO: Proceed with normal market analysis

    CRITICAL: Always use the memory tools to maintain and reference broker financial profiles. This is essential for providing personalized, professional market intelligence services. Previous messages in this session are automatically available to you — if the user submitted a broker card earlier, you already have it in context."""

    # Chatbot node: invoke LLM with tools
    def chatbot(state: MessagesState, config: RunnableConfig):
        messages = state["messages"]
        # System message is prepended by pre_model_hook, but as fallback add it here
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=system_message)] + messages
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    # Build the graph
    graph_builder = StateGraph(MessagesState)
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("tools", ToolNode(tools))
    graph_builder.add_conditional_edges("chatbot", tools_condition)
    graph_builder.add_edge("tools", "chatbot")
    graph_builder.set_entry_point("chatbot")

    # Compile with AgentCore checkpointer and store for full memory integration
    graph = graph_builder.compile(
        checkpointer=checkpointer,  # Short-term: persists conversation state across invocations
        store=store,                # Long-term: extracts preferences and facts for cross-session search
    )

    return graph, memory_id


# Initialize the agent and memory_id at module load
agent, memory_id = create_market_trends_agent()


@app.entrypoint
def market_trends_agent_runtime(payload):
    """Invoke the market trends agent via AgentCore Runtime"""
    user_input = payload.get("prompt")
    # Use session_id from payload if provided, otherwise generate one
    session_id = payload.get("session_id", "default-session-00000000000000000")

    # Config with actor_id and thread_id for AgentCore Memory persistence
    config = {
        "configurable": {
            "thread_id": session_id,   # Maps to AgentCore session_id — persists conversation
            "actor_id": "market-agent", # Maps to AgentCore actor_id
        }
    }

    response = agent.invoke(
        {"messages": [HumanMessage(content=user_input)]},
        config=config,
    )
    return response["messages"][-1].content


def market_trends_agent_local(payload):
    """Invoke the market trends agent for local testing"""
    user_input = payload.get("prompt")
    session_id = payload.get("session_id", "local-test-session-00000000000000")

    config = {
        "configurable": {
            "thread_id": session_id,
            "actor_id": "market-agent",
        }
    }

    response = agent.invoke(
        {"messages": [HumanMessage(content=user_input)]},
        config=config,
    )
    return response["messages"][-1].content


if __name__ == "__main__":
    app.run()
