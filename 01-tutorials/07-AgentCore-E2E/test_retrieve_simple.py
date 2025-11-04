# passing seesion didn't work
# Workaround in retrieve-from-kb-with-refresh.py -use @tool def retrieve_from_kb, that is calling  retrieve.retrieve(tool_use)
import os
import boto3
from strands.models.bedrock import BedrockModel

# MUST set environment variables BEFORE importing strands
os.environ["AWS_PROFILE"] = "975050157807_AdministratorAccess"
os.environ["AWS_DEFAULT_REGION"] = "ap-southeast-2"
os.environ["KNOWLEDGE_BASE_ID"] = "YPMPOPGJ6H"

# Create a fresh boto3 session
session = boto3.Session(profile_name='975050157807_AdministratorAccess', region_name='ap-southeast-2')

# Test credentials
sts = session.client('sts')
identity = sts.get_caller_identity()
print(f"Authenticated as: {identity['Arn']}")

# Now import strands
from strands import Agent
from strands_tools import retrieve

print("=" * 60)
print("Testing retrieve tool with knowledge base")
print("=" * 60)

# Verify environment variables
print(f"KNOWLEDGE_BASE_ID: {os.environ.get('KNOWLEDGE_BASE_ID')}")
print(f"AWS_DEFAULT_REGION: {os.environ.get('AWS_DEFAULT_REGION')}")
print(f"AWS_PROFILE: {os.environ.get('AWS_PROFILE')}")

# Create agent with fresh session
model = BedrockModel(boto_session=session)
agent = Agent(
    model=model,
    tools=[retrieve],
    system_prompt="You are a helpful assistant. Use the knowledge base to answer questions."
)

print("\nSending query to agent...")
try:
    response = agent("What documents are in the knowledge base?")
    print(f"\nAgent Response:\n{response}")
except Exception as e:
    print(f"\nError: {type(e).__name__}: {e}")

# Agent Response:
# It appears there's an authentication issue with the AWS credentials. The security token has expired, which means I cannot currently access the knowledge base to retrieve information about what documents are available.

# To see what documents are in the knowledge base, you would need to:

# 1. **Refresh your AWS credentials** - Update your AWS access tokens or re-authenticate
# 2. **Check your AWS profile** - Ensure the correct profile is configured with valid credentials
# 3. **Verify permissions** - Make sure your credentials have access to the Amazon Bedrock Knowledge Base

# Workaround in retrieve-from-kb-with-refresh.py -use @tool def retrieve_from_kb, that is calling  retrieve.retrieve(tool_use)
