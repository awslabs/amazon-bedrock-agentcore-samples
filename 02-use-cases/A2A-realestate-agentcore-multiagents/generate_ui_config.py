#!/usr/bin/env python3
"""
Generate UI configuration with OAuth token and agent ARNs
Creates .env.local file for React app
"""

import json
import os
import sys

def main():
    print("="*70)
    print("Generating UI Configuration")
    print("="*70)
    
    # Load deployment info
    if not os.path.exists('deployment_info.json'):
        print("❌ Error: deployment_info.json not found")
        print("Please deploy agents first: python deploy_agents_with_oauth.py")
        sys.exit(1)
    
    with open('deployment_info.json', 'r', encoding='utf-8') as f:
        deployment_info = json.load(f)
    
    # Always generate a fresh bearer token (tokens expire in 60 minutes)
    print("\n🔑 Generating fresh OAuth bearer token...")
    
    # Import the token generation function instead of using subprocess
    from get_fresh_token import generate_fresh_token
    
    access_token, expires_at = generate_fresh_token('deployment_info.json')
    
    if not access_token:
        print("❌ Failed to generate token")
        sys.exit(1)
    
    print("✅ Fresh token generated")
    
    # Token is already saved to file by generate_fresh_token()
    # Read the token
    token_file = '.bearer_token'
    with open(token_file, 'r', encoding='utf-8') as f:
        bearer_token = f.read().strip()
    
    # Get coordinator agent ARN
    coordinator_agent_arn = None
    
    for agent in deployment_info['agents']:
        if 'coordinator' in agent['name']:
            coordinator_agent_arn = agent['arn']
            break
    
    if not coordinator_agent_arn:
        print("❌ Error: Coordinator agent ARN not found in deployment_info.json")
        print("Please ensure the coordinator agent is deployed")
        sys.exit(1)
    
    # Create .env.local file for React
    env_content = f"""# Auto-generated configuration for Real Estate UI
# Generated: {json.loads(json.dumps(deployment_info))['timestamp']}

# OAuth Bearer Token (expires in 60 minutes)
VITE_BEARER_TOKEN={bearer_token}

# Coordinator Agent ARN (orchestrates sub-agents via A2A protocol)
VITE_COORDINATOR_AGENT_ARN={coordinator_agent_arn}

# API Mode (direct = connect directly to AWS coordinator)
VITE_API_MODE=direct
"""
    
    env_file = 'ui/.env.local'
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print(f"\n✅ Configuration generated successfully!")
    print(f"\nCreated: {env_file}")
    print(f"\nConfiguration:")
    print(f"  • Bearer Token: {bearer_token[:30]}...")
    print(f"  • Coordinator Agent: {coordinator_agent_arn}")
    print(f"  • API Mode: Direct (connects to coordinator)")
    
    print(f"\n⚠️  Note: Bearer token expires in 60 minutes")
    print(f"   Run this script again to refresh the token")
    
    print("\n" + "="*70)
    print("Ready to start UI!")
    print("="*70)
    print("\nRun: ./start-ui.sh")
    print()

if __name__ == '__main__':
    main()
