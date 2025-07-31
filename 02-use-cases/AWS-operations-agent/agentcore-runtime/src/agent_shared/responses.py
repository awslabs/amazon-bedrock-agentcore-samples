# ============================================================================
# IMPORTS
# ============================================================================

import json
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# DIY RESPONSE FORMATTING
# ============================================================================

def format_diy_response(event):
    """
    Format event for DIY agent streaming (Server-Sent Events) with enhanced text processing.
    
    Args:
        event: Strands streaming event
    
    Returns:
        str: Formatted SSE string with proper newline handling
    """
    try:
        # Extract structured content from event
        content_data = extract_content_from_event(event)
        
        # Create enhanced SSE payload
        if content_data['has_text']:
            # Text content - use structured format
            sse_payload = {
                'content': content_data['content'],
                'type': 'text_delta',
                'metadata': {
                    'event_type': content_data['event_type'],
                    'has_formatting': '\n' in content_data['content']
                }
            }
            logger.debug(f"📤 Formatted text content: {len(content_data['content'])} chars")
        else:
            # Non-text event - use legacy format for compatibility
            sse_payload = {
                'event': content_data['raw_event'],
                'type': 'event',
                'metadata': {
                    'event_type': content_data['event_type']
                }
            }
            logger.debug(f"📤 Formatted non-text event: {content_data['event_type']}")
        
        # Format as Server-Sent Events with proper JSON encoding
        sse_data = json.dumps(sse_payload, ensure_ascii=False)
        formatted = f"data: {sse_data}\n\n"
        
        return formatted
        
    except Exception as e:
        logger.error(f"❌ Failed to format DIY response: {e}")
        logger.error(f"❌ Event details: {type(event).__name__}")
        logger.error(f"❌ Event content: {str(event)[:200]}...")
        # Re-raise the exception to expose the real issue
        raise

# ============================================================================
# SDK RESPONSE FORMATTING
# ============================================================================

def format_sdk_response(event):
    """
    Format event for SDK agent streaming (direct streaming).
    
    Args:
        event: Strands streaming event
    
    Returns:
        Any: Event as-is for direct streaming
    """
    try:
        # For SDK agent, return event directly
        # BedrockAgentCoreApp handles the formatting
        return event
        
    except Exception as e:
        logger.error(f"❌ Failed to format SDK response: {e}")
        # Return error string
        return f"Error: {str(e)}"

# ============================================================================
# ENHANCED TEXT PROCESSING
# ============================================================================

def process_text_formatting(text: str) -> str:
    """
    Process text to handle newlines and formatting properly for display.
    
    Args:
        text (str): Raw text that may contain literal \n characters
    
    Returns:
        str: Text with proper newlines for display
    """
    if not text:
        return text
    
    try:
        # Convert literal \n strings to actual newlines
        # Handle both single and double backslash cases
        processed_text = text.replace('\\n', '\n')
        
        # Handle other common escape sequences that might appear
        processed_text = processed_text.replace('\\t', '\t')
        processed_text = processed_text.replace('\\r', '\r')
        
        # Clean up any excessive whitespace while preserving intentional formatting
        # Don't strip all whitespace as it might be intentional formatting
        
        logger.debug(f"📝 Text processing: {len(text)} chars → {len(processed_text)} chars")
        if '\\n' in text:
            logger.debug(f"🔄 Converted literal newlines in text: {text[:50]}...")
        
        return processed_text
        
    except Exception as e:
        logger.error(f"❌ Failed to process text formatting: {e}")
        logger.error(f"❌ Input text: {repr(text)}")
        # Re-raise to expose the real issue
        raise

def extract_content_from_event(event) -> dict:
    """
    Extract structured content from a Strands streaming event.
    
    Args:
        event: Strands streaming event
    
    Returns:
        dict: Structured content with metadata
    """
    try:
        content_data = {
            'content': '',
            'event_type': type(event).__name__,
            'has_text': False,
            'raw_event': str(event)[:200] + '...' if len(str(event)) > 200 else str(event)
        }
        
        # Try to extract text from delta attribute
        if hasattr(event, 'delta') and hasattr(event.delta, 'text'):
            raw_text = event.delta.text or ""
            if raw_text:
                content_data['content'] = process_text_formatting(raw_text)
                content_data['has_text'] = True
                logger.debug(f"📤 Extracted text from delta: {raw_text[:30]}...")
                return content_data
        
        # Try to extract from string representation as fallback
        event_str = str(event)
        if 'contentBlockDelta' in event_str and "'text':" in event_str:
            import re
            # More robust regex pattern to handle various formats
            patterns = [
                r"delta=\{[^}]*'text':\s*'([^']*)'[^}]*\}",
                r'"text":\s*"([^"]*)"',
                r"'text':\s*'([^']*)'",
            ]
            
            for pattern in patterns:
                delta_match = re.search(pattern, event_str)
                if delta_match:
                    raw_text = delta_match.group(1)
                    content_data['content'] = process_text_formatting(raw_text)
                    content_data['has_text'] = True
                    logger.debug(f"📤 Extracted text from string: {raw_text[:30]}...")
                    return content_data
        
        # No text content found
        logger.debug(f"📭 No text content in event: {content_data['event_type']}")
        return content_data
        
    except Exception as e:
        logger.error(f"❌ Failed to extract content from event: {e}")
        logger.error(f"❌ Event type: {type(event).__name__}")
        logger.error(f"❌ Event details: {str(event)[:200]}...")
        # Re-raise to expose the real issue
        raise

# ============================================================================
# UTILITIES (ENHANCED)
# ============================================================================

def extract_text_from_event(event):
    """
    Extract text content from a Strands streaming event.
    Enhanced version that uses the new content extraction.
    
    Args:
        event: Strands streaming event
    
    Returns:
        str: Extracted and formatted text or empty string
    """
    try:
        content_data = extract_content_from_event(event)
        return content_data.get('content', '')
        
    except Exception as e:
        logger.error(f"❌ Failed to extract text from event: {e}")
        logger.error(f"❌ Event type: {type(event).__name__}")
        # Re-raise to expose the real issue
        raise

def format_error_response(error_message, agent_type="diy"):
    """
    Format error response for streaming.
    
    Args:
        error_message (str): Error message
        agent_type (str): "diy" or "sdk"
    
    Returns:
        str: Formatted error response
    """
    try:
        if agent_type == "diy":
            # Format as SSE for DIY agent
            error_data = json.dumps({'error': error_message, 'type': 'error'})
            return f"data: {error_data}\n\n"
        else:
            # Format as plain text for SDK agent
            return f"Error: {error_message}"
            
    except Exception as e:
        logger.error(f"❌ Failed to format error response: {e}")
        return f"Error: {error_message}"