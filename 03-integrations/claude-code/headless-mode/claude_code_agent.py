"""
Claude Code Agent for Amazon Bedrock AgentCore

This agent runs Claude Code in headless mode to autonomously handle coding tasks.
It accepts natural language prompts and executes them using Claude Code's CLI.
Configured to use Amazon Bedrock for model inference.
"""

import os
import json
import subprocess
import logging
from typing import Dict, Any, Optional
# Configure Claude Code to use Amazon Bedrock
os.environ["CLAUDE_CODE_USE_BEDROCK"] = "1"
os.environ["AWS_REGION"] = os.environ.get("AWS_REGION", "us-east-1")
os.environ["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "4096"
os.environ["MAX_THINKING_TOKENS"] = "1024"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_claude_code(
    prompt: str,
    output_format: str = "json",
    allowed_tools: Optional[str] = None,
    permission_mode: str = "acceptEdits",
    append_system_prompt: Optional[str] = None,
    session_id: Optional[str] = None,
    continue_conversation: bool = False
) -> Dict[str, Any]:
    """
    Execute Claude Code in headless mode
    
    Args:
        prompt: The task prompt for Claude Code
        output_format: Output format (json, text, stream-json)
        allowed_tools: Comma-separated list of allowed tools
        permission_mode: Permission handling mode
        append_system_prompt: Additional system instructions
        session_id: Session ID for resuming conversations
        continue_conversation: Whether to continue the most recent conversation
    
    Returns:
        Dictionary containing the execution result
    """
    
    # Build command
    cmd = ["claude", "-p", prompt]
    
    # Add output format
    cmd.extend(["--output-format", output_format])
    
    # Add permission mode
    cmd.extend(["--permission-mode", permission_mode])
    
    # Add allowed tools if specified
    if allowed_tools:
        cmd.extend(["--allowedTools", allowed_tools])
    
    # Add system prompt if provided
    if append_system_prompt:
        cmd.extend(["--append-system-prompt", append_system_prompt])
    
    # Handle conversation continuation
    if session_id:
        cmd.extend(["--resume", session_id])
    elif continue_conversation:
        cmd.append("--continue")
    
    # Add verbose flag for debugging
    if os.environ.get("CLAUDE_CODE_VERBOSE", "false").lower() == "true":
        cmd.append("--verbose")
    
    logger.info(f"Executing Claude Code with command: {' '.join(cmd[:3])}...")
    
    try:
        # Run Claude Code
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("CLAUDE_CODE_TIMEOUT", "600"))  # 10 min default
        )
        
        # Parse output based on format
        if output_format == "json":
            try:
                output = json.loads(result.stdout)
                return {
                    "success": not output.get("is_error", False),
                    "result": output.get("result", ""),
                    "session_id": output.get("session_id"),
                    "total_cost_usd": output.get("total_cost_usd", 0),
                    "duration_ms": output.get("duration_ms", 0),
                    "num_turns": output.get("num_turns", 0),
                    "raw_output": output
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON output: {e}")
                return {
                    "success": False,
                    "error": f"JSON parse error: {str(e)}",
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
        else:
            # For text or stream-json format
            return {
                "success": result.returncode == 0,
                "result": result.stdout,
                "stderr": result.stderr if result.stderr else None
            }
            
    except subprocess.TimeoutExpired:
        logger.error("Claude Code execution timed out")
        return {
            "success": False,
            "error": "Execution timed out"
        }
    except Exception as e:
        logger.error(f"Error executing Claude Code: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main handler for Claude Code agent invocation
    
    Args:
        event: AWS Lambda/AgentCore event containing the payload
        context: Lambda/AgentCore context
        
    Returns:
        Dictionary containing execution results
    """
    
    # Extract payload from event
    payload = event
    if isinstance(event, dict) and 'body' in event:
        # If event has a body field, parse it
        if isinstance(event['body'], str):
            try:
                payload = json.loads(event['body'])
            except json.JSONDecodeError:
                payload = event
        else:
            payload = event['body']
    
    # Extract parameters from payload
    prompt = payload.get("prompt")
    if not prompt:
        return {
            "success": False,
            "error": "No prompt provided. Please include a 'prompt' field in your payload."
        }
    
    # Get optional parameters with defaults
    session_id = payload.get("session_id")
    continue_conversation = payload.get("continue", False)
    output_format = payload.get("output_format", "json")
    permission_mode = payload.get("permission_mode", "acceptEdits")
    append_system_prompt = payload.get("append_system_prompt")
    
    # Default allowed tools for autonomous operation
    default_tools = "Bash,Read,Write,Replace,Search,List,WebFetch,AskFollowup"
    allowed_tools = payload.get("allowed_tools", default_tools)
    
    # Add AWS-specific context if needed
    if "aws" in prompt.lower() or "s3" in prompt.lower() or "cloudfront" in prompt.lower():
        aws_context = """
        You have AWS CLI configured and boto3 available.
        When deploying to AWS services:
        - Use boto3 for programmatic access
        - Ensure proper error handling
        - Set appropriate permissions and policies
        - Return resource URLs/ARNs in the final output
        """
        if append_system_prompt:
            append_system_prompt = f"{append_system_prompt}\n\n{aws_context}"
        else:
            append_system_prompt = aws_context
    
    logger.info(f"Processing prompt: {prompt[:100]}...")
    
    # Execute Claude Code
    result = run_claude_code(
        prompt=prompt,
        output_format=output_format,
        allowed_tools=allowed_tools,
        permission_mode=permission_mode,
        append_system_prompt=append_system_prompt,
        session_id=session_id,
        continue_conversation=continue_conversation
    )
    
    # Log execution result
    if result.get("success"):
        logger.info("Claude Code execution completed successfully")
    else:
        logger.error(f"Claude Code execution failed: {result.get('error', 'Unknown error')}")
    
    # Return result
    return {
        "success": result.get("success", False),
        "result": result.get("result", ""),
        "session_id": result.get("session_id"),
        "metadata": {
            "cost_usd": result.get("total_cost_usd"),
            "duration_ms": result.get("duration_ms"),
            "num_turns": result.get("num_turns")
        },
        "error": result.get("error") if not result.get("success") else None
    }

# For local testing
if __name__ == "__main__":
    import sys
    
    # Test handler with a sample event
    test_event = {
        "prompt": sys.argv[1] if len(sys.argv) > 1 else "Create a hello world Python script"
    }
    
    result = handler(test_event, {})
    print(json.dumps(result, indent=2))
