"""
Deploy Real Estate Coordinator with Sub-Agent URLs as Environment Variables
"""

import os
import sys
import yaml
from pathlib import Path

# Sub-agent ARNs
property_search_arn = "arn:aws:bedrock-agentcore:us-east-1:506053230750:runtime/property_search_agent-hcIU3UFyU1"
property_booking_arn = "arn:aws:bedrock-agentcore:us-east-1:506053230750:runtime/property_booking_agent-0jtIDe6Ho0"

# Convert ARNs to runtime URLs
from urllib.parse import quote
from boto3.session import Session

boto_session = Session()
region = boto_session.region_name

search_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{quote(property_search_arn, safe='')}/invocations/"
booking_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{quote(property_booking_arn, safe='')}/invocations/"

print("=" * 70)
print("Deploying Real Estate Coordinator with Sub-Agent URLs")
print("=" * 70)
print()
print("Sub-Agent URLs:")
print(f"  Property Search: {search_url}")
print(f"  Property Booking: {booking_url}")
print()

# Update .bedrock_agentcore.yaml with environment variables
config_path = Path(".bedrock_agentcore.yaml")

with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# Add environment variables to the realestate_coordinator agent
if 'agents' in config and 'realestate_coordinator' in config['agents']:
    if 'environment' not in config['agents']['realestate_coordinator']:
        config['agents']['realestate_coordinator']['environment'] = {}
    
    config['agents']['realestate_coordinator']['environment']['PROPERTY_SEARCH_AGENT_URL'] = search_url
    config['agents']['realestate_coordinator']['environment']['PROPERTY_BOOKING_AGENT_URL'] = booking_url
    
    # Write back
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print("✓ Configuration updated with environment variables")
    print()

# Now deploy using agentcore CLI
print("Deploying with agentcore CLI...")
print()

import subprocess
result = subprocess.run(['agentcore', 'launch', '-a', 'realestate_coordinator'], 
                       capture_output=False, text=True, check=False)

if result.returncode == 0:
    print()
    print("=" * 70)
    print("✓ Deployment Complete!")
    print("=" * 70)
    print()
    print("Test the coordinator:")
    print("  python test_coordinator.py")
    print()
else:
    print()
    print("=" * 70)
    print("✗ Deployment Failed")
    print("=" * 70)
    sys.exit(1)
