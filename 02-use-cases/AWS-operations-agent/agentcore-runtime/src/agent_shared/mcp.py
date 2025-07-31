# ============================================================================
# IMPORTS
# ============================================================================

import logging
from .auth import get_m2m_token

logger = logging.getLogger(__name__)

# Global MCP client for persistent connection
_global_mcp_client = None
_global_gateway_url = None
_global_token = None

def create_global_mcp_client(gateway_url, token=None):
    """
    Create a global MCP client that stays alive for the application lifetime.
    
    Args:
        gateway_url (str): Gateway URL for MCP connection
        token (str, optional): OAuth token. If None, will try to get one automatically
    
    Returns:
        MCPClient or None: MCP client instance or None if not available
    """
    global _global_mcp_client, _global_gateway_url, _global_token
    
    if not gateway_url:
        logger.info("🏠 No gateway URL provided - MCP client not created")
        return None
    
    try:
        # Import MCP dependencies
        from mcp.client.streamable_http import streamablehttp_client
        from strands.tools.mcp.mcp_client import MCPClient
        
        # Get token if not provided
        if not token:
            token = get_m2m_token()
            if not token:
                logger.warning("⚠️ No OAuth token available for MCP client")
                return None
        
        logger.info(f"🔗 Creating global MCP client for gateway: {gateway_url}")
        logger.info(f"🔑 Using token (length: {len(token)})")
        
        # Create transport with authentication
        def create_transport():
            headers = {"Authorization": f"Bearer {token}"}
            return streamablehttp_client(gateway_url, headers=headers)
        
        # Create and start MCP client
        mcp_client = MCPClient(create_transport)
        
        # Store globally
        _global_mcp_client = mcp_client
        _global_gateway_url = gateway_url
        _global_token = token
        
        logger.info(f"✅ Global MCP client created successfully")
        return mcp_client
        
    except ImportError as e:
        logger.warning(f"⚠️ MCP dependencies not available: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to create global MCP client: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        return None

def get_mcp_tools_simple(gateway_url, token=None):
    """
    Get available tools from MCP gateway using a simple approach.
    
    Args:
        gateway_url (str): Gateway URL for MCP connection
        token (str, optional): OAuth token. If None, will try to get one automatically
    
    Returns:
        list: List of available tools or empty list if none available
    """
    if not gateway_url:
        logger.info("🏠 No gateway URL provided - returning empty tools list")
        return []
    
    try:
        # Import MCP dependencies
        from mcp.client.streamable_http import streamablehttp_client
        from strands.tools.mcp.mcp_client import MCPClient
        
        # Get token if not provided
        if not token:
            token = get_m2m_token()
            if not token:
                logger.warning("⚠️ No OAuth token available for MCP client")
                return []
        
        logger.info(f"🔗 Creating simple MCP client for tool discovery")
        logger.info(f"🌐 Gateway: {gateway_url}")
        logger.info(f"🔑 Using token (length: {len(token)})")
        
        # Create transport with authentication
        def create_transport():
            headers = {"Authorization": f"Bearer {token}"}
            return streamablehttp_client(gateway_url, headers=headers)
        
        # Use MCP client within context manager for tool discovery only
        with MCPClient(create_transport) as mcp_client:
            logger.info("🔍 Attempting to list tools from MCP client...")
            
            # Get tools from MCP client
            tools = mcp_client.list_tools_sync()
            tool_count = len(tools) if tools else 0
            
            logger.info(f"🛠️ Found {tool_count} MCP tools")
            
            if tools:
                logger.info("📋 Available MCP tools:")
                for i, tool in enumerate(tools[:5]):  # Show first 5 tools
                    # Try to get tool name from tool_spec
                    tool_spec = getattr(tool, 'tool_spec', None)
                    if tool_spec and hasattr(tool_spec, 'name'):
                        tool_name = tool_spec.name
                        tool_desc = getattr(tool_spec, 'description', 'No description')
                    else:
                        tool_name = getattr(tool, 'tool_name', 'Unknown')
                        tool_desc = 'No description'
                    
                    logger.info(f"   {i+1}. {tool_name}: {tool_desc[:50]}...")
                if len(tools) > 5:
                    logger.info(f"   ... and {len(tools) - 5} more tools")
            
            # Return the tools - the client will stay alive within the context manager
            # The key is that we need to keep the client alive for the agent's lifetime
            logger.info("✅ Returning MCP tools for agent integration")
            return tools or []
        
    except Exception as e:
        logger.error(f"❌ Failed to get MCP tools: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        return []

# ============================================================================
# MCP CLIENT CREATION
# ============================================================================

def create_mcp_client(gateway_url, token=None):
    """
    Create MCP client with authentication.
    
    Args:
        gateway_url (str): Gateway URL for MCP connection
        token (str, optional): OAuth token. If None, will try to get one automatically
    
    Returns:
        MCPClient or None: MCP client instance or None if not available
    """
    if not gateway_url:
        logger.info("🏠 No gateway URL provided - MCP client not created")
        return None
    
    try:
        # Import MCP dependencies
        from mcp.client.streamable_http import streamablehttp_client
        from strands.tools.mcp.mcp_client import MCPClient
        
        # Get token if not provided
        if not token:
            token = get_m2m_token()
            if not token:
                logger.warning("⚠️ No OAuth token available for MCP client")
                return None
        
        logger.info(f"🔗 Creating MCP client for gateway: {gateway_url}")
        logger.info(f"🔑 Using token (length: {len(token)}, starts with: {token[:20]}...)")
        
        # Create transport with authentication
        def create_transport():
            headers = {"Authorization": f"Bearer {token}"}
            logger.info(f"🌐 Creating transport with headers: {list(headers.keys())}")
            return streamablehttp_client(
                gateway_url,
                headers=headers
            )
        
        # Create MCP client
        mcp_client = MCPClient(create_transport)
        logger.info(f"✅ MCP client created successfully")
        
        # Test the connection by trying to initialize
        try:
            # This will test the connection
            logger.info("🔍 Testing MCP client connection...")
            # Don't close the client here - let it stay open
            logger.info("✅ MCP client connection test passed")
        except Exception as test_e:
            logger.warning(f"⚠️ MCP client connection test failed: {test_e}")
            # Still return the client as it might work when actually used
        
        return mcp_client
        
    except ImportError as e:
        logger.warning(f"⚠️ MCP dependencies not available: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to create MCP client: {e}")
        return None

# ============================================================================
# TOOL DISCOVERY
# ============================================================================

def get_mcp_tools_with_client(gateway_url, token=None):
    """
    Get available tools from MCP gateway using a properly managed client.
    
    Args:
        gateway_url (str): Gateway URL for MCP connection
        token (str, optional): OAuth token. If None, will try to get one automatically
    
    Returns:
        list: List of available tools or empty list if none available
    """
    if not gateway_url:
        logger.info("🏠 No gateway URL provided - returning empty tools list")
        return []
    
    try:
        # Import MCP dependencies
        from mcp.client.streamable_http import streamablehttp_client
        from strands.tools.mcp.mcp_client import MCPClient
        
        # Get token if not provided
        if not token:
            token = get_m2m_token()
            if not token:
                logger.warning("⚠️ No OAuth token available for MCP client")
                return []
        
        logger.info(f"🔗 Creating MCP client for tool discovery")
        logger.info(f"🌐 Gateway: {gateway_url}")
        logger.info(f"🔑 Using token (length: {len(token)})")
        
        # Create transport with authentication
        def create_transport():
            headers = {"Authorization": f"Bearer {token}"}
            return streamablehttp_client(gateway_url, headers=headers)
        
        # Use MCP client within context manager
        with MCPClient(create_transport) as mcp_client:
            logger.info("🔍 Attempting to list tools from MCP client...")
            
            # Get tools from MCP client
            tools = mcp_client.list_tools_sync()
            tool_count = len(tools) if tools else 0
            
            logger.info(f"🛠️ Found {tool_count} MCP tools")
            
            if tools:
                logger.info("📋 Available MCP tools:")
                for i, tool in enumerate(tools[:5]):  # Show first 5 tools
                    # Try different attribute names for tool info
                    tool_name = getattr(tool, 'name', None) or getattr(tool, 'tool_name', None) or str(tool)
                    tool_desc = getattr(tool, 'description', None) or getattr(tool, 'tool_description', None) or 'No description'
                    
                    # Debug: show tool attributes
                    tool_attrs = [attr for attr in dir(tool) if not attr.startswith('_')]
                    logger.debug(f"   Tool {i+1} attributes: {tool_attrs}")
                    
                    logger.info(f"   {i+1}. {tool_name}: {tool_desc[:50]}...")
                if len(tools) > 5:
                    logger.info(f"   ... and {len(tools) - 5} more tools")
            
            return tools or []
        
    except ImportError as e:
        logger.warning(f"⚠️ MCP dependencies not available: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Failed to get MCP tools: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        return []

def get_mcp_tools(mcp_client):
    """
    Get available tools from MCP client (legacy function for compatibility).
    
    Args:
        mcp_client: MCP client instance
    
    Returns:
        list: List of available tools or empty list if none available
    """
    if not mcp_client:
        logger.info("🏠 No MCP client provided - returning empty tools list")
        return []
    
    try:
        logger.info("🔍 Attempting to list tools from MCP client...")
        
        # Get tools from MCP client
        tools = mcp_client.list_tools_sync()
        tool_count = len(tools) if tools else 0
        
        logger.info(f"🛠️ Found {tool_count} MCP tools")
        
        if tools:
            logger.info("📋 Available MCP tools:")
            for i, tool in enumerate(tools[:5]):  # Show first 5 tools
                tool_name = getattr(tool, 'name', 'Unknown')
                tool_desc = getattr(tool, 'description', 'No description')
                logger.info(f"   {i+1}. {tool_name}: {tool_desc[:50]}...")
            if len(tools) > 5:
                logger.info(f"   ... and {len(tools) - 5} more tools")
        
        return tools or []
        
    except Exception as e:
        logger.error(f"❌ Failed to get MCP tools: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        return []

# ============================================================================
# PERSISTENT MCP CLIENT MANAGEMENT
# ============================================================================

def create_persistent_mcp_client(gateway_url, token=None):
    """
    Create a persistent MCP client that stays alive for tool execution.
    
    Args:
        gateway_url (str): Gateway URL for MCP connection
        token (str, optional): OAuth token. If None, will try to get one automatically
    
    Returns:
        MCPClient or None: MCP client instance or None if not available
    """
    global _global_mcp_client, _global_gateway_url, _global_token
    
    if not gateway_url:
        logger.info("🏠 No gateway URL provided - MCP client not created")
        return None
    
    try:
        # Import MCP dependencies
        from mcp.client.streamable_http import streamablehttp_client
        from strands.tools.mcp.mcp_client import MCPClient
        
        # Get token if not provided
        if not token:
            token = get_m2m_token()
            if not token:
                logger.warning("⚠️ No OAuth token available for MCP client")
                return None
        
        logger.info(f"🔗 Creating persistent MCP client for gateway: {gateway_url}")
        logger.info(f"🔑 Using token (length: {len(token)})")
        
        # Create transport with authentication
        def create_transport():
            headers = {"Authorization": f"Bearer {token}"}
            return streamablehttp_client(gateway_url, headers=headers)
        
        # Create MCP client (don't use context manager - keep it alive)
        mcp_client = MCPClient(create_transport)
        
        # Initialize the client
        mcp_client.__enter__()
        
        # Store globally for tool execution
        _global_mcp_client = mcp_client
        _global_gateway_url = gateway_url
        _global_token = token
        
        logger.info(f"✅ Persistent MCP client created successfully")
        return mcp_client
        
    except ImportError as e:
        logger.warning(f"⚠️ MCP dependencies not available: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to create persistent MCP client: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        return None

def get_global_mcp_client():
    """
    Get the global MCP client for tool execution.
    
    Returns:
        MCPClient or None: Global MCP client instance
    """
    return _global_mcp_client

def cleanup_global_mcp_client():
    """
    Clean up the global MCP client.
    """
    global _global_mcp_client
    if _global_mcp_client:
        try:
            # The client should already be closed from the context manager
            logger.info("🧹 Global MCP client cleaned up")
        except Exception as e:
            logger.warning(f"⚠️ Error cleaning up global MCP client: {e}")
        finally:
            _global_mcp_client = None

def cleanup_mcp_client():
    """Legacy cleanup function for compatibility"""
    cleanup_global_mcp_client()

def get_mcp_tools_with_persistent_client(gateway_url, token=None):
    """
    Get available tools from MCP gateway using a persistent client.
    
    Args:
        gateway_url (str): Gateway URL for MCP connection
        token (str, optional): OAuth token. If None, will try to get one automatically
    
    Returns:
        list: List of available tools or empty list if none available
    """
    if not gateway_url:
        logger.info("🏠 No gateway URL provided - returning empty tools list")
        return []
    
    try:
        # Create persistent client
        mcp_client = create_persistent_mcp_client(gateway_url, token)
        if not mcp_client:
            logger.warning("⚠️ Failed to create persistent MCP client")
            return []
        
        logger.info("🔍 Attempting to list tools from persistent MCP client...")
        
        # Get tools from MCP client
        tools = mcp_client.list_tools_sync()
        tool_count = len(tools) if tools else 0
        
        logger.info(f"🛠️ Found {tool_count} MCP tools")
        
        if tools:
            logger.info("📋 Available MCP tools:")
            for i, tool in enumerate(tools[:5]):  # Show first 5 tools
                # Try different attribute names for tool info
                tool_name = getattr(tool, 'name', None) or getattr(tool, 'tool_name', None) or str(tool)
                tool_desc = getattr(tool, 'description', None) or getattr(tool, 'tool_description', None) or 'No description'
                
                logger.info(f"   {i+1}. {tool_name}: {tool_desc[:50]}...")
            if len(tools) > 5:
                logger.info(f"   ... and {len(tools) - 5} more tools")
        
        return tools or []
        
    except Exception as e:
        logger.error(f"❌ Failed to get MCP tools with persistent client: {e}")
        import traceback
        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        return []

# ============================================================================
# ERROR HANDLING
# ============================================================================

def is_mcp_available(gateway_url):
    """
    Check if MCP functionality is available.
    
    Args:
        gateway_url (str): Gateway URL to check
    
    Returns:
        bool: True if MCP can be used
    """
    if not gateway_url:
        return False
    
    try:
        # Check if MCP dependencies are available
        from mcp.client.streamable_http import streamablehttp_client
        from strands.tools.mcp.mcp_client import MCPClient
        return True
    except ImportError:
        return False