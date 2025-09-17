#!/usr/bin/env python3
"""
Local Browser Backend - Playwright implementation for AgentCore Browser Tool fallback
"""

import asyncio
import json
import base64
from typing import Dict, Any, Optional, List
from playwright.async_api import async_playwright, Browser, Page
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class LocalBrowserBackend:
    """Local browser automation backend using Playwright"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.pages: Dict[str, Page] = {}
        self.playwright = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop()
        
    async def start(self):
        """Start the browser backend"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            logger.info("Local browser backend started successfully")
        except Exception as e:
            logger.error(f"Failed to start browser backend: {e}")
            raise
            
    async def stop(self):
        """Stop the browser backend"""
        try:
            # Close all pages
            for page in self.pages.values():
                await page.close()
            self.pages.clear()
            
            # Close browser
            if self.browser:
                await self.browser.close()
                
            # Stop playwright
            if self.playwright:
                await self.playwright.stop()
                
            logger.info("Local browser backend stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping browser backend: {e}")
            
    async def create_session(self, session_id: str) -> Dict[str, Any]:
        """Create a new browser session"""
        try:
            if session_id in self.pages:
                await self.pages[session_id].close()
                
            page = await self.browser.new_page()
            self.pages[session_id] = page
            
            return {
                "success": True,
                "session_id": session_id,
                "message": "Session created successfully",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to create session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
    async def navigate(self, session_id: str, url: str, wait_for: str = "load") -> Dict[str, Any]:
        """Navigate to a URL"""
        try:
            if session_id not in self.pages:
                return {
                    "success": False,
                    "error": f"Session {session_id} not found",
                    "timestamp": datetime.now().isoformat()
                }
                
            page = self.pages[session_id]
            
            # Navigate to URL
            await page.goto(url, wait_until=wait_for)
            
            # Get page info
            title = await page.title()
            current_url = page.url
            
            return {
                "success": True,
                "url": current_url,
                "title": title,
                "message": f"Successfully navigated to {url}",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Navigation failed for session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
    async def extract_content(self, session_id: str, content_type: str = "text") -> Dict[str, Any]:
        """Extract content from the current page"""
        try:
            if session_id not in self.pages:
                return {
                    "success": False,
                    "error": f"Session {session_id} not found",
                    "timestamp": datetime.now().isoformat()
                }
                
            page = self.pages[session_id]
            
            result = {
                "success": True,
                "url": page.url,
                "title": await page.title(),
                "timestamp": datetime.now().isoformat()
            }
            
            if content_type == "text":
                # Extract text content
                text_content = await page.evaluate("""
                    () => {
                        // Remove script and style elements
                        const scripts = document.querySelectorAll('script, style');
                        scripts.forEach(el => el.remove());
                        
                        // Get clean text content
                        return document.body.innerText || document.body.textContent || '';
                    }
                """)
                result["content"] = text_content.strip()
                result["content_length"] = len(text_content)
                
            elif content_type == "html":
                # Extract HTML content
                html_content = await page.content()
                result["content"] = html_content
                result["content_length"] = len(html_content)
                
            elif content_type == "structured":
                # Extract structured data
                structured_data = await page.evaluate("""
                    () => {
                        const data = {
                            headings: [],
                            links: [],
                            images: [],
                            paragraphs: []
                        };
                        
                        // Extract headings
                        document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(h => {
                            data.headings.push({
                                level: h.tagName.toLowerCase(),
                                text: h.textContent.trim()
                            });
                        });
                        
                        // Extract links
                        document.querySelectorAll('a[href]').forEach(a => {
                            data.links.push({
                                text: a.textContent.trim(),
                                href: a.href
                            });
                        });
                        
                        // Extract images
                        document.querySelectorAll('img[src]').forEach(img => {
                            data.images.push({
                                alt: img.alt || '',
                                src: img.src
                            });
                        });
                        
                        // Extract paragraphs
                        document.querySelectorAll('p').forEach(p => {
                            const text = p.textContent.trim();
                            if (text) {
                                data.paragraphs.push(text);
                            }
                        });
                        
                        return data;
                    }
                """)
                result["content"] = structured_data
                
            return result
            
        except Exception as e:
            logger.error(f"Content extraction failed for session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
    async def take_screenshot(self, session_id: str, full_page: bool = True) -> Dict[str, Any]:
        """Take a screenshot of the current page"""
        try:
            if session_id not in self.pages:
                return {
                    "success": False,
                    "error": f"Session {session_id} not found",
                    "timestamp": datetime.now().isoformat()
                }
                
            page = self.pages[session_id]
            
            # Take screenshot
            screenshot_bytes = await page.screenshot(full_page=full_page)
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            return {
                "success": True,
                "screenshot": screenshot_base64,
                "screenshot_size": len(screenshot_bytes),
                "url": page.url,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Screenshot failed for session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
    async def close_session(self, session_id: str) -> Dict[str, Any]:
        """Close a browser session"""
        try:
            if session_id in self.pages:
                await self.pages[session_id].close()
                del self.pages[session_id]
                
            return {
                "success": True,
                "message": f"Session {session_id} closed successfully",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to close session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get information about a session"""
        try:
            if session_id not in self.pages:
                return {
                    "success": False,
                    "error": f"Session {session_id} not found",
                    "timestamp": datetime.now().isoformat()
                }
                
            page = self.pages[session_id]
            
            return {
                "success": True,
                "session_id": session_id,
                "url": page.url,
                "title": await page.title(),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get session info for {session_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
    def list_sessions(self) -> Dict[str, Any]:
        """List all active sessions"""
        return {
            "success": True,
            "sessions": list(self.pages.keys()),
            "session_count": len(self.pages),
            "timestamp": datetime.now().isoformat()
        }