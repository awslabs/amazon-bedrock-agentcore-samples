"""
Memory-Powered Customer Support Agent

A conversational support agent that uses AgentCore Memory for:
  - Short-term memory: Maintains context within a single session
  - Long-term memory: Remembers customer facts and issue history across sessions

Uses the Strands Agents SDK with AgentCore Memory integration.
"""

import json
import logging
import os
import sys
from datetime import datetime

import boto3
from bedrock_agentcore.memory import MemoryClient
from strands import Agent, tool

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REGION = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "anthropic.claude-haiku-4-5-20251001-v1:0"
)
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "memory_config.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("customer-support-agent")


def load_config():
    """Load memory configuration from the config file."""
    if not os.path.exists(CONFIG_FILE):
        print("Error: memory_config.json not found.")
        print("Run: python create_memory.py")
        sys.exit(1)

    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Memory-Backed Tools
# ---------------------------------------------------------------------------

# Initialize memory client globally so tools can access it
config = load_config()
memory_client = MemoryClient(region_name=REGION)
MEMORY_ID = config["memory_id"]


@tool
def recall_customer_history(customer_id: str, query: str) -> str:
    """
    Retrieve relevant facts and history about a customer from long-term memory.

    Use this tool when a returning customer contacts support, or when you need
    to look up past interactions, preferences, or issue history.

    Args:
        customer_id: The unique customer identifier (e.g., 'customer-sarah')
        query: What information to search for (e.g., 'past issues', 'preferences')

    Returns:
        A summary of relevant customer facts and history from memory.
    """
    results = []

    # Search customer facts
    try:
        facts_namespace = f"/customers/{customer_id}/facts"
        facts = memory_client.retrieve_memories(
            memory_id=MEMORY_ID,
            namespace=facts_namespace,
            query=query,
            top_k=5,
        )
        if facts:
            results.append("--- Customer Facts ---")
            for fact in facts:
                results.append(f"  - {fact['content']['text']}")
    except Exception as e:
        logger.warning(f"Could not retrieve customer facts: {e}")

    # Search issue history
    try:
        issues_namespace = f"/customers/{customer_id}/issues"
        issues = memory_client.retrieve_memories(
            memory_id=MEMORY_ID,
            namespace=issues_namespace,
            query=query,
            top_k=5,
        )
        if issues:
            results.append("--- Issue History ---")
            for issue in issues:
                results.append(f"  - {issue['content']['text']}")
    except Exception as e:
        logger.warning(f"Could not retrieve issue history: {e}")

    if not results:
        return "No previous history found for this customer."

    return "\n".join(results)


@tool
def get_recent_conversation(
    customer_id: str, session_id: str, num_turns: int = 5
) -> str:
    """
    Retrieve recent conversation turns from short-term memory.

    Use this tool when you need to recall what was discussed earlier in the
    current session.

    Args:
        customer_id: The unique customer identifier
        session_id: The current session identifier
        num_turns: Number of recent turns to retrieve (default: 5)

    Returns:
        Recent conversation history.
    """
    try:
        turns = memory_client.get_last_k_turns(
            memory_id=MEMORY_ID,
            actor_id=customer_id,
            session_id=session_id,
            k=num_turns,
        )

        if not turns:
            return "No previous conversation in this session."

        conversation = []
        for turn in turns:
            for msg in turn:
                role = msg.get("role", "UNKNOWN")
                text = msg.get("content", {}).get("text", "")
                conversation.append(f"  {role}: {text}")

        return "--- Recent Conversation ---\n" + "\n".join(conversation)

    except Exception as e:
        logger.warning(f"Could not retrieve conversation: {e}")
        return "Could not retrieve recent conversation."


@tool
def create_support_ticket(
    customer_id: str,
    subject: str,
    description: str,
    priority: str = "medium",
) -> str:
    """
    Create a new support ticket for a customer issue.

    Args:
        customer_id: The unique customer identifier
        subject: Brief summary of the issue
        description: Detailed description of the problem
        priority: Ticket priority - 'low', 'medium', 'high', or 'critical'

    Returns:
        Ticket confirmation with ticket ID.
    """
    ticket_id = f"TKT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # In production, this would integrate with a ticketing system.
    # For this demo, we log the ticket creation.
    ticket = {
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "subject": subject,
        "description": description,
        "priority": priority,
        "status": "open",
        "created_at": datetime.now().isoformat(),
    }

    logger.info(f"Ticket created: {json.dumps(ticket, indent=2)}")

    return (
        f"Support ticket created successfully.\n"
        f"  Ticket ID: {ticket_id}\n"
        f"  Subject: {subject}\n"
        f"  Priority: {priority}\n"
        f"  Status: Open\n"
        f"You will receive updates via your preferred communication channel."
    )


