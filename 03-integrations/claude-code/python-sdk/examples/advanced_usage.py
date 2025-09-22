"""
Advanced Usage Examples for Claude Code Python SDK on AgentCore

This file demonstrates advanced patterns including:
- Continuous conversations with ClaudeSDKClient
- Custom MCP tools
- Hooks for control and monitoring
- Multi-turn workflows
"""

import asyncio
from typing import Any, Dict
from claude_code_sdk import (
    ClaudeSDKClient,
    ClaudeCodeOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    tool,
    create_sdk_mcp_server,
    HookMatcher,
    HookContext
)


async def continuous_conversation_example():
    """
    Example 1: Continuous conversation with context
    Maintains conversation context across multiple exchanges.
    """
    print("=" * 50)
    print("Example 1: Continuous Conversation")
    print("=" * 50)
    
    options = ClaudeCodeOptions(
        allowed_tools=["Read", "Write", "Edit"],
        permission_mode="acceptEdits"
    )
    
    async with ClaudeSDKClient(options) as client:
        # Step 1: Create initial project structure
        print("\nStep 1: Creating project structure...")
        await client.query("Create a Python package structure for a library called 'datautils'")
        
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                print("✓ Project structure created")
        
        # Step 2: Add functionality (Claude remembers the context)
        print("\nStep 2: Adding core functionality...")
        await client.query("Add a module for CSV processing with functions to read, write, and validate CSV files")
        
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                print("✓ CSV module added")
        
        # Step 3: Add tests (still remembers everything)
        print("\nStep 3: Creating tests...")
        await client.query("Create comprehensive unit tests for the CSV module using pytest")
        
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                print("✓ Tests created")
        
        # Step 4: Documentation
        print("\nStep 4: Generating documentation...")
        await client.query("Add docstrings to all functions and create a README with usage examples")
        
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                print("✓ Documentation complete")
                print("\nProject 'datautils' successfully created with full context maintained!")


async def custom_tools_example():
    """
    Example 2: Using custom MCP tools
    Create and use custom tools for specialized functionality.
    """
    print("\n" + "=" * 50)
    print("Example 2: Custom MCP Tools")
    print("=" * 50)
    
    # Define custom tools
    @tool("get_weather", "Get current weather for a city", {"city": str})
    async def get_weather(args: Dict[str, Any]) -> Dict[str, Any]:
        """Mock weather tool for demonstration."""
        city = args["city"]
        # In real implementation, this would call a weather API
        weather_data = {
            "New York": "Partly cloudy, 72°F",
            "London": "Rainy, 59°F",
            "Tokyo": "Sunny, 78°F"
        }
        return {
            "content": [{
                "type": "text",
                "text": f"Weather in {city}: {weather_data.get(city, 'Unknown location')}"
            }]
        }
    
    @tool("calculate_stats", "Calculate statistics for numbers", {"numbers": list})
    async def calculate_stats(args: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate basic statistics."""
        numbers = args["numbers"]
        if not numbers:
            return {"content": [{"type": "text", "text": "No numbers provided"}]}
        
        avg = sum(numbers) / len(numbers)
        return {
            "content": [{
                "type": "text",
                "text": f"Statistics: Count={len(numbers)}, Sum={sum(numbers)}, Average={avg:.2f}"
            }]
        }
    
    # Create MCP server with custom tools
    custom_server = create_sdk_mcp_server(
        name="custom_tools",
        version="1.0.0",
        tools=[get_weather, calculate_stats]
    )
    
    # Configure options with custom tools
    options = ClaudeCodeOptions(
        mcp_servers={"custom": custom_server},
        allowed_tools=[
            "mcp__custom__get_weather",
            "mcp__custom__calculate_stats",
            "Write"
        ],
        permission_mode="acceptEdits"
    )
    
    # Use custom tools in a task
    async with ClaudeSDKClient(options) as client:
        await client.query("""
        1. Get the weather for New York, London, and Tokyo
        2. Calculate statistics for the numbers [10, 20, 30, 40, 50]
        3. Create a report.txt file with all this information
        """)
        
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        print(f"Using custom tool: {block.name}")
        
        print("✓ Custom tools executed successfully")


async def hooks_example():
    """
    Example 3: Using hooks for monitoring and control
    Implement hooks to monitor, log, and control tool usage.
    """
    print("\n" + "=" * 50)
    print("Example 3: Hooks for Control and Monitoring")
    print("=" * 50)
    
    # Track tool usage
    tool_usage = {"count": 0, "tools": []}
    
    async def monitor_tools(
        input_data: Dict[str, Any],
        tool_use_id: str | None,
        context: HookContext
    ) -> Dict[str, Any]:
        """Monitor all tool usage."""
        tool_name = input_data.get('tool_name', 'unknown')
        tool_usage["count"] += 1
        tool_usage["tools"].append(tool_name)
        print(f"  [MONITOR] Tool #{tool_usage['count']}: {tool_name}")
        return {}
    
    async def validate_file_writes(
        input_data: Dict[str, Any],
        tool_use_id: str | None,
        context: HookContext
    ) -> Dict[str, Any]:
        """Validate and potentially block dangerous file operations."""
        tool_name = input_data.get('tool_name')
        
        if tool_name == 'Write':
            file_path = input_data.get('tool_input', {}).get('file_path', '')
            
            # Block writes to sensitive directories
            if file_path.startswith('/etc/') or file_path.startswith('/sys/'):
                print(f"  [BLOCKED] Attempted write to sensitive location: {file_path}")
                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PreToolUse',
                        'permissionDecision': 'deny',
                        'permissionDecisionReason': 'Write to sensitive directory blocked'
                    }
                }
            
            # Redirect temp files to safe location
            if file_path.startswith('/tmp/'):
                safe_path = f"./safe_temp/{file_path[5:]}"
                print(f"  [REDIRECT] {file_path} -> {safe_path}")
                return {
                    'hookSpecificOutput': {
                        'hookEventName': 'PreToolUse',
                        'permissionDecision': 'allow',
                        'updatedInput': {
                            **input_data.get('tool_input', {}),
                            'file_path': safe_path
                        }
                    }
                }
        
        return {}
    
    # Configure options with hooks
    options = ClaudeCodeOptions(
        hooks={
            'PreToolUse': [
                HookMatcher(hooks=[monitor_tools, validate_file_writes])
            ],
            'PostToolUse': [
                HookMatcher(hooks=[monitor_tools])
            ]
        },
        allowed_tools=["Write", "Read"],
        permission_mode="acceptEdits"
    )
    
    # Execute task with hooks
    async with ClaudeSDKClient(options) as client:
        await client.query("""
        Create three files:
        1. ./safe_file.txt with some content
        2. /tmp/temp_file.txt with temporary data
        3. ./config.json with configuration settings
        """)
        
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                print(f"\n✓ Task completed")
                print(f"  Total tools used: {tool_usage['count']}")
                print(f"  Tools: {', '.join(set(tool_usage['tools']))}")


async def streaming_input_example():
    """
    Example 4: Streaming input to Claude
    Send messages dynamically as they become available.
    """
    print("\n" + "=" * 50)
    print("Example 4: Streaming Input")
    print("=" * 50)
    
    async def generate_data_stream():
        """Simulate streaming data from an external source."""
        yield {"type": "text", "text": "Analyze this streaming data:\n"}
        
        # Simulate data arriving over time
        for i in range(1, 6):
            await asyncio.sleep(0.5)  # Simulate delay
            yield {"type": "text", "text": f"Data point {i}: Temperature={70+i}°F, Humidity={50+i*2}%\n"}
        
        yield {"type": "text", "text": "\nCreate a summary report of this data."}
    
    options = ClaudeCodeOptions(
        allowed_tools=["Write"],
        permission_mode="acceptEdits"
    )
    
    async with ClaudeSDKClient(options) as client:
        print("Streaming data to Claude...")
        
        # Stream input
        await client.query(generate_data_stream())
        
        # Get response
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                print("✓ Streaming analysis complete")


async def interrupt_example():
    """
    Example 5: Interrupting long-running tasks
    Demonstrate how to interrupt Claude during execution.
    """
    print("\n" + "=" * 50)
    print("Example 5: Task Interruption")
    print("=" * 50)
    
    options = ClaudeCodeOptions(
        allowed_tools=["Write", "Bash"],
        permission_mode="acceptEdits"
    )
    
    async with ClaudeSDKClient(options) as client:
        # Start a long-running task
        print("Starting long task...")
        await client.query("""
        Create 20 files named file1.txt through file20.txt,
        each containing a unique story. Take your time with each one.
        """)
        
        # Let it run for a bit
        await asyncio.sleep(2)
        
        # Interrupt the task
        print("Interrupting task...")
        await client.interrupt()
        
        # Send a new, simpler task
        print("Sending new task...")
        await client.query("Just create one file called summary.txt with 'Task interrupted' as content")
        
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                print("✓ New task completed after interruption")


async def nyc_running_clubs_deployment():
    """
    Example 6: Complete NYC Running Clubs Website Deployment
    Full workflow from research to deployment.
    """
    print("\n" + "=" * 50)
    print("Example 6: NYC Running Clubs Website Deployment")
    print("=" * 50)
    
    options = ClaudeCodeOptions(
        allowed_tools=["WebFetch", "Write", "Bash", "Read"],
        permission_mode="acceptEdits",
        append_system_prompt="""
        Create a professional, mobile-responsive website.
        Use modern HTML5, CSS3 with flexbox/grid, and vanilla JavaScript.
        Include proper SEO meta tags and accessibility features.
        For deployment simulation, create deployment scripts instead of actual AWS deployment.
        """
    )
    
    async with ClaudeSDKClient(options) as client:
        # Step 1: Research
        print("\nStep 1: Researching NYC running clubs...")
        await client.query("Research popular running clubs in New York City and gather information about their schedules, meeting locations, and contact details")
        
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                print("✓ Research complete")
        
        # Step 2: Create website
        print("\nStep 2: Creating website...")
        await client.query("Create a beautiful, responsive website displaying the NYC running clubs with filtering, search, and map integration")
        
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                print("✓ Website created")
        
        # Step 3: Optimize
        print("\nStep 3: Optimizing for production...")
        await client.query("Optimize the website for production: minify CSS/JS, optimize images, add caching headers configuration")
        
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                print("✓ Optimization complete")
        
        # Step 4: Create deployment scripts
        print("\nStep 4: Creating deployment scripts...")
        await client.query("""
        Create deployment scripts that would:
        1. Deploy the website to an S3 bucket
        2. Configure CloudFront distribution
        3. Set up proper caching and compression
        Include a deploy.sh script and AWS configuration files
        """)
        
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                print("✓ Deployment scripts created")
                print("\nNYC Running Clubs website ready for deployment!")


async def main():
    """Run all advanced examples."""
    print("Claude Code SDK Advanced Usage Examples")
    print("========================================\n")
    
    # Run examples
    await continuous_conversation_example()
    await custom_tools_example()
    await hooks_example()
    await streaming_input_example()
    await interrupt_example()
    await nyc_running_clubs_deployment()
    
    print("\n" + "=" * 50)
    print("All advanced examples completed!")
    print("=" * 50)


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())
