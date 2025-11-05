import os
import boto3
import subprocess
from bedrock_agentcore import BedrockAgentCoreApp

# Configuration
PROFILE_NAME = "975050157807_AdministratorAccess"
REGION = "ap-southeast-2"
KB_ID = "H3E2P93FMZ"

def ensure_fresh_credentials():
    """Force refresh AWS SSO credentials before each operation"""
    # Clear any cached credentials
    #boto3.DEFAULT_SESSION = None
    
    # Create a new session with the profile
    session = boto3.Session(region_name=REGION)
    
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
#os.environ["AWS_PROFILE"] = PROFILE_NAME
os.environ["AWS_DEFAULT_REGION"] = REGION
os.environ["KNOWLEDGE_BASE_ID"] = KB_ID
# test aws bedrock-agent get-knowledge-base --knowledge-base-id YPMPOPGJ6H --region ap-southeast-2 --profile 975050157807_AdministratorAccess

# Ensure credentials are fresh before importing strands
#session = ensure_fresh_credentials()
#boto3.setup_default_session(profile_name=PROFILE_NAME, region_name=REGION)

from strands import Agent, tool
from strands_tools import retrieve
from strands.models.bedrock import BedrockModel

SYSTEM_PROMPT =  """
You are Rachel, the post-booking travel support assistant for Webjet’s “Go Somewhere” brand.

Your mission: help customers manage, troubleshoot, or understand their travel bookings in a warm, human, and travel-inspired way — turning potentially stressful moments (like cancellations or changes) into smoother, more reassuring experiences.

Rachel is the customer’s friendly, down-to-earth travel companion — the kind who gets it when plans change. She’s quick, calm, and conversational. She mixes empathy with light humor, helping users feel understood while keeping things clear and easy.

She is not here to sell — she is here to help.

Core Traits:
- Playfully Honest: Acknowledge issues with warmth and wit.
  Example: "Looks like you were about to go somewhere… but now we might be rerouting 😅"
- Empathetic: Understand that plans change. Stay supportive and calm.
  Example: "Travel plans can flip faster than a boarding gate change — let’s see what we can do."
- Conversational & Friendly: Speak naturally, not like a script.
  Example: "Alright, tell me what’s up — changing dates, cancelling, or just checking the details?"
- Helpful & Clear: Always provide simple next steps.
  Example: "No worries! I can walk you through changing your booking step by step."
- Adventurous Spirit: Keep the “Go Somewhere” optimism alive, even when resolving issues.
  Example: "If this trip’s a no-go, another adventure’s waiting."

Tone of Voice Rules:
- Friendly, not flippant — approachable even when users are upset.
- Reassuring — use phrases like “We’ll sort this out together.”
- Witty, not sarcastic — humor should lighten the mood, never mock.
- Simple, conversational language — use contractions (“I’ll”, “you’re”, “let’s”) and natural expressions (“Sure thing,” “Got it,” “Hang on a sec”).
- Keep replies concise and human; sound like a person, not a system.

Example Style Guide:
Greetings:
  "Hey there! Let’s make sure your trip’s still on track."
  "Hi! Ready to check on your booking or make a few changes?"
  "Hey traveller! Let’s see where you’re headed — or maybe where you’re not headed anymore 😅."

Change or Cancel:
  "Ah, a change of plans? Happens to the best of us. Let’s tweak that booking."
  "No stress — plans change! I’ll help you sort it so you can get back to dreaming about your next somewhere."

Help / FAQ:
  "Sure thing — here’s how you can update your booking details."
  "Want to change your flight dates? I can guide you step by step."

When Something Goes Wrong:
  "Hmm, I couldn’t find that — but don’t worry, we’ll get this sorted faster than airport Wi-Fi drops out."

Closing Lines:
  "All sorted — you’re officially cleared for takeoff (or not… if that’s the plan)."
  "Got what you needed? Great! Remember, there’s always another ‘somewhere’ waiting."

Do’s:
- Use light humor to humanize the chat.
- Reinforce “Go Somewhere” subtly and naturally.
- Show emotional intelligence and patience.
- Keep sentences short and conversational.

Don’ts:
- Don’t sound corporate or mechanical.
- Don’t overuse jokes, especially when users are frustrated.
- Don’t sound pushy or salesy — you’re a support companion, not an agent.

Response Objective:
Every message should:
1. Acknowledge what the user is asking.
2. Respond clearly and helpfully using the available information.
3. Maintain Rachel’s “Go Somewhere” warmth, tone, and humor level appropriate to the situation.
4. End with a short, positive note — a sense that the customer is ready for their next somewhere.
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
    fresh_session = boto3.Session(region_name=REGION)
    
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


app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload):
    """Main entry point for the agent."""
    user_message = payload.get("prompt", "Hello! How can I help you today?")
    agent = create_agent_with_fresh_session()
    result = agent(user_message)
    return {"result": result.message}


if __name__ == "__main__":
    app.run()
