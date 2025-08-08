#!/usr/bin/env python3
"""
Auto Insurance Agent using Strands and MCP

This agent connects to the local insurance MCP server to provide
auto insurance quotes, customer information, and vehicle details.

It can be used in two ways:
1. With a direct command-line input: python interactive_insurance_agent.py --user_input "your question"
2. As an AWS Bedrock Agent (when deployed to AgentCore)
"""

# Standard library imports
import logging
from typing import Dict, List, Optional
import time
import json
import os
from datetime import datetime

# Import dotenv for loading environment variables
from dotenv import load_dotenv

from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# ADDED: BEDROCK_AGENTCORE IMPORT
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Load environment variables from .env file
load_dotenv()

# ADDED: BEDROCK_AGENTCORE APP CREATION
app = BedrockAgentCoreApp()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # logging.StreamHandler()
    ]
)
logger = logging.getLogger("InsuranceAgent")

# MCP server URL and access token from environment variables
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")
access_token = os.getenv("MCP_ACCESS_TOKEN")

# Check if environment variables are set
if not MCP_SERVER_URL:
    logger.error("MCP_SERVER_URL not found in environment variables.")
    raise ValueError("MCP_SERVER_URL environment variable is required")

if not access_token:
    logger.warning("MCP_ACCESS_TOKEN not found in environment variables. Authentication might fail.")
    # Don't set a default access token as it's sensitive and should be provided via environment

# Create an MCP Client pointing to our MCP server
insurance_client = MCPClient(lambda: streamablehttp_client(MCP_SERVER_URL, headers={"Authorization": f"Bearer {access_token}"})) 


# System prompt for the insurance agent
INSURANCE_SYSTEM_PROMPT = """
You are an auto insurance assistant that helps customers understand their insurance options.

Your goal is to provide helpful, accurate information about auto insurance products, 
customer details, vehicle information, and insurance quotes.

Use the available tools to retrieve information from the insurance database.
When providing quotes or information, be professional but conversational.
Explain insurance terms in simple language and highlight key benefits of different options.

Available tools:
x_amz_bedrock_agentcore_search - A special tool that returns a trimmed down list of tools given a context. 
Use this tool only when there are many tools available and you want to get a subset that matches the provided context.

Always verify the information with the customer and ask for clarification when needed.
Keep your responses concise and focused on answering the user's questions.

Remember previous context from the conversation when responding.
"""

def log_conversation(role: str, content: str, tool_calls: Optional[List] = None) -> None:
    """Log each conversation turn with timestamp and optional tool calls"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[{timestamp}] {role}: {content[:100]}..." if len(content) > 100 else f"[{timestamp}] {role}: {content}")
    
    if tool_calls:
        for call in tool_calls:
            logger.info(f"  Tool used: {call['name']} with args: {json.dumps(call['args'])}")

def insurance_quote_agent(question: str):
    """
    Creates a Strands agent that answers questions about auto insurance
    using the MCP tools from our local MCP server.
    
    Args:
        question: The customer's question or request
        history: Chat history for context
        
    Returns:
        The agent's response
    """
    log_conversation("User", question)
    
    with insurance_client:
        try:
            # Get the list of available tools from the MCP server
            tools = insurance_client.list_tools_sync()
            logger.info(f"Connected to MCP server, found {len(tools)} tools")
            
            # Get model name from environment or use default
            model_name = os.getenv("MODEL_NAME", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
            
            # Create an agent with our tools
            agent = Agent(
                model=model_name,
                tools=tools,
                system_prompt=INSURANCE_SYSTEM_PROMPT,
                callback_handler=None
            )
            
            # Add context using previous conversation
            prompt = question
            
            start_time = time.time()
            # Process the question and return the response
            response = agent(prompt)
            end_time = time.time()
            
            logger.info(f"Request processed in {end_time - start_time:.2f} seconds")
            
            return response
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            # Return a graceful error response
            return {"message": {"content": f"I'm sorry, I encountered an error: {str(e)}. Please try again later."}}

def process_single_input(user_input: str, history: List[Dict[str, str]] = None):
    """
    Process a single user input and return the response
    
    Args:
        user_input: The user's question or request
        history: Optional chat history for context
        
    Returns:
        The agent's response as a string
    """
    if history is None:
        history = []
        
    logger.info(f"Processing single input: {user_input}")
    
    # Get response from agent
    response = insurance_quote_agent(user_input)
    
    # Format the response for display
    if isinstance(response, dict):
        if "content" in response:
            return response["content"]
        elif "message" in response and "content" in response["message"]:
            return response["message"]["content"]
    
    # Default return the full response
    return str(response)

# ADDED: BEDROCK_AGENTCORE - APP ENTRYPOINT DECLARATION
@app.entrypoint
def main(payload):
    """
    Main function to run the insurance agent
    
    Args:
        payload: Input payload from AgentCore, which may contain the user's message
    """
    logger.info("Starting Insurance Agent")
    logger.info(f"Received payload: {payload}")
    logger.info(f"Is payload string? {isinstance(payload, str)}")
    
    try:
        # Extract the user input from the payload
        logger.info(f"Input Payload: {payload}")
        user_input = payload.get("user_input")
        
        # Add explicit check
        if "user_input" not in payload:
            logger.error("No 'user_input' key found in payload, using default")
        
        logger.info(f"Extracted user_input: {user_input}")
        logger.info("\n🚀 Processing request...")
        
        # Process the request
        response = process_single_input(user_input)
        logger.info(f"\n🤖 Assistant: {response}")
        
        return response
    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        logger.error(error_msg)
        logger.info(f"\n❌ {error_msg}")
        
        # Format error response for AgentCore
        return f"I'm sorry, I encountered an error: {str(e)}. Please try again later."
        
    finally:
        logger.info("Insurance Agent request processed")

if __name__ == "__main__":
    # REMOVED: PREVIOUS CODE FOR LOCAL PROCESSING
    # ADDED: BEDROCK_AGENTCORE - RUN APP
    app.run()

