"""
AWS Bedrock AgentCore Browser Tool with Strands Integration

This module demonstrates TRUE integration between AWS Bedrock AgentCore browser capabilities
and the Strands agent framework for intelligent web browsing and content analysis.

Author: AWS Labs Community
License: MIT-0
"""

import os
import asyncio
from typing import Literal
from strands import tool
from strands_tools.browser import AgentCoreBrowser


@tool
def browse_web(url: str, extract_mode: Literal["text", "html", "metadata"] = "text") -> str:
    """
    Browse a web page and extract content using FULL Bedrock AgentCore browser capabilities.
    
    This tool provides TRUE integration between Strands agents and AWS Bedrock AgentCore,
    using the full browser automation capabilities instead of simple HTTP requests.
    
    Args:
        url (str): The website URL to browse and extract content from
        extract_mode (str): Content extraction mode:
            - "text": Extract clean text content (default)
            - "html": Extract full HTML content
            - "metadata": Extract page metadata (title, status, etc.)
    
    Returns:
        str: Extracted content from the web page, or error message if failed
        
    Example:
        >>> content = browse_web("https://example.com", "text")
        >>> print(content[:100])
        Example Domain This domain is for use in illustrative examples...
    """
    try:
        # Validate extract_mode parameter
        valid_modes = ["text", "html", "metadata"]
        if extract_mode not in valid_modes:
            return f"Error: Invalid extract_mode '{extract_mode}'. Valid options: {valid_modes}"
        
        # Get AWS region configuration
        region = os.getenv('AWS_REGION', 'us-east-1')
        
        # Use synchronous browser automation (AgentCoreBrowser is synchronous)
        return _browse_with_agentcore_sync(url, extract_mode, region)
        
    except Exception as e:
        # Handle any errors
        if "credential" in str(e).lower() or "auth" in str(e).lower():
            error_msg = f"Error: AWS authentication failed: {str(e)}"
        elif "timeout" in str(e).lower():
            error_msg = f"Error: Request timeout for {url}: {str(e)}"
        elif "session" in str(e).lower():
            error_msg = f"Error: Bedrock AgentCore session failed: {str(e)}"
        else:
            error_msg = f"Error browsing {url}: {str(e)}"
        
        print(error_msg)
        return error_msg


def _browse_with_agentcore_sync(url: str, extract_mode: str, region: str) -> str:
    """
    Internal synchronous function that uses FULL Bedrock AgentCore browser capabilities.
    
    This function creates a real browser session through AWS Bedrock AgentCore,
    navigates to the URL, and extracts content using browser automation.
    """
    from strands_tools.browser.models import (
        BrowserInput, InitSessionAction, NavigateAction, 
        GetTextAction, GetHtmlAction, EvaluateAction, CloseAction
    )
    
    # Create Bedrock AgentCore browser instance
    browser = AgentCoreBrowser(region=region, session_timeout=1800)  # 30 minutes
    session_name = "browser-session-1"
    
    try:
        # Start the browser platform
        browser.start_platform()
        
        # Initialize a browser session (this creates AWS-hosted browser)
        init_action = InitSessionAction(
            type="init_session", 
            session_name=session_name,
            description="Browser session for web content extraction"
        )
        init_input = BrowserInput(action=init_action)
        init_result = browser.browser(init_input)
        
        if init_result.get('status') != 'success':
            return f"Error: Failed to initialize browser session: {init_result}"
        
        # Navigate to the URL using real browser
        nav_action = NavigateAction(type="navigate", session_name=session_name, url=url)
        nav_input = BrowserInput(action=nav_action)
        nav_result = browser.browser(nav_input)
        
        if nav_result.get('status') != 'success':
            return f"Error: Failed to navigate to {url}: {nav_result}"
        
        # Extract content based on mode using browser capabilities
        if extract_mode == "html":
            # Get full HTML content from the browser (no selector = full page)
            html_action = GetHtmlAction(type="get_html", session_name=session_name)
            html_input = BrowserInput(action=html_action)
            result_dict = browser.browser(html_input)
            
            if result_dict.get('status') == 'success':
                content = result_dict.get('content', [])
                if content and len(content) > 0:
                    result = content[0].get('text', '') if isinstance(content[0], dict) else str(content[0])
                else:
                    result = "No HTML content found"
            else:
                result = f"Error getting HTML: {result_dict}"
            
        elif extract_mode == "text":
            # Extract clean text content using browser's text extraction (body selector)
            text_action = GetTextAction(type="get_text", session_name=session_name, selector="body")
            text_input = BrowserInput(action=text_action)
            result_dict = browser.browser(text_input)
            
            if result_dict.get('status') == 'success':
                content = result_dict.get('content', [])
                if content and len(content) > 0:
                    text_content = content[0].get('text', '') if isinstance(content[0], dict) else str(content[0])
                    # Clean up extra whitespace
                    import re
                    result = re.sub(r'\s+', ' ', text_content.strip())
                else:
                    result = "No text content found"
            else:
                result = f"Error getting text: {result_dict}"
            
        elif extract_mode == "metadata":
            # Extract comprehensive metadata using browser capabilities
            eval_action = EvaluateAction(
                type="evaluate",
                session_name=session_name,
                script="""
                () => {
                    const meta = {
                        title: document.title || 'No title',
                        url: window.location.href,
                        content_length: document.documentElement.outerHTML.length,
                        bedrock_agentcore: true,
                        viewport: {
                            width: window.innerWidth,
                            height: window.innerHeight
                        }
                    };
                    
                    // Extract meta tags
                    const description = document.querySelector('meta[name="description"]');
                    if (description) meta.description = description.content;
                    
                    const keywords = document.querySelector('meta[name="keywords"]');
                    if (keywords) meta.keywords = keywords.content;
                    
                    const ogTitle = document.querySelector('meta[property="og:title"]');
                    if (ogTitle) meta.og_title = ogTitle.content;
                    
                    const ogDescription = document.querySelector('meta[property="og:description"]');
                    if (ogDescription) meta.og_description = ogDescription.content;
                    
                    return meta;
                }
                """
            )
            eval_input = BrowserInput(action=eval_action)
            result_dict = browser.browser(eval_input)
            
            if result_dict.get('status') == 'success':
                content = result_dict.get('content', [])
                if content and len(content) > 0:
                    # The evaluation result is in the 'text' field
                    eval_text = content[0].get('text', '') if isinstance(content[0], dict) else str(content[0])
                    # Extract the actual result from "Evaluation result: {result}"
                    if eval_text.startswith('Evaluation result: '):
                        result = eval_text[19:]  # Remove "Evaluation result: " prefix
                    else:
                        result = eval_text
                else:
                    result = "No metadata found"
            else:
                result = f"Error getting metadata: {result_dict}"
        
        # Close the session
        try:
            close_action = CloseAction(type="close", session_name=session_name)
            close_input = BrowserInput(action=close_action)
            browser.browser(close_input)
        except Exception as e:
            print(f"Warning: Failed to close session: {e}")
        
        return result
        
    finally:
        # Always clean up browser resources
        try:
            browser.close_platform()
        except Exception as cleanup_error:
            print(f"Warning: Browser cleanup error: {cleanup_error}")


def get_tool_info() -> dict:
    """
    Get information about the TRUE Bedrock AgentCore browser tool capabilities.
    
    Returns:
        dict: Tool information including supported modes and requirements
    """
    return {
        "name": "browse_web",
        "description": "Browse web pages using FULL AWS Bedrock AgentCore browser automation with Strands integration",
        "supported_modes": ["text", "html", "metadata"],
        "requirements": ["AWS Bedrock AgentCore access", "Strands agents", "Internet connectivity"],
        "browser_type": "AWS-hosted browser instance",
        "automation": "Full browser automation (not just HTTP requests)",
        "timeout": 30,
        "session_timeout": 1800,
        "capabilities": ["JavaScript execution", "Dynamic content loading", "Real browser rendering"],
    }


if __name__ == "__main__":
    # Basic functionality test
    print("🧪 Testing Bedrock Strands Browser Tool")
    print("=" * 50)
    
    # Test basic functionality
    test_url = "https://example.com"
    
    print(f"Testing URL: {test_url}")
    
    # Test text extraction
    print("\n📄 Testing text extraction...")
    text_result = browse_web(test_url, "text")
    if not text_result.startswith("Error"):
        print(f"✅ Success: {len(text_result)} characters extracted")
        print(f"Preview: {text_result[:100]}...")
    else:
        print(f"❌ Failed: {text_result}")
    
    # Test metadata extraction
    print("\n📊 Testing metadata extraction...")
    metadata_result = browse_web(test_url, "metadata")
    if not metadata_result.startswith("Error"):
        print(f"✅ Success: {metadata_result}")
    else:
        print(f"❌ Failed: {metadata_result}")
    
    print("\n🎉 Basic test completed!")