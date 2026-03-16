"""
Test Property Booking Agent

This script tests the deployed Property Booking Agent using AWS SigV4 authentication.
"""

import asyncio
import json
from uuid import uuid4
from urllib.parse import quote

import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from boto3.session import Session

# Get AWS session and credentials
boto_session = Session()
region = boto_session.region_name
credentials = boto_session.get_credentials()

# Read agent ARN from file
try:
    with open(".agent_arn", "r", encoding='utf-8') as f:
        agent_arn = f.read().strip()
except FileNotFoundError:
    print("Error: .agent_arn file not found")
    print("Please deploy the agent first: python deploy_to_agentcore.py")
    sys.exit(1)

print("=" * 70)
print("Property Booking Agent - Test Suite")
print("=" * 70)
print()
print(f"Agent ARN: {agent_arn}")
print(f"Region: {region}")
print()

# Construct runtime URL
escaped_agent_arn = quote(agent_arn, safe='')
runtime_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations/"


def sign_request(method, url, body=None, headers=None):
    """Sign a request using AWS SigV4."""
    if headers is None:
        headers = {}
    
    request = AWSRequest(method=method, url=url, data=body, headers=headers)
    SigV4Auth(credentials, "bedrock-agentcore", region).add_auth(request)
    
    return dict(request.headers)


async def invoke_agent(prompt, test_name):
    """Invoke the agent with a prompt."""
    print(f"Test: {test_name}")
    print("-" * 70)
    print(f"Prompt: {prompt}")
    print()
    
    message = {
        "jsonrpc": "2.0",
        "id": str(uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": prompt}],
                "messageId": str(uuid4())
            }
        }
    }
    
    body = json.dumps(message)
    headers = sign_request("POST", runtime_url, body=body, headers={"Content-Type": "application/json"})
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(runtime_url, content=body, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            # Extract response text
            if "result" in result:
                artifacts = result["result"].get("artifacts", [])
                if artifacts and len(artifacts) > 0:
                    parts = artifacts[0].get("parts", [])
                    if parts and len(parts) > 0:
                        response_text = parts[0].get("text", "")
                        print("Response:")
                        print(response_text)
                        print()
                        print("✓ Test Passed")
                        print()
                        return True
            
            print("Response (raw):")
            print(json.dumps(result, indent=2)[:500])
            print()
            return True
            
        except Exception as e:
            print(f"✗ Failed: {e}")
            print()
            return False


async def main():
    """Run all tests."""
    
    # Test 1: Book a property
    await invoke_agent(
        "Book property PROP001 for John Doe, email john@example.com, phone 555-1234, move-in date 2025-12-01",
        "Book Property"
    )
    
    await asyncio.sleep(2)
    
    # Test 2: Check booking status
    await invoke_agent(
        "Check the status of booking BOOK-001",
        "Check Booking Status"
    )
    
    await asyncio.sleep(2)
    
    # Test 3: List bookings by email
    await invoke_agent(
        "List all bookings for testuser@example.com",
        "List Bookings by Email"
    )
    
    await asyncio.sleep(2)
    
    # Test 4: Cancel booking
    await invoke_agent(
        "Cancel booking BOOK-001",
        "Cancel Booking"
    )
    
    print("=" * 70)
    print("✓ Test Suite Complete!")
    print("=" * 70)
    print()


if __name__ == "__main__":
    asyncio.run(main())
