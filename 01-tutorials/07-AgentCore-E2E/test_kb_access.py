import os
import boto3
from botocore.exceptions import ClientError

# Configuration
PROFILE_NAME = "975050157807_AdministratorAccess"
REGION = "ap-southeast-2"
KB_ID = "YPMPOPGJ6H"

# Set up boto3 session
session = boto3.Session(profile_name=PROFILE_NAME, region_name=REGION)

# Test 1: Check identity
print("=" * 60)
print("TEST 1: Verify AWS Identity")
print("=" * 60)
try:
    sts = session.client('sts')
    identity = sts.get_caller_identity()
    print(f"✓ Authenticated as: {identity['Arn']}")
    print(f"  Account: {identity['Account']}")
except Exception as e:
    print(f"✗ Failed: {e}")

# Test 2: Check knowledge base exists
print("\n" + "=" * 60)
print("TEST 2: Get Knowledge Base Details")
print("=" * 60)
try:
    bedrock_agent = session.client('bedrock-agent')
    kb_response = bedrock_agent.get_knowledge_base(knowledgeBaseId=KB_ID)
    print(f"✓ Knowledge Base Found: {kb_response['knowledgeBase']['name']}")
    print(f"  ID: {kb_response['knowledgeBase']['knowledgeBaseId']}")
    print(f"  Status: {kb_response['knowledgeBase']['status']}")
    print(f"  ARN: {kb_response['knowledgeBase']['knowledgeBaseArn']}")
except Exception as e:
    print(f"✗ Failed: {e}")

# Test 3: Try to retrieve from knowledge base
print("\n" + "=" * 60)
print("TEST 3: Test Retrieve API")
print("=" * 60)
try:
    bedrock_agent_runtime = session.client('bedrock-agent-runtime')
    retrieve_response = bedrock_agent_runtime.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={'text': 'test query'}
    )
    print(f"✓ Retrieve API works!")
    print(f"  Retrieved {len(retrieve_response.get('retrievalResults', []))} results")
except ClientError as e:
    error_code = e.response['Error']['Code']
    error_msg = e.response['Error']['Message']
    print(f"✗ ClientError: {error_code}")
    print(f"  Message: {error_msg}")
    if error_code == 'ResourceNotFoundException':
        print("\n⚠️  The knowledge base ID is not accessible via bedrock-agent-runtime API")
        print("   This might be a regional issue or permissions problem")
except Exception as e:
    print(f"✗ Failed: {type(e).__name__}: {e}")

# Test 4: Check environment variables
print("\n" + "=" * 60)
print("TEST 4: Environment Variables")
print("=" * 60)
os.environ["AWS_PROFILE"] = PROFILE_NAME
os.environ["AWS_DEFAULT_REGION"] = REGION
os.environ["STRANDS_KNOWLEDGE_BASE_ID"] = KB_ID

print(f"AWS_PROFILE: {os.environ.get('AWS_PROFILE')}")
print(f"AWS_DEFAULT_REGION: {os.environ.get('AWS_DEFAULT_REGION')}")
print(f"STRANDS_KNOWLEDGE_BASE_ID: {os.environ.get('STRANDS_KNOWLEDGE_BASE_ID')}")

# Test 5: Try strands retrieve tool
print("\n" + "=" * 60)
print("TEST 5: Test strands_tools.retrieve")
print("=" * 60)
try:
    # Set up session before importing strands
    boto3.setup_default_session(profile_name=PROFILE_NAME, region_name=REGION)
    
    from strands_tools import retrieve
    
    print(f"✓ strands_tools imported successfully")
    print(f"  retrieve tool: {retrieve}")
    
    # Check if retrieve has any configuration methods
    if hasattr(retrieve, '__dict__'):
        print(f"  retrieve attributes: {dir(retrieve)}")
    
except Exception as e:
    print(f"✗ Failed to import strands_tools: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
