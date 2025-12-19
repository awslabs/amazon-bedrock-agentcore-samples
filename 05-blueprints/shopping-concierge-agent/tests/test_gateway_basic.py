#!/usr/bin/env python3
"""
Test Gateway Tool Discovery and Filtering

Tests tool discovery and MCPClient tool_filters functionality.
For tool execution tests, see test_gateway_tools.py.

Usage:
    uv run --with boto3 --with requests --with colorama --with strands-agents --with mcp \
        python tests/test_gateway_basic.py
"""

import sys
import re
import asyncio
from pathlib import Path

import requests
from colorama import Fore, Style, init

sys.path.insert(0, str(Path(__file__).parent))
from utils import print_msg, print_section, get_agent_config

init(autoreset=True)


def call_gateway(gateway_url: str, access_token: str, method: str, params: dict = None) -> dict:
    """Call gateway with MCP JSON-RPC request."""
    mcp_request = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params:
        mcp_request["params"] = params
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    return requests.post(gateway_url, headers=headers, json=mcp_request, timeout=30)


def test_tool_organization(all_tools: list) -> list:
    """Test that tools are properly organized by category."""
    print("\n" + "=" * 60)
    print(f"{Fore.CYAN}TOOL ORGANIZATION TESTS{Style.RESET_ALL}")
    print("=" * 60)
    
    results = []
    
    # Categorize tools
    cart_tools = [t for t in all_tools if t["name"].startswith("cart")]
    shopping_tools = [t for t in all_tools if t["name"].startswith("shopping")]
    
    print(f"\n📊 Tool Distribution:")
    print(f"   Cart tools: {len(cart_tools)}")
    print(f"   Shopping tools: {len(shopping_tools)}")
    print(f"   Total tools: {len(all_tools)}")
    
    # Test 1: Cart tools exist
    print(f"\n🧪 Test 1: Cart tools available")
    if len(cart_tools) >= 5:
        print(f"   {Fore.GREEN}✓ Found {len(cart_tools)} cart tools{Style.RESET_ALL}")
        results.append(True)
    else:
        print(f"   {Fore.RED}✗ Expected at least 5 cart tools, found {len(cart_tools)}{Style.RESET_ALL}")
        results.append(False)
    
    # Test 2: Shopping tools exist
    print(f"\n🧪 Test 2: Shopping tools available")
    if len(shopping_tools) >= 2:
        print(f"   {Fore.GREEN}✓ Found {len(shopping_tools)} shopping tools{Style.RESET_ALL}")
        results.append(True)
    else:
        print(f"   {Fore.RED}✗ Expected at least 2 shopping tools, found {len(shopping_tools)}{Style.RESET_ALL}")
        results.append(False)
    
    # Test 3: Tool naming convention
    print(f"\n🧪 Test 3: Tool naming convention")
    valid_prefixes = ["carttools", "shoppingtools", "x_amz_bedrock_agentcore"]
    naming_ok = True
    for tool in all_tools:
        if "___" in tool["name"]:
            prefix = tool["name"].split("___")[0]
            if not any(prefix.startswith(p) for p in valid_prefixes):
                print(f"   {Fore.YELLOW}⚠ Unexpected prefix: {prefix}{Style.RESET_ALL}")
                naming_ok = False
    
    if naming_ok:
        print(f"   {Fore.GREEN}✓ All tools follow naming convention{Style.RESET_ALL}")
        results.append(True)
    else:
        results.append(False)
    
    return results


def create_gateway_mcp_client(access_token: str, gateway_url: str, tool_filter_pattern: str, prefix: str = "gateway"):
    """
    Create MCP client with tool filtering - same approach as gateway_client.py.
    Default prefix is "gateway" for all tools.
    """
    from strands.tools.mcp import MCPClient
    from mcp.client.streamable_http import streamablehttp_client
    
    tool_filters = {"allowed": [re.compile(tool_filter_pattern)]}
    
    return MCPClient(
        lambda: streamablehttp_client(
            url=gateway_url,
            headers={"Authorization": f"Bearer {access_token}"}
        ),
        prefix=prefix,
        tool_filters=tool_filters
    )


