#!/usr/bin/env python3
"""
Check AgentCore Runtime CloudWatch Logs

This script retrieves recent logs from the MCP server runtime.
"""

import boto3
import sys
from datetime import datetime, timedelta


def get_logs_from_group(logs, log_group_name, minutes=10, limit=50):
    """Get recent logs from a log group."""
    print(f"\n📋 Getting recent log streams from: {log_group_name}")
    
    try:
        response = logs.describe_log_streams(
            logGroupName=log_group_name,
            orderBy='LastEventTime',
            descending=True,
            limit=5
        )
        
        if not response['logStreams']:
            print(f"   ⚠️  No log streams found")
            return
        
        print(f"   Found {len(response['logStreams'])} recent streams")
        
        # Get logs from the most recent stream
        stream_name = response['logStreams'][0]['logStreamName']
        print(f"\n📄 Latest log stream: {stream_name}")
        
        # Get logs from last N minutes
        start_time = int((datetime.now() - timedelta(minutes=minutes)).timestamp() * 1000)
        
        log_response = logs.get_log_events(
            logGroupName=log_group_name,
            logStreamName=stream_name,
            startTime=start_time,
            limit=limit
        )
        
        events = log_response['events']
        if not events:
            print(f"\n   ⚠️  No recent log events in last {minutes} minutes")
        else:
            print(f"\n📝 Recent Log Events ({len(events)} events):")
            print("=" * 70)
            for event in events:
                timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
                message = event['message'].strip()
                print(f"[{timestamp.strftime('%H:%M:%S')}] {message}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")


def main():
    session = boto3.Session()
    region = session.region_name
    
    ssm = boto3.client('ssm', region_name=region)
    logs = boto3.client('logs', region_name=region)
    
    print("=" * 70)
    print("Check AgentCore Runtime Logs")
    print("=" * 70)
    
    # Get runtime info from SSM
    print("\n🔍 Loading runtime configuration from SSM...")
    try:
        runtime_arn = ssm.get_parameter(Name='/app/lakehouse-agent/mcp-server-runtime-arn')['Parameter']['Value']
        runtime_id = ssm.get_parameter(Name='/app/lakehouse-agent/mcp-server-runtime-id')['Parameter']['Value']
        
        print(f"   MCP Server Runtime ARN: {runtime_arn}")
        print(f"   MCP Server Runtime ID: {runtime_id}")
    except Exception as e:
        print(f"   ⚠️  MCP Server runtime not found: {e}")
        runtime_id = None
    
    # List ALL AgentCore log groups
    print(f"\n🔍 Listing all AgentCore log groups...")
    
    try:
        response = logs.describe_log_groups(logGroupNamePrefix="/aws/bedrock-agentcore")
        if response['logGroups']:
            print(f"\n   Available log groups ({len(response['logGroups'])}):")
            for lg in response['logGroups']:
                name = lg['logGroupName']
                # Highlight MCP server log groups
                if 'lakehouse_mcp_server' in name.lower() or 'mcp' in name.lower():
                    print(f"      🎯 {name}  <-- MCP SERVER")
                elif 'lakehouse_agent' in name.lower():
                    print(f"      🤖 {name}  <-- AGENT")
                else:
                    print(f"      - {name}")
        else:
            print(f"   No AgentCore log groups found")
            sys.exit(1)
    except Exception as e:
        print(f"   ❌ Error listing log groups: {e}")
        sys.exit(1)
    
    # Find MCP server log group
    mcp_log_group = None
    agent_log_group = None
    
    for lg in response['logGroups']:
        name = lg['logGroupName']
        if 'lakehouse_mcp_server' in name.lower():
            mcp_log_group = name
        elif 'lakehouse_agent' in name.lower():
            agent_log_group = name
    
    # Show MCP server logs
    if mcp_log_group:
        print("\n" + "=" * 70)
        print("🎯 MCP SERVER LOGS")
        print("=" * 70)
        get_logs_from_group(logs, mcp_log_group, minutes=15, limit=100)
    else:
        print("\n⚠️  MCP Server log group not found!")
        print("   Expected pattern: /aws/bedrock-agentcore/runtimes/lakehouse_mcp_server-*")
    
    # Optionally show agent logs
    if agent_log_group:
        print("\n" + "=" * 70)
        print("🤖 AGENT LOGS (for comparison)")
        print("=" * 70)
        get_logs_from_group(logs, agent_log_group, minutes=5, limit=20)
    
    print("\n" + "=" * 70)
    print("💡 TIP: If MCP server logs don't show tool invocations, check:")
    print("   1. Gateway is routing to the correct MCP server runtime")
    print("   2. Gateway target configuration points to MCP server")
    print("   3. M2M authentication between Gateway and MCP server")
    print("=" * 70)


if __name__ == '__main__':
    main()