@tool
def lookup_order(order_id: str) -> str:
    """
    Look up order details by order ID.

    Args:
        order_id: The order number (e.g., '12345')

    Returns:
        Order details including status, items, and shipping info.
    """
    # Simulated order database for demonstration
    orders = {
        "12345": {
            "order_id": "12345",
            "items": ["Laptop - Model X Pro 16-inch"],
            "status": "Delivered",
            "delivery_date": "2026-06-15",
            "shipping_address": "123 Main St, Seattle, WA",
            "total": "$1,299.99",
        },
        "12346": {
            "order_id": "12346",
            "items": ["Wireless Mouse", "USB-C Hub"],
            "status": "In Transit",
            "estimated_delivery": "2026-06-23",
            "tracking_number": "1Z999AA10123456784",
            "total": "$89.98",
        },
        "12347": {
            "order_id": "12347",
            "items": ["Noise Cancelling Headphones"],
            "status": "Processing",
            "estimated_delivery": "2026-06-28",
            "total": "$349.99",
        },
    }

    order = orders.get(order_id)
    if not order:
        return f"Order #{order_id} not found. Please verify the order number."

    details = [f"--- Order #{order_id} ---"]
    for key, value in order.items():
        if key != "order_id":
            label = key.replace("_", " ").title()
            if isinstance(value, list):
                value = ", ".join(value)
            details.append(f"  {label}: {value}")

    return "\n".join(details)


# ---------------------------------------------------------------------------
# Agent Setup
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a friendly and professional Customer Support Agent.

CAPABILITIES:
- You can remember customers across sessions using long-term memory
- You can recall details from the current conversation using short-term memory
- You can create support tickets for customer issues
- You can look up order details

GUIDELINES:
1. Always start by checking if you have prior history with the customer using
   the recall_customer_history tool. Use their name or ID as the customer_id.
2. Be warm and personal. If you remember them, acknowledge it.
3. When a customer mentions an issue, gather details before creating a ticket.
4. Use the lookup_order tool when customers ask about order status.
5. Always confirm actions taken and next steps.
6. Be empathetic and solution-oriented.

MEMORY USAGE:
- For returning customers, ALWAYS use recall_customer_history first
- Use get_recent_conversation if you need to recall earlier parts of this chat
- The memory system automatically extracts and stores important facts
  (names, preferences, issue details) from the conversation

IMPORTANT: Never fabricate customer history. Only reference information
retrieved from memory tools."""


def save_conversation_to_memory(
    customer_id: str, session_id: str, user_message: str, agent_response: str
):
    """Save a conversation turn to AgentCore Memory."""
    try:
        memory_client.create_event(
            memory_id=MEMORY_ID,
            actor_id=customer_id,
            session_id=session_id,
            messages=[
                (user_message, "USER"),
                (agent_response, "ASSISTANT"),
            ],
        )
        logger.debug("Conversation saved to memory.")
    except Exception as e:
        logger.warning(f"Failed to save conversation to memory: {e}")


def run_agent():
    """Run the interactive customer support agent."""
    print("=" * 60)
    print("  Memory-Powered Customer Support Agent")
    print("  Powered by Amazon Bedrock AgentCore Memory")
    print("=" * 60)
    print()

    # Get customer identifier
    customer_name = input("Enter your name (or customer ID): ").strip()
    if not customer_name:
        customer_name = "anonymous"

    customer_id = f"customer-{customer_name.lower().replace(' ', '-')}"
    session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    print(f"\nSession ID: {session_id}")
    print(f"Customer ID: {customer_id}")
    print("Type 'quit' or 'exit' to end the conversation.\n")

    # Create the Strands agent with memory tools
    agent = Agent(
        model=MODEL_ID,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            recall_customer_history,
            get_recent_conversation,
            create_support_ticket,
            lookup_order,
        ],
    )

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "bye"):
            print("\nThank you for contacting support. Have a great day!")
            break

        # Inject context: pass customer_id and session_id in the prompt
        contextual_prompt = (
            f"[Customer ID: {customer_id}, Session: {session_id}]\n"
            f"Customer says: {user_input}"
        )

        try:
            response = agent(contextual_prompt)
            agent_response = str(response)

            print(f"\nAgent: {agent_response}")

            # Save the conversation turn to memory
            save_conversation_to_memory(
                customer_id=customer_id,
                session_id=session_id,
                user_message=user_input,
                agent_response=agent_response,
            )

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            print("\nAgent: I apologize, but I encountered an error. "
                  "Let me try again. Could you please repeat your request?")


if __name__ == "__main__":
    run_agent()
