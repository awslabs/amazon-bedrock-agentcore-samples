"""
Strands-based MCP Client for BAC Gateway
Replaces custom MCP client with Strands SDK patterns
"""
import os
import logging
import jwt
from typing import Dict, Any, List, Optional
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)

class StrandsMCPClient:
    """
    Strands-based MCP client for BAC Gateway
    Uses Strands SDK patterns for MCP communication
    """
    
    def __init__(self, gateway_url: Optional[str] = None):
        # BAC Gateway URL - must be provided dynamically, no environment fallback
        self.gateway_url = gateway_url
        if not self.gateway_url:
            logger.warning("BAC Gateway URL not provided - MCP tools will be unavailable until URL is set")
            self._ready = False
        else:
            self._ready = True
            logger.info(f"StrandsMCPClient initialized with Gateway URL: {self.gateway_url}")
            
        self.auth_token = None
        self.mcp_client = None
        self._tools_cache = []
        self.jwt_signature_secret = os.environ.get("JWT_SIGNATURE_SECRET", "default-secret")
    
    def update_gateway_url(self, gateway_url: str):
        """Update the BAC Gateway URL dynamically"""
        if gateway_url and gateway_url != self.gateway_url:
            logger.info(f"Updating BAC Gateway URL from {self.gateway_url} to {gateway_url}")
            self.gateway_url = gateway_url
            self._ready = True
            # Reset client to force re-initialization with new URL
            self.mcp_client = None
            self._tools_cache = []
        elif gateway_url == self.gateway_url:
            logger.debug("Gateway URL unchanged, no update needed")
        else:
            logger.warning("Empty gateway URL provided, ignoring update")
    
    async def initialize(self):
        """Initialize Strands MCP client"""
        try:
            logger.info(f"Initializing Strands MCP client with BAC Gateway: {self.gateway_url}")
            self._ready = True
            logger.info("Strands MCP client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Strands MCP client: {str(e)}")
    
    def is_ready(self) -> bool:
        """Check if MCP client is ready"""
        return self._ready
    
    async def set_auth_token(self, token: str):
        """Set OAuth authentication token and create MCP client"""
        try:
            self.auth_token = token
            logger.info(f"Setting auth token for Gateway URL: {self.gateway_url}")
            
            if not self.gateway_url:
                logger.error("Cannot create MCP client: Gateway URL not set")
                return
            
            # Create Strands MCP client with same authentication as direct MCP calls
            # Use only Bearer token, no JWT token to match working direct calls
            self.mcp_client = MCPClient(lambda: streamablehttp_client(
                url=self.gateway_url,
                headers={
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            ))
            
            # Start the MCP client (synchronous method)
            self.mcp_client.start()
            
            # Fetch available tools
            await self._fetch_tools()
            
            logger.info(f"Strands MCP client connected to {self.gateway_url} with {len(self._tools_cache)} tools")
            
        except Exception as e:
            logger.error(f"Error setting auth token and creating MCP client: {str(e)}")
            self.mcp_client = None
    
    async def get_available_tools(self) -> List[Dict]:
        """Get list of available MCP tools"""
        if not self.is_ready() or not self.mcp_client:
            return []
        
        return self._tools_cache
    
    async def _fetch_tools(self):
        """Fetch available tools using Strands MCP client"""
        try:
            if not self.mcp_client:
                logger.warning("MCP client not initialized")
                return
            
            # Use Strands MCP client to list tools (async version)
            tools = await self.mcp_client.list_tools()
            
            # Convert Strands tools to our expected format
            self._tools_cache = []
            for tool in tools:
                try:
                    # Handle different tool attribute patterns
                    tool_name = getattr(tool, 'name', None) or getattr(tool, '_name', None) or str(tool)
                    tool_description = getattr(tool, 'description', None) or getattr(tool, '_description', None) or "No description available"
                    tool_schema = getattr(tool, 'inputSchema', None) or getattr(tool, 'input_schema', None) or {"type": "object"}
                    
                    tool_def = {
                        "name": tool_name,
                        "description": tool_description,
                        "inputSchema": tool_schema
                    }
                    self._tools_cache.append(tool_def)
                except Exception as tool_error:
                    logger.warning(f"Error processing tool {tool}: {str(tool_error)}")
                    continue
            
            logger.info(f"Fetched {len(self._tools_cache)} tools from BAC Gateway via Strands")
            
        except Exception as e:
            logger.error(f"Error fetching tools via Strands: {str(e)}")
    
    def get_mcp_tools_for_agent(self) -> List:
        """Get MCP tools in Strands format for agent integration"""
        if not self.mcp_client:
            logger.warning("MCP client not available for agent tools")
            return []
        
        try:
            # Return Strands MCP tools directly
            # The MCP client should provide tools that Strands Agent can use
            tools = []
            
            # Try to get tools from the MCP client
            if hasattr(self.mcp_client, 'list_tools_sync'):
                tools = self.mcp_client.list_tools_sync()
                logger.info("Got tools using list_tools_sync method")
            elif hasattr(self.mcp_client, 'tools'):
                tools = self.mcp_client.tools
                logger.info("Got tools using tools attribute")
            else:
                logger.warning("MCP client doesn't have expected tool methods")
                return []
            
            # Log detailed information about each tool
            logger.info(f"Retrieved {len(tools)} tools from MCP client")
            for i, tool in enumerate(tools[:5]):  # Log first 5 tools
                tool_name = getattr(tool, 'name', None) or getattr(tool, '_name', None) or str(tool)
                logger.info(f"Tool {i}: name={tool_name}, type={type(tool).__name__}, length={len(tool_name)}")
                if '___' in tool_name:
                    prefix, operation = tool_name.split('___', 1)
                    logger.info(f"  - Tool name has prefix: prefix={prefix}, operation={operation}")
            
            logger.info(f"Returning {len(tools)} Strands MCP tools for agent")
            logger.debug(f"Tool types: {[type(tool).__name__ for tool in tools[:3]]}")  # Log first 3 tool types
            
            return tools
        except Exception as e:
            logger.error(f"Error getting MCP tools for agent: {str(e)}")
            return []
    
    async def close(self):
        """Close the MCP client"""
        try:
            if self.mcp_client:
                # Strands MCP client cleanup
                logger.info("Closing Strands MCP client")
                # Note: Strands MCPClient may not have explicit close method
                self.mcp_client = None
        except Exception as e:
            logger.error(f"Error closing Strands MCP client: {str(e)}")
