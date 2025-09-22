"""
Claude Code AgentCore Integration Wrapper

This wrapper integrates the official Claude Code Python SDK with Amazon Bedrock AgentCore,
allowing you to run Claude Code as an autonomous agent on AgentCore infrastructure.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, AsyncIterator
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Import Claude Code SDK components
from claude_code_sdk import (
    query,
    ClaudeSDKClient,
    ClaudeCodeOptions,
    Message,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    tool,
    create_sdk_mcp_server
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AgentCore app
app = BedrockAgentCoreApp()


async def execute_claude_code_query(
    prompt: str,
    options: Optional[ClaudeCodeOptions] = None
) -> Dict[str, Any]:
    """
    Execute a one-off Claude Code query.
    
    Args:
        prompt: The task prompt
        options: Optional Claude Code configuration
        
    Returns:
        Dictionary containing execution results
    """
    result_text = []
    session_id = None
    total_cost = 0.0
    duration_ms = 0
    num_turns = 0
    is_error = False
    tools_used = []
    
    try:
        # Execute query and collect results
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                # Collect assistant responses
                for block in message.content:
                    if isinstance(block, TextBlock):
                        result_text.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        tools_used.append({
                            "name": block.name,
                            "id": block.id
                        })
                        logger.info(f"Tool used: {block.name}")
                    elif isinstance(block, ToolResultBlock):
                        logger.debug(f"Tool result for {block.tool_use_id}")
                        
            elif isinstance(message, ResultMessage):
                # Extract final metadata
                session_id = message.session_id
                total_cost = message.total_cost_usd or 0.0
                duration_ms = message.duration_ms
                num_turns = message.num_turns
                is_error = message.is_error
                if message.result:
                    result_text.append(message.result)
        
        return {
            "success": not is_error,
            "result": "\n".join(result_text),
            "session_id": session_id,
            "metadata": {
                "cost_usd": total_cost,
                "duration_ms": duration_ms,
                "num_turns": num_turns,
                "tools_used": tools_used
            }
        }
        
    except Exception as e:
        logger.error(f"Error executing Claude Code: {e}")
        return {
            "success": False,
            "error": str(e),
            "result": ""
        }


async def execute_claude_code_session(
    prompts: list[str],
    options: Optional[ClaudeCodeOptions] = None
) -> Dict[str, Any]:
    """
    Execute multiple prompts in a continuous conversation session.
    
    Args:
        prompts: List of prompts to execute in sequence
        options: Optional Claude Code configuration
        
    Returns:
        Dictionary containing conversation results
    """
    results = []
    total_cost = 0.0
    total_duration = 0
    
    try:
        async with ClaudeSDKClient(options) as client:
            for i, prompt in enumerate(prompts):
                logger.info(f"Processing prompt {i+1}/{len(prompts)}")
                
                # Send prompt
                await client.query(prompt)
                
                # Collect response
                turn_result = []
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                turn_result.append(block.text)
                    elif isinstance(message, ResultMessage):
                        total_cost += message.total_cost_usd or 0.0
                        total_duration += message.duration_ms
                
                results.append({
                    "prompt": prompt,
                    "response": "\n".join(turn_result)
                })
        
        return {
            "success": True,
            "results": results,
            "metadata": {
                "total_cost_usd": total_cost,
                "total_duration_ms": total_duration,
                "num_prompts": len(prompts)
            }
        }
        
    except Exception as e:
        logger.error(f"Session error: {e}")
        return {
            "success": False,
            "error": str(e),
            "results": results
        }


@app.entrypoint
def claude_code_agentcore_handler(payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main handler for Claude Code agent invocation on AgentCore.
    
    Supports two modes:
    1. Single prompt execution (default)
    2. Multi-turn conversation (when prompts array is provided)
    
    Args:
        payload: Input payload containing:
            - prompt: Single prompt string (for one-off execution)
            - prompts: Array of prompts (for conversation session)
            - options: Optional configuration object with:
                - allowed_tools: List of allowed tool names
                - system_prompt: System prompt override
                - append_system_prompt: Additional system instructions
                - permission_mode: Permission handling mode
                - cwd: Working directory
                - max_turns: Maximum conversation turns
                - model: Claude model to use
        context: AgentCore context
        
    Returns:
        Dictionary containing execution results
    """
    
    # Build ClaudeCodeOptions from payload
    options_dict = payload.get("options", {})
    
    options = ClaudeCodeOptions(
        allowed_tools=options_dict.get("allowed_tools", []),
        system_prompt=options_dict.get("system_prompt"),
        append_system_prompt=options_dict.get("append_system_prompt"),
        permission_mode=options_dict.get("permission_mode", "acceptEdits"),
        cwd=options_dict.get("cwd"),
        max_turns=options_dict.get("max_turns"),
        model=options_dict.get("model"),
        continue_conversation=options_dict.get("continue_conversation", False),
        resume=options_dict.get("resume")
    )
    
    # Add AWS-specific context if needed
    if any(keyword in str(payload).lower() for keyword in ["aws", "s3", "cloudfront", "lambda"]):
        aws_context = """
        You have AWS CLI configured and boto3 available.
        When deploying to AWS services:
        - Use boto3 for programmatic access
        - Ensure proper error handling
        - Set appropriate permissions and policies
        - Return resource URLs/ARNs in the final output
        """
        if options.append_system_prompt:
            options.append_system_prompt = f"{options.append_system_prompt}\n\n{aws_context}"
        else:
            options.append_system_prompt = aws_context
    
    # Determine execution mode
    if "prompts" in payload:
        # Multi-turn conversation mode
        prompts = payload["prompts"]
        if not isinstance(prompts, list) or not prompts:
            return {
                "success": False,
                "error": "Invalid prompts array. Please provide a non-empty list of prompts."
            }
        
        logger.info(f"Starting conversation session with {len(prompts)} prompts")
        
        # Run async session
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                execute_claude_code_session(prompts, options)
            )
        finally:
            loop.close()
            
    else:
        # Single prompt mode
        prompt = payload.get("prompt")
        if not prompt:
            return {
                "success": False,
                "error": "No prompt provided. Please include a 'prompt' field in your payload."
            }
        
        logger.info(f"Processing single prompt: {prompt[:100]}...")
        
        # Run async query
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                execute_claude_code_query(prompt, options)
            )
        finally:
            loop.close()
    
    return result


# Custom tools for AgentCore-specific functionality
@tool("deploy_to_s3", "Deploy files to S3 bucket", {
    "bucket_name": str,
    "files": list,
    "make_public": bool
})
async def deploy_to_s3(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Custom tool for deploying files to S3.
    This would integrate with boto3 in a real implementation.
    """
    bucket_name = args["bucket_name"]
    files = args["files"]
    make_public = args.get("make_public", False)
    
    # This is a placeholder - in real implementation, use boto3
    return {
        "content": [{
            "type": "text",
            "text": f"Would deploy {len(files)} files to s3://{bucket_name}/ (public: {make_public})"
        }]
    }


@tool("setup_cloudfront", "Set up CloudFront distribution", {
    "origin_bucket": str,
    "price_class": str
})
async def setup_cloudfront(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Custom tool for setting up CloudFront.
    This would integrate with boto3 in a real implementation.
    """
    origin_bucket = args["origin_bucket"]
    price_class = args.get("price_class", "PriceClass_100")
    
    # This is a placeholder - in real implementation, use boto3
    return {
        "content": [{
            "type": "text",
            "text": f"Would create CloudFront distribution for {origin_bucket} with {price_class}"
        }]
    }


def create_aws_tools_server():
    """
    Create an MCP server with AWS-specific tools.
    
    Returns:
        MCP server configuration for AWS tools
    """
    return create_sdk_mcp_server(
        name="aws_tools",
        version="1.0.0",
        tools=[deploy_to_s3, setup_cloudfront]
    )


if __name__ == "__main__":
    # Run the AgentCore app
    app.run()
