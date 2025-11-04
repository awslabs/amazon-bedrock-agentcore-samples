import os
import boto3
# session expired, working example retrieve-from-kb-with-refresh.py

# MUST set AWS profile and region BEFORE importing any AWS/strands libraries
os.environ["AWS_PROFILE"] = "975050157807_AdministratorAccess"
os.environ["AWS_DEFAULT_REGION"] = "ap-southeast-2"
os.environ["KNOWLEDGE_BASE_ID"] = "YPMPOPGJ6H"

# Create boto3 session explicitly with the profile to force SSO credential refresh
boto3.setup_default_session(profile_name='975050157807_AdministratorAccess', region_name='ap-southeast-2')

from strands import Agent
from strands_tools import retrieve

# Before running this script, login first:
# aws sso login --profile 975050157807_AdministratorAccess
# Verify: aws sts get-caller-identity --profile 975050157807_AdministratorAccess #your-kb-id-goes-here" https://ap-southeast-2.console.aws.amazon.com/bedrock/home?region=ap-southeast-2#/knowledge-bases/knowledge-base-quick-start-mjihn/YPMPOPGJ6H/0

SYSTEM_PROMPT = """
You are DocumentHelper, an intelligent virtual assistant. 
Use the knowledge base of company documents to answer user questions. 
If you cannot find a clear answer, say you are unsure and suggest human support.
"""

agent = Agent(
    tools=[ retrieve ],
    system_prompt=SYSTEM_PROMPT
)

def chat_loop():
    while True:
        user_query = input("You: ") # e.g : which documents are in knowledge base?
        user_query = " which documents are in knowledge base?"
        if user_query.lower() in ("exit","quit"):
            break
        response = agent(user_query)
        print("DocumentHelper:", response)
        # break #if hardcoded query, exit after first response
if __name__ == "__main__":
    chat_loop()
