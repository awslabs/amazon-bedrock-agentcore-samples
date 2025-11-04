import os
import boto3

# Set environment variables FIRST
os.environ["KNOWLEDGE_BASE_ID"] = "YPMPOPGJ6H"
os.environ["AWS_DEFAULT_REGION"] = "ap-southeast-2"

# Create a fresh session
session = boto3.Session(profile_name='975050157807_AdministratorAccess', region_name='ap-southeast-2')

# Test the bedrock-agent-runtime API directly with this session
print("Testing bedrock-agent-runtime API directly...")
bedrock_agent_runtime = session.client('bedrock-agent-runtime')

try:
    response = bedrock_agent_runtime.retrieve(
        knowledgeBaseId='YPMPOPGJ6H',
        retrievalQuery={'text': 'What documents are available?'}
    )
    results = response.get('retrievalResults', [])
    print(f"✓ Successfully retrieved {len(results)} results")
    if results:
        for i, result in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"  Score: {result.get('score')}")
            print(f"  Location: {result.get('location')}")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")
