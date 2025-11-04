import os
import boto3
import subprocess

# Configuration
PROFILE_NAME = "975050157807_AdministratorAccess"
REGION = "ap-southeast-2"
KB_ID = "YPMPOPGJ6H"

def ensure_fresh_credentials():
    """Force refresh AWS SSO credentials before each operation"""
    # Clear any cached credentials
    boto3.DEFAULT_SESSION = None
    
    # Create a new session with the profile
    session = boto3.Session(profile_name=PROFILE_NAME, region_name=REGION)
    
    # Test the credentials
    try:
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        print(f"✓ Authenticated as: {identity['Arn']}")
        return session
    except Exception as e:
        print(f"✗ Credentials expired or invalid: {e}")
        print(f"Running: aws sso login --profile {PROFILE_NAME}")
        subprocess.run(["aws", "sso", "login", "--profile", PROFILE_NAME], check=True)
        # Retry after login
        session = boto3.Session(profile_name=PROFILE_NAME, region_name=REGION)
        return session

# Set environment variables
os.environ["AWS_PROFILE"] = PROFILE_NAME
os.environ["AWS_DEFAULT_REGION"] = REGION
os.environ["KNOWLEDGE_BASE_ID"] = KB_ID
# test aws bedrock-agent get-knowledge-base --knowledge-base-id YPMPOPGJ6H --region ap-southeast-2 --profile 975050157807_AdministratorAccess

# Ensure credentials are fresh before importing strands
session = ensure_fresh_credentials()
boto3.setup_default_session(profile_name=PROFILE_NAME, region_name=REGION)

from strands import Agent, tool
from strands_tools import retrieve
from strands.models.bedrock import BedrockModel

SYSTEM_PROMPT = """
You are DocumentHelper, an intelligent virtual assistant. 
Use the knowledge base of company documents to answer user questions. 
If you cannot find a clear answer, say you are unsure and suggest human support.
"""

# Option: Create a custom retrieve wrapper that ensures KB_ID is always set
@tool
def retrieve_from_kb(query: str, number_of_results: int = 10) -> str:
    """
    Retrieve information from the company knowledge base.
    
    Args:
        query: The search query to find relevant documents
        number_of_results: Maximum number of results to return (default: 10)
    
    Returns:
        Relevant information from the knowledge base
    """
    tool_use = {
        "toolUseId": "kb_retrieve",
        "input": {
            "text": query,
            "knowledgeBaseId": KB_ID,
            "region": REGION,
            "numberOfResults": number_of_results,
            "score": 0.4,
        },
    }
    
    result = retrieve.retrieve(tool_use)
    
    if result["status"] == "success":
        return result["content"][0]["text"]
    else:
        return f"Unable to retrieve from knowledge base. Error: {result['content'][0]['text']}"

def create_agent_with_fresh_session():
    """Create an agent with a fresh boto3 session to avoid credential caching"""
    fresh_session = boto3.Session(profile_name=PROFILE_NAME, region_name=REGION)
    
    # Create a BedrockModel with the fresh session
    model = BedrockModel(boto_session=fresh_session)
    
    # Create agent with the fresh model
    # Option 1: Use the default retrieve tool (relies on KNOWLEDGE_BASE_ID env var)
    # agent = Agent(
    #     model=model,
    #     tools=[retrieve],
    #     system_prompt=SYSTEM_PROMPT
    # )
    
    # Option 2: Use custom wrapper that hardcodes KB_ID
    agent = Agent(
        model=model,
        tools=[retrieve_from_kb],
        system_prompt=SYSTEM_PROMPT
    )
    return agent

def chat_loop():
    while True:
        #from  CAT GUIDE extracts KB "YPMPOPGJ6H"- 0 - B Airlines - 31 JUL 24.pdf  is actually 3C info. s3://bangyantest/3K.pdf' has 3U information
        user_query = input("You: ") # e.g :what are 3C change rules? # which documents are in knowledge base YPMPOPGJ6H?
        if user_query.lower() in ("exit","quit"):
            break
        
        try:
            # Create a NEW agent with fresh credentials for each query
            print("Creating agent with fresh credentials...")
            agent = create_agent_with_fresh_session()
            response = agent(user_query)
            print("DocumentHelper:", response)
        except Exception as e:
            print(f"Error: {e}")
            print("If credentials expired, run: aws sso login --profile " + PROFILE_NAME)

if __name__ == "__main__":
    chat_loop()
