#!/usr/bin/env python
"""
Test Deployed Coordinator Agent with OAuth A2A

Tests the deployed coordinator agent by making HTTP requests to it,
simulating how the UI would interact with it.
"""

import os
import sys
import json
import asyncio
from uuid import uuid4
from urllib.parse import quote

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart

DEFAULT_TIMEOUT = 300

async def test_deployed_coordinator():
    """Test the deployed coordinator agent"""
    
    print("\n" + "="*70)
    print("TESTING DEPLOYED COORDINATOR AGENT")
    print("="*70)
    
    # Load deployment info
    script_dir = os.path.dirname(os.path.abspath(__file__))
    deployment_file = os.path.join(script_dir, 'deployment_info.json')
    
    with open(deployment_file, 'r', encoding='utf-8') as f:
        deployment_info = json.load(f)
    
    # Find coordinator agent
    coordinator_agent = None
    for agent in deployment_info['agents']:
        if agent['name'] == 'realestate_coordinator':
            coordinator_agent = agent
            break
    
    if not coordinator_agent or 'arn' not in coordinator_agent:
        print("✗ Coordinator agent not found in deployment_info.json")
        return False
    
    # Get coordinator URL
    arn = coordinator_agent['arn']
    region = arn.split(':')[3]
    escaped_arn = quote(arn, safe='')
    coordinator_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations/"
    
    print(f"\nCoordinator ARN: {arn}")
    print(f"Coordinator URL: {coordinator_url}")
    
    # Load bearer token
    token_file = os.path.join(script_dir, '.bearer_token')
    with open(token_file, 'r', encoding='utf-8') as f:
        bearer_token = f.read().strip()
    
    print(f"Bearer token loaded: {bearer_token[:20]}...")
    
    # Create HTTP client with bearer token
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    
    session_id = str(uuid4())
    print(f"Session ID: {session_id}")
    
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, headers=headers) as httpx_client:
            # Get agent card
            print("\n1. Fetching coordinator agent card...")
            resolver = A2ACardResolver(httpx_client=httpx_client, base_url=coordinator_url)
            agent_card = await resolver.get_agent_card()
            
            print(f"✓ Agent card retrieved")
            print(f"  Name: {agent_card.name}")
            print(f"  Description: {agent_card.description}")
            
            # Create A2A client
            config = ClientConfig(
                httpx_client=httpx_client,
                streaming=False
            )
            factory = ClientFactory(config)
            client = factory.create(agent_card)
            
            # Test 1: Search for apartments
            print("\n2. Testing property search via deployed coordinator...")
            test_message = "Find apartments in New York under $4000"
            print(f"   Message: {test_message}")
            
            msg = Message(
                kind="message",
                role=Role.user,
                parts=[Part(TextPart(kind="text", text=test_message))],
                message_id=uuid4().hex,
            )
            
            # Add session ID header
            httpx_client.headers['X-Amzn-Bedrock-AgentCore-Runtime-Session-Id'] = session_id
            
            response_received = False
            response_text = None
            
            async for event in client.send_message(msg):
                response_received = True
                
                if isinstance(event, Message):
                    print(f"\n✓ Message response received from coordinator")
                    for part in event.parts:
                        if hasattr(part, 'text'):
                            response_text = part.text
                            break
                    if response_text:
                        break
                
                elif isinstance(event, tuple) and len(event) == 2:
                    task, update_event = event
                    print(f"\n✓ Task response received from coordinator")
                    
                    # Extract text from task artifacts (this is where A2A responses are)
                    if hasattr(task, 'artifacts') and task.artifacts:
                        for artifact in task.artifacts:
                            if hasattr(artifact, 'parts') and artifact.parts:
                                for part in artifact.parts:
                                    if hasattr(part, 'root') and hasattr(part.root, 'text'):
                                        response_text = part.root.text
                                        break
                                    elif hasattr(part, 'text'):
                                        response_text = part.text
                                        break
                            if response_text:
                                break
                    
                    if response_text:
                        break
            
            if response_text:
                print(f"\n{'='*70}")
                print("COORDINATOR RESPONSE:")
                print(f"{'='*70}")
                print(response_text)
                print(f"{'='*70}")
                
                # Verify it contains property search results
                if any(keyword in response_text.lower() for keyword in ['apartment', 'property', 'new york', 'rent', '$']):
                    print("\n✅ Response contains property search results!")
                    print("✅ Coordinator successfully called search agent and returned results")
                else:
                    print("\n⚠️  Response received but doesn't contain expected property data")
            else:
                print(f"\n⚠️  Response received but couldn't extract text")
            
            if not response_received:
                print(f"\n✗ No response received from coordinator")
                return False
            
            print("\n" + "="*70)
            print("✅ DEPLOYED COORDINATOR TEST PASSED")
            print("="*70)
            return True
            
    except Exception as e:
        print(f"\n✗ Error testing deployed coordinator: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_deployed_coordinator())
    sys.exit(0 if result else 1)
