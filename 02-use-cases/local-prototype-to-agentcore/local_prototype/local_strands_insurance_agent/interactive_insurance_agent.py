#!/usr/bin/env python3
"""
Interactive Auto Insurance Agent using Strands and MCP

This agent connects to the local insurance MCP server to provide
auto insurance quotes, customer information, and vehicle details
in an interactive chat format with logging.
"""

# Standard library imports
import logging
from typing import Dict, Any, List, Optional
import time
import json
from datetime import datetime

from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.StreamHandler()
    ]
)
logger = logging.getLogger("InsuranceAgent")

# MCP server URL - points to our local MCP server
MCP_SERVER_URL = "http://localhost:8000/mcp"

# Create an MCP Client pointing to our local MCP server
insurance_client = MCPClient(lambda: streamablehttp_client(MCP_SERVER_URL))

# Chat history to maintain context
chat_history: List[Dict[str, str]] = []

# System prompt for the insurance agent
INSURANCE_SYSTEM_PROMPT = """
You are an auto insurance assistant that helps customers understand their insurance options.

Your goal is to provide helpful, accurate information about auto insurance products, 
customer details, vehicle information, and insurance quotes.

Use the available tools to retrieve information from the insurance database.
When providing quotes or information, be professional but conversational.
Explain insurance terms in simple language and highlight key benefits of different options.

Available tools:
- get_customer_info: Look up customer details by ID
- get_vehicle_info: Retrieve vehicle specifications by make, model, and year
- get_insurance_quote: Generate an insurance quote for a customer and vehicle
- get_vehicle_safety: Get safety ratings for a specific vehicle make and model

Always verify the information with the customer and ask for clarification when needed.
Keep your responses concise and focused on answering the user's questions.

When a customer asks for a quote, make sure to collect:
1. Customer ID (if available)
2. Vehicle make, model, and year

Remember previous context from the conversation when responding.
"""

def log_conversation(role: str, content: str, tool_calls: Optional[List] = None) -> None:
    """Log each conversation turn with timestamp and optional tool calls"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{timestamp}] {role}: {content[:100]}..." if len(content) > 100 else f"[{timestamp}] {role}: {content}")
    
    if tool_calls:
        for call in tool_calls:
            logger.info(f"  Tool used: {call['name']} with args: {json.dumps(call['args'])}")

def insurance_quote_agent(question: str, history: List[Dict[str, str]]) -> Dict[Any, Any]:
    """
    Creates a Strands agent that answers questions about auto insurance
    using the MCP tools from our local MCP server.
    
    Args:
        question: The customer's question or request
        history: Chat history for context
        
    Returns:
        The agent's response as a dictionary
    """
    log_conversation("User", question)
    
    with insurance_client:
        try:
            # Get the list of available tools from the MCP server
            tools = insurance_client.list_tools_sync()
            logger.info(f"Connected to MCP server, found {len(tools)} tools")
            
            # Create an agent with Claude 3.7 Sonnet and our tools
            # Create agent without chat_history parameter
            agent = Agent(
                model="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                tools=tools,
                system_prompt=INSURANCE_SYSTEM_PROMPT,
                callback_handler=None
            )
            
            # Add context using previous conversation
            prompt = question
            if history and len(history) > 1:
                context = "\n\nPrevious conversation:\n"
                # Add previous exchanges (up to 5) for context
                for i in range(max(0, len(history)-10), len(history), 2):
                    if i+1 < len(history):  # Make sure we have both user and assistant messages
                        context += f"User: {history[i]['content']}\nAssistant: {history[i+1]['content']}\n\n"
                prompt = context + "\nCurrent question: " + question
            
            start_time = time.time()
            # Process the question and return the response
            response = agent(prompt)
            end_time = time.time()
            
            logger.info(f"Request processed in {end_time - start_time:.2f} seconds")
            
            # Log the assistant's response
            try:
                log_conversation("Assistant", response, 
                              response.tool_calls if hasattr(response, "tool_calls") else None)
            except Exception as e:
                logger.error(f"Error logging response: {str(e)}")
                log_conversation("Assistant", str(response))
            
            return response
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            # Return a graceful error response
            return {"message": {"content": f"I'm sorry, I encountered an error: {str(e)}. Please try again later."}}

def run_interactive_session():
    """Run an interactive session with the insurance agent"""
    print("\n🚗 Welcome to the Interactive Auto Insurance Assistant! 🚗")
    print("Ask questions about auto insurance, get quotes, or inquire about specific vehicles.")
    print("Type 'exit', 'quit', or 'bye' to end the session.\n")
    
    global chat_history
    
    while True:
        try:
            # Get user input
            user_input = input("\n💬 You: ")
            
            # Check for exit commands
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("\n👋 Thank you for using our Auto Insurance Assistant. Goodbye!")
                break
            
            # Add user message to history
            chat_history.append({"role": "user", "content": user_input})
            
            print("\n⏳ Processing your request...")
            
            # Get response from agent
            response = insurance_quote_agent(user_input, chat_history)
                
            print(f"\n🤖 Assistant: {response}")
            
            # Add assistant response to history
            try:
                chat_history.append({"role": "assistant", "content": response})
            except Exception as e:
                logger.error(f"Error adding to chat history: {str(e)}")
            
            # Print which tools were used (for user information)
            if hasattr(response, "tool_calls") and response.tool_calls:
                print("\n🔧 Tools Used:")
                for call in response.tool_calls:
                    print(f"- {call['name']}")
            
        except KeyboardInterrupt:
            print("\n\n👋 Session interrupted. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error in interactive session: {str(e)}")
            print(f"\n❌ An error occurred: {str(e)}")
            print("Please try again or restart the application.")

def main():
    """Main function to run the interactive insurance agent"""
    logger.info("Starting Interactive Insurance Agent")
    print("\n🚀 Initializing Insurance Agent...")
    
    try:
        run_interactive_session()
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        print(f"\n❌ Fatal error: {str(e)}")
    
    logger.info("Insurance Agent session ended")

if __name__ == "__main__":
    main()