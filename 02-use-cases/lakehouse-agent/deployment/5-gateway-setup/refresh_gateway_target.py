#!/usr/bin/env python3
"""
Refresh AgentCore Gateway Target

This script refreshes the gateway target to pick up changes from the MCP server.
Use this after updating the MCP server code on the runtime.

Usage:
    python refresh_gateway_target.py
"""

import boto3
import sys
import time


def main():
    print("=" * 70)
    print("Refresh AgentCore Gateway Target")
    print("=" * 70)
    
    # Get region
    session = boto3.Session()
    region = session.region_name
    
    # Initialize clients
    ssm = boto3.client('ssm', region_name=region)
    agentcore = boto3.client('bedrock-agentcore-control', region_name=region)
    
    print(f"\n✅ Using region: {region}")
    
    # Get gateway ID from SSM
    try:
        gateway_id = ssm.get_parameter(Name='/app/lakehouse-agent/gateway-id')['Parameter']['Value']
        print(f"✅ Gateway ID: {gateway_id}")
    except Exception as e:
        print(f"❌ Error: Could not find gateway ID in SSM")
        print(f"   Parameter: /app/lakehouse-agent/gateway-id")
        print(f"   Error: {e}")
        sys.exit(1)
    
    # List gateway targets
    print(f"\n🔍 Listing gateway targets...")
    try:
        response = agentcore.list_gateway_targets(gatewayIdentifier=gateway_id)
        targets = response.get('items', [])
        
        if not targets:
            print(f"⚠️  No targets found for gateway {gateway_id}")
            sys.exit(0)
        
        print(f"✅ Found {len(targets)} target(s)")
        
        # Find the lakehouse MCP target
        target_to_refresh = None
        for target in targets:
            print(f"   - {target['name']} (ID: {target['targetId']})")
            if target['name'] == 'lakehouse-mcp-target':
                target_to_refresh = target
        
        if not target_to_refresh:
            print(f"\n⚠️  Target 'lakehouse-mcp-target' not found")
            print(f"   Available targets: {[t['name'] for t in targets]}")
            sys.exit(0)
        
        target_id = target_to_refresh['targetId']
        
        # Get full target details
        print(f"\n📋 Getting target details...")
        target_details = agentcore.get_gateway_target(
            gatewayIdentifier=gateway_id,
            targetId=target_id
        )
        
        print(f"✅ Target: {target_details['name']}")
        print(f"   Status: {target_details.get('status', 'UNKNOWN')}")
        
        # Option 1: Just trigger a sync by getting the target (this may refresh cache)
        print(f"\n🔄 Triggering gateway sync...")
        print(f"   The gateway will automatically sync with the MCP server")
        print(f"   This may take a few minutes...")
        
        # Option 2: If you want to force refresh, delete and recreate
        print(f"\n❓ Do you want to force refresh by recreating the target?")
        print(f"   This will delete and recreate the target connection.")
        print(f"   Type 'yes' to proceed, or press Enter to skip: ", end='')
        
        user_input = input().strip().lower()
        
        if user_input == 'yes':
            print(f"\n🗑️  Deleting target: {target_id}")
            agentcore.delete_gateway_target(
                gatewayIdentifier=gateway_id,
                targetId=target_id
            )
            print(f"✅ Target deleted")
            
            print(f"\n⏳ Waiting 5 seconds before recreating...")
            time.sleep(5)
            
            print(f"\n📝 To recreate the target, run:")
            print(f"   python create_gateway.py")
            print(f"\n   Or manually recreate it in the AWS Console")
        else:
            print(f"\n✅ Skipped force refresh")
            print(f"\n💡 The gateway should automatically sync within a few minutes")
            print(f"   If tools are not appearing, try:")
            print(f"   1. Wait 5-10 minutes for automatic sync")
            print(f"   2. Run this script again and choose 'yes' to force refresh")
            print(f"   3. Or run: python create_gateway.py")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "=" * 70)
    print("✨ Done!")
    print("=" * 70)


if __name__ == '__main__':
    main()