def test_mcpclient_tool_filters(gateway_url: str, access_token: str) -> list:
    """Test that tool_filters works exactly as used in the agent code."""
    print("\n" + "=" * 60)
    print(f"{Fore.CYAN}MCPCLIENT TOOL_FILTERS TESTS{Style.RESET_ALL}")
    print("=" * 60)
    print(f"Testing the exact same filtering approach used by agents")
    
    try:
        from strands.tools.mcp import MCPClient
    except ImportError as e:
        print(f"\n   {Fore.YELLOW}⚠ Cannot import strands: {e}{Style.RESET_ALL}")
        return []
    
    results = []
    
    def test_filter(name: str, filter_pattern: str, expected_min: int):
        """Test filter using same create_gateway_mcp_client approach."""
        print(f"\n🧪 {name}: get_gateway_client(\"{filter_pattern}\")")
        
        try:
            client = create_gateway_mcp_client(access_token, gateway_url, filter_pattern)
            
            with client:
                tools = client.list_tools_sync()
                tool_names = [t.tool_name for t in tools]
                
                print(f"   Found {len(tools)} tools:")
                for t_name in tool_names[:5]:
                    print(f"     - {t_name}")
                if len(tool_names) > 5:
                    print(f"     ... and {len(tool_names) - 5} more")
                
                if len(tools) >= expected_min:
                    print(f"   {Fore.GREEN}✓ Filter works correctly{Style.RESET_ALL}")
                    return True
                else:
                    print(f"   {Fore.RED}✗ Expected at least {expected_min}, got {len(tools)}{Style.RESET_ALL}")
                    return False
        except Exception as e:
            print(f"   {Fore.RED}✗ Error: {e}{Style.RESET_ALL}")
            return False
    
    # Test exact same calls as used in agent code
    results.append(test_filter("Cart Subagent", "^carttools___", 5))
    results.append(test_filter("Shopping Subagent", "^shoppingtools___", 2))
    
    return results


def main():
    print_section("Gateway Tool Discovery & Filtering Test")
    
    # Load configuration
    print_msg("Loading configuration", "info")
    try:
        config = get_agent_config()
        gateway_url = config["gateway_url"]
        access_token = config["access_token"]
        print(f"Gateway URL: {gateway_url}")
        print_msg("Token obtained", "success")
    except Exception as e:
        print_msg(f"Setup failed: {e}", "error")
        sys.exit(1)
    
    # List tools
    print("\n" + "-" * 60)
    print("Discovering tools from gateway...")
    
    try:
        response = call_gateway(gateway_url, access_token, "tools/list")
        if response.status_code == 200:
            result = response.json()
            tools = result.get("result", {}).get("tools", [])
            print_msg(f"Found {len(tools)} tools", "success")
            
            for tool in tools:
                print(f"   - {tool['name']}")
            
            if not tools:
                print_msg("No tools found in gateway", "error")
                sys.exit(1)
        else:
            print_msg(f"Failed to list tools: {response.status_code}", "error")
            sys.exit(1)
    except Exception as e:
        print_msg(f"Error listing tools: {e}", "error")
        sys.exit(1)
    
    # Run tests
    org_results = test_tool_organization(tools)
    filter_results = test_mcpclient_tool_filters(gateway_url, access_token)
    
    # Summary
    org_passed = sum(org_results)
    org_total = len(org_results)
    filter_passed = sum(filter_results)
    filter_total = len(filter_results)
    
    total_passed = org_passed + filter_passed
    total_tests = org_total + filter_total
    
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"Tool Organization: {org_passed}/{org_total} passed")
    print(f"MCPClient Filters: {filter_passed}/{filter_total} passed")
    print(f"Total: {total_passed}/{total_tests} passed")
    print("=" * 60)
    
    if total_passed == total_tests:
        print_msg("All tests passed!", "success")
    else:
        print_msg(f"{total_tests - total_passed} test(s) failed", "error")
    
    sys.exit(0 if total_passed == total_tests else 1)


if __name__ == "__main__":
    main()
