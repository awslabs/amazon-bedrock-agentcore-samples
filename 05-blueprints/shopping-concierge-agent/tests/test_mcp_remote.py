#!/usr/bin/env python3
"""
Test MCP Server Remotely

Tests the Travel MCP Server using the MCP client library.
Connects directly to the MCP runtime (not through gateway).

Usage:
    uv run --with boto3 --with requests --with mcp tests/test-mcp-remote.py

Requirements:
    - AWS credentials configured
    - MCP server deployed (TravelStack)
    - amplify_outputs.json exists
    - mcp library installed

Note: This test requires the 'mcp' package which may need special installation.
For most testing, use test-gateway.py instead.
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

import boto3

# Add parent to path for utils import
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import print_msg, print_section, get_oauth_token, get_stack_exports, REGION


async def test_mcp_server():
    """Test the MCP server using MCP client library."""
    
    # Try to import MCP - may not be installed
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError:
        print_msg("MCP library not installed. Install with: pip install mcp", "error")
        print_msg("For gateway testing, use test-gateway.py instead", "info")
        return False
    
    print_section("MCP Server - Remote Test")
    
    # Get configuration
    print_msg("Loading configuration", "info")
    try:
        access_token, config = get_oauth_token()
        
        # Get exports directly (not filtered by AgentStack prefix)
        cfn = boto3.client("cloudformation", region_name=REGION)
        
        deployment_id = config.get("deployment_id", "shopping")
        runtime_arn = None
        
        # Handle pagination
        paginator = cfn.get_paginator('list_exports')
        for page in paginator.paginate():
            for export in page.get("Exports", []):
                name = export["Name"]
                # Look for ShoppingStack MCP runtime matching deployment ID
                if f"ShoppingStack-{deployment_id}" in name and "RuntimeArn" in name:
                    runtime_arn = export["Value"]
                    print(f"Found MCP runtime: {name}")
                    break
            if runtime_arn:
                break
        
        if not runtime_arn:
            print_msg(f"Could not find ShoppingStack-{deployment_id} or CartStack-{deployment_id} RuntimeArn in CloudFormation exports", "error")
            print_msg("Make sure MCP stacks are deployed for this deployment ID", "info")
            return False
        
        print(f"Runtime ARN: {runtime_arn[:60]}...")
        print_msg("Token obtained", "success")
    except Exception as e:
        print_msg(f"Setup failed: {e}", "error")
        return False
    
    # Construct MCP URL
    encoded_arn = runtime_arn.replace(":", "%3A").replace("/", "%2F")
    mcp_url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    
    headers = {
        "authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    print(f"\nConnecting to MCP server...")
    print(f"URL: {mcp_url[:80]}...")
    
    try:
        async with streamablehttp_client(
            mcp_url, 
            headers, 
            timeout=timedelta(seconds=30), 
            terminate_on_close=True
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize session with timeout
                print("\nInitializing MCP session...")
                try:
                    await asyncio.wait_for(session.initialize(), timeout=15)
                except asyncio.TimeoutError:
                    print_msg("MCP session initialization timed out", "error")
                    return False
                print_msg("MCP session initialized", "success")
                
                # List tools
                print("\nListing available tools...")
                tool_result = await asyncio.wait_for(session.list_tools(), timeout=15)
                
                print(f"\nFound {len(tool_result.tools)} tools:")
                for tool in tool_result.tools:
                    print(f"  - {tool.name}")
                
                # Test a tool - use first available tool
                print("\nTesting tool call...")
                if tool_result.tools:
                    test_tool = tool_result.tools[0]
                    print(f"Tool: {test_tool.name}")
                    
                    # Try to call with minimal args
                    test_args = {"user_id": "test-user"}
                    print(f"Args: {test_args}")
                    
                    call_result = await asyncio.wait_for(
                        session.call_tool(
                            test_tool.name,
                            arguments=test_args
                        ),
                        timeout=60
                    )
                else:
                    print_msg("No tools found to test", "error")
                    return False
                
                print_msg("Tool call completed", "success")
                
                print("\nResponse:")
                print("-" * 60)
                for content in call_result.content:
                    if hasattr(content, "text"):
                        print(content.text[:500])
                    else:
                        print(content)
                print("-" * 60)
                
                return True
        
    except asyncio.TimeoutError:
        print_msg("Operation timed out", "error")
        return False
    except Exception as e:
        print_msg(f"Error: {e}", "error")
        # Only print short error, not full traceback for expected failures
        if "validation error" in str(e).lower() or "protocol" in str(e).lower():
            print_msg("This runtime may not support MCP protocol directly", "info")
            print_msg("Use test-gateway.py for gateway-based testing instead", "info")
        else:
            import traceback
            traceback.print_exc()
        return False


def main():
    success = asyncio.run(test_mcp_server())
    
    if success:
        print_msg("MCP server test passed!", "success")
    else:
        print_msg("MCP server test failed", "error")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
