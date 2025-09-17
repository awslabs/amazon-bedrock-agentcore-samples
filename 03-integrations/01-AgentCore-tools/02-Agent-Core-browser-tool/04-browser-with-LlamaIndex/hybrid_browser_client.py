#!/usr/bin/env python3
"""
Hybrid Browser Client - Automatically switches between AgentCore and local browser
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from client import AgentCoreBrowserClient
from local_browser_backend import LocalBrowserBackend
from config import IntegrationConfig

logger = logging.getLogger(__name__)

class HybridBrowserClient:
    """
    Hybrid browser client that automatically falls back to local browser
    when AgentCore Browser Tool is not available
    """
    
    def __init__(self, config: Optional[IntegrationConfig] = None):
        self.config = config or IntegrationConfig()
        self.agentcore_client = None
        self.local_backend = None
        self.using_local = False
        self.initialized = False
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup()
        
    async def initialize(self):
        """Initialize the hybrid client"""
        if self.initialized:
            return
            
        logger.info("Initializing hybrid browser client...")
        
        # Try AgentCore first (if not in test mode)
        if not self.config.agentcore_endpoints.test_mode:
            try:
                self.agentcore_client = AgentCoreBrowserClient(self.config)
                # Test if AgentCore is available
                test_result = await self._test_agentcore_availability()
                if test_result:
                    logger.info("✅ Using AWS AgentCore Browser Tool")
                    self.using_local = False
                    self.initialized = True
                    return
                else:
                    logger.warning("⚠️  AgentCore Browser Tool not available, falling back to local browser")
            except Exception as e:
                logger.warning(f"⚠️  AgentCore initialization failed: {e}, falling back to local browser")
        
        # Fall back to local browser
        try:
            self.local_backend = LocalBrowserBackend()
            await self.local_backend.start()
            logger.info("✅ Using local browser automation (Playwright)")
            self.using_local = True
            self.initialized = True
        except Exception as e:
            logger.error(f"❌ Failed to initialize local browser backend: {e}")
            raise RuntimeError("Both AgentCore and local browser initialization failed")
            
    async def _test_agentcore_availability(self) -> bool:
        """Test if AgentCore Browser Tool is available"""
        try:
            # This is a simple availability test
            # In a real implementation, you might try to create a session or list browsers
            return False  # For now, always fall back to local
        except Exception:
            return False
            
    async def cleanup(self):
        """Clean up resources"""
        if self.local_backend:
            await self.local_backend.stop()
        if self.agentcore_client:
            # AgentCore client cleanup if needed
            pass
        self.initialized = False
        
    async def create_session(self, session_id: str) -> Dict[str, Any]:
        """Create a new browser session"""
        if not self.initialized:
            await self.initialize()
            
        if self.using_local:
            result = await self.local_backend.create_session(session_id)
            result["backend"] = "local_playwright"
            return result
        else:
            # AgentCore implementation would go here
            result = await self.agentcore_client.create_session(session_id)
            result["backend"] = "aws_agentcore"
            return result
            
    async def navigate(self, session_id: str, url: str, wait_for: str = "load") -> Dict[str, Any]:
        """Navigate to a URL"""
        if not self.initialized:
            await self.initialize()
            
        if self.using_local:
            result = await self.local_backend.navigate(session_id, url, wait_for)
            result["backend"] = "local_playwright"
            return result
        else:
            # AgentCore implementation would go here
            result = await self.agentcore_client.navigate(session_id, url, wait_for)
            result["backend"] = "aws_agentcore"
            return result
            
    async def extract_content(self, session_id: str, content_type: str = "text") -> Dict[str, Any]:
        """Extract content from the current page"""
        if not self.initialized:
            await self.initialize()
            
        if self.using_local:
            result = await self.local_backend.extract_content(session_id, content_type)
            result["backend"] = "local_playwright"
            return result
        else:
            # AgentCore implementation would go here
            result = await self.agentcore_client.extract_content(session_id, content_type)
            result["backend"] = "aws_agentcore"
            return result
            
    async def take_screenshot(self, session_id: str, full_page: bool = True) -> Dict[str, Any]:
        """Take a screenshot of the current page"""
        if not self.initialized:
            await self.initialize()
            
        if self.using_local:
            result = await self.local_backend.take_screenshot(session_id, full_page)
            result["backend"] = "local_playwright"
            return result
        else:
            # AgentCore implementation would go here
            result = await self.agentcore_client.take_screenshot(session_id, full_page)
            result["backend"] = "aws_agentcore"
            return result
            
    async def close_session(self, session_id: str) -> Dict[str, Any]:
        """Close a browser session"""
        if not self.initialized:
            await self.initialize()
            
        if self.using_local:
            result = await self.local_backend.close_session(session_id)
            result["backend"] = "local_playwright"
            return result
        else:
            # AgentCore implementation would go here
            result = await self.agentcore_client.close_session(session_id)
            result["backend"] = "aws_agentcore"
            return result
            
    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get information about a session"""
        if not self.initialized:
            await self.initialize()
            
        if self.using_local:
            result = await self.local_backend.get_session_info(session_id)
            result["backend"] = "local_playwright"
            return result
        else:
            # AgentCore implementation would go here
            result = await self.agentcore_client.get_session_info(session_id)
            result["backend"] = "aws_agentcore"
            return result
            
    def list_sessions(self) -> Dict[str, Any]:
        """List all active sessions"""
        if not self.initialized:
            return {
                "success": False,
                "error": "Client not initialized",
                "timestamp": datetime.now().isoformat()
            }
            
        if self.using_local:
            result = self.local_backend.list_sessions()
            result["backend"] = "local_playwright"
            return result
        else:
            # AgentCore implementation would go here
            result = self.agentcore_client.list_sessions()
            result["backend"] = "aws_agentcore"
            return result
            
    def get_backend_info(self) -> Dict[str, Any]:
        """Get information about the current backend"""
        return {
            "backend": "local_playwright" if self.using_local else "aws_agentcore",
            "initialized": self.initialized,
            "test_mode": self.config.agentcore_endpoints.test_mode,
            "timestamp": datetime.now().isoformat()
        }