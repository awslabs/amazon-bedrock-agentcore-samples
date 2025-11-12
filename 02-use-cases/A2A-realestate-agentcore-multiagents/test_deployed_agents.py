#!/usr/bin/env python
"""
Test Deployed A2A Agents with OAuth Authentication
Tests property search and booking agents deployed to AgentCore
"""

import os
import sys
import json
import asyncio
import logging
from uuid import uuid4
from urllib.parse import quote

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, TextPart

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300  # 5 minutes

class AgentTester:
    def __init__(self, config_file='cognito_config.json', deployment_file='deployment_info.json'):
        # Get script directory to find files relative to script location
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config = self.load_config(config_file)
        self.deployment = self.load_deployment(deployment_file)
        self.bearer_token = self.load_bearer_token()
    
    def get_file_path(self, filename):
        """Get full path to file, checking script directory first."""
        # Check in script directory
        script_path = os.path.join(self.script_dir, filename)
        if os.path.exists(script_path):
            return script_path
        
        # Check in current directory
        if os.path.exists(filename):
            return filename
        
        return None
    
    def load_config(self, config_file):
        """Load Cognito configuration."""
        file_path = self.get_file_path(config_file)
        
        if not file_path:
            print(f"✗ Error: {config_file} not found")
            sys.exit(1)
        
        with open(file_path, 'r') as f:
            return json.load(f)
    
    def load_deployment(self, deployment_file):
        """Load deployment information."""
        file_path = self.get_file_path(deployment_file)
        
        if not file_path:
            print(f"✗ Error: {deployment_file} not found")
            print("Please deploy agents first: python deploy_agents_with_oauth.py")
            sys.exit(1)
        
        with open(file_path, 'r') as f:
            return json.load(f)
    
    def load_bearer_token(self):
        """Load bearer token from file."""
        token_file = 'bearer_token.json'
        file_path = self.get_file_path(token_file)
        
        if not file_path:
            print(f"✗ Error: {token_file} not found")
            print("Please generate token first: python generate_bearer_token.py")
            sys.exit(1)
        
        with open(file_path, 'r') as f:
            token_data = json.load(f)
            return token_data['access_token']
    
    def get_agent_runtime_url(self, agent_arn):
        """Construct runtime URL from agent ARN."""
        # Extract region from ARN
        region = agent_arn.split(':')[3]
        
        # URL encode the ARN
        escaped_arn = quote(agent_arn, safe='')
        
        # Construct runtime URL
        runtime_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations/"
        
        return runtime_url
    
    def create_message(self, text: str, role: Role = Role.user) -> Message:
        """Create A2A message."""
        return Message(
            kind="message",
            role=role,
            parts=[Part(TextPart(kind="text", text=text))],
            message_id=uuid4().hex,
        )
    
    async def test_agent(self, agent_name: str, test_message: str):
        """Test a specific agent."""
        print(f"\n{'='*70}")
        print(f"Testing: {agent_name}")
        print(f"{'='*70}")
        
        # Find agent in deployment info
        agent_info = None
        for agent in self.deployment['agents']:
            if agent['name'] == agent_name:
                agent_info = agent
                break
        
        if not agent_info or 'arn' not in agent_info:
            print(f"✗ Agent ARN not found for {agent_name}")
            return False
        
        agent_arn = agent_info['arn']
        runtime_url = self.get_agent_runtime_url(agent_arn)
        
        print(f"Agent ARN: {agent_arn}")
        print(f"Runtime URL: {runtime_url}")
        print(f"Test Message: {test_message}")
        
        # Generate session ID
        session_id = str(uuid4())
        print(f"Session ID: {session_id}")
        
        # Prepare headers
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id
        }
        
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, headers=headers) as httpx_client:
                # Get agent card
                print("\nFetching agent card...")
                resolver = A2ACardResolver(httpx_client=httpx_client, base_url=runtime_url)
                agent_card = await resolver.get_agent_card()
                
                print(f"✓ Agent card retrieved")
                print(f"  Name: {agent_card.name}")
                print(f"  Description: {agent_card.description}")
                
                # Create client
                config = ClientConfig(
                    httpx_client=httpx_client,
                    streaming=False
                )
                factory = ClientFactory(config)
                client = factory.create(agent_card)
                
                # Send message
                print(f"\nSending message...")
                msg = self.create_message(test_message)
                
                response_received = False
                async for event in client.send_message(msg):
                    response_received = True
                    
                    if isinstance(event, Message):
                        print(f"\n✓ Response received:")
                        print(f"{'-'*70}")
                        
                        # Extract text from response
                        for part in event.parts:
                            if hasattr(part, 'text'):
                                print(part.text)
                        
                        print(f"{'-'*70}")
                        return True
                    
                    elif isinstance(event, tuple) and len(event) == 2:
                        task, update_event = event
                        print(f"\n✓ Task response received")
                        return True
                
                if not response_received:
                    print(f"\n✗ No response received")
                    return False
        
        except Exception as e:
            print(f"\n✗ Error testing agent: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def run_tests(self):
        """Run all agent tests."""
        print("\n" + "="*70)
        print("TESTING DEPLOYED A2A AGENTS")
        print("="*70)
        print(f"Cognito User Pool: {self.config['user_pool_id']}")
        print(f"Region: {self.config['region']}")
        
        test_cases = [
            {
                'agent': 'property_search_agent',
                'message': 'Find me apartments in New York under $4000 per month with at least 2 bedrooms'
            },
            {
                'agent': 'property_booking_agent',
                'message': 'Create a booking for property PROP001 for John Doe, email john@example.com, phone 555-1234, move-in date 2024-06-01'
            }
        ]
        
        results = []
        
        for test_case in test_cases:
            success = await self.test_agent(
                test_case['agent'],
                test_case['message']
            )
            results.append({
                'agent': test_case['agent'],
                'success': success
            })
        
        # Print summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        
        passed = sum(1 for r in results if r['success'])
        total = len(results)
        
        print(f"\nPassed: {passed}/{total}")
        
        for result in results:
            status = "✓ PASS" if result['success'] else "✗ FAIL"
            print(f"  {status}: {result['agent']}")
        
        return passed == total


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test deployed A2A agents')
    parser.add_argument('--config', default='cognito_config.json', help='Cognito config file')
    parser.add_argument('--deployment', default='deployment_info.json', help='Deployment info file')
    parser.add_argument('--agent', help='Test specific agent only')
    parser.add_argument('--message', help='Custom test message')
    args = parser.parse_args()
    
    tester = AgentTester(
        config_file=args.config,
        deployment_file=args.deployment
    )
    
    if args.agent and args.message:
        # Test specific agent with custom message
        success = asyncio.run(tester.test_agent(args.agent, args.message))
        sys.exit(0 if success else 1)
    else:
        # Run all tests
        success = asyncio.run(tester.run_tests())
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
