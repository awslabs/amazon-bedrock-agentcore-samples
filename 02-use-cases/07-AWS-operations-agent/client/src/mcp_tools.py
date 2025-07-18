"""
Simple MCP tools manager - just calls Lambda APIs
"""
from typing import Dict, Any
from lambda_client import LambdaClient
import config

class MCPTools:
    """Simple MCP tools manager"""
    
    def __init__(self, lambda_client: LambdaClient):
        self.lambda_client = lambda_client
        self.okta_token = None
        self.tools = []
    
    def set_token(self, token: str):
        """Set Okta token and fetch tools"""
        self.okta_token = token
        self.fetch_tools()
    
    def fetch_tools(self):
        """Fetch tools from Lambda"""
        if not self.okta_token:
            print("⚠️  No Okta token - cannot fetch MCP tools")
            return
        
        print("🔄 Fetching MCP tools...")
        url = config.get_tools_url(self.lambda_client.function_url)
        
        # Include both Okta token and Bedrock AgentCore Gateway URL in the request
        request_data = {
            "okta_token": self.okta_token,
            "bedrock_agentcore_gateway_url": config.BEDROCK_AGENTCORE_GATEWAY_URL
        }
        
        result = self.lambda_client.call_api(url, 'POST', request_data)
        
        if "error" in result:
            print(f"⚠️  Failed to fetch tools: {result['error']}")
            return
        
        self.tools = result.get("tools", [])
        print(f"🛠️  Available MCP tools: {len(self.tools)}")
        for tool in self.tools:
            print(f"   - {tool.get('name', 'unknown')}")
    
    def list_tools(self):
        """List available tools"""
        if not self.tools:
            print("⚠️  No MCP tools available")
            return
        
        print("\n🛠️  Available MCP tools:")
        for i, tool in enumerate(self.tools, 1):
            print(f"  {i}. {tool.get('name', 'unknown')}")
            print(f"     {tool.get('description', 'No description')}")
    
    def has_tools(self):
        """Check if tools are available"""
        return len(self.tools) > 0
