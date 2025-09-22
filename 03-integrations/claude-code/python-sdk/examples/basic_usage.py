"""
Basic Usage Examples for Claude Code Python SDK on AgentCore

This file demonstrates basic usage patterns for the Claude Code SDK.
"""

import asyncio
from claude_code_sdk import query, ClaudeCodeOptions, AssistantMessage, TextBlock, ResultMessage


async def simple_query_example():
    """
    Example 1: Simple one-off query
    Creates a new session for a single task.
    """
    print("=" * 50)
    print("Example 1: Simple Query")
    print("=" * 50)
    
    options = ClaudeCodeOptions(
        allowed_tools=["Write"],
        permission_mode="acceptEdits"
    )
    
    async for message in query(
        prompt="Create a simple Python hello world script",
        options=options
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"Claude: {block.text}")
        elif isinstance(message, ResultMessage):
            print(f"\nTask completed!")
            print(f"Cost: ${message.total_cost_usd:.4f}" if message.total_cost_usd else "Cost: N/A")
            print(f"Duration: {message.duration_ms}ms")


async def file_operations_example():
    """
    Example 2: File operations
    Create, read, and modify files.
    """
    print("\n" + "=" * 50)
    print("Example 2: File Operations")
    print("=" * 50)
    
    options = ClaudeCodeOptions(
        allowed_tools=["Write", "Read", "Edit"],
        permission_mode="acceptEdits",
        cwd="./test_workspace"  # Set working directory
    )
    
    prompt = """
    1. Create a file called data.json with sample user data
    2. Create a Python script that reads and processes this data
    3. Add error handling to the script
    """
    
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            if message.is_error:
                print(f"Error: {message.result}")
            else:
                print(f"Files created successfully!")


async def web_scraping_example():
    """
    Example 3: Web scraping and data processing
    Fetch web content and process it.
    """
    print("\n" + "=" * 50)
    print("Example 3: Web Scraping")
    print("=" * 50)
    
    options = ClaudeCodeOptions(
        allowed_tools=["WebFetch", "Write", "Bash"],
        permission_mode="acceptEdits"
    )
    
    prompt = """
    Research Python web frameworks and create a comparison table
    in markdown format. Save it as frameworks_comparison.md
    """
    
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            # Monitor progress
            for block in message.content:
                if isinstance(block, TextBlock):
                    # Only show first 100 chars to avoid clutter
                    text = block.text[:100] + "..." if len(block.text) > 100 else block.text
                    print(f"Progress: {text}")


async def bash_automation_example():
    """
    Example 4: Bash automation
    Run shell commands and automate tasks.
    """
    print("\n" + "=" * 50)
    print("Example 4: Bash Automation")
    print("=" * 50)
    
    options = ClaudeCodeOptions(
        allowed_tools=["Bash", "Write"],
        permission_mode="acceptEdits"
    )
    
    prompt = """
    Create a bash script that:
    1. Creates a project directory structure
    2. Initializes a git repository
    3. Creates a README with project information
    Then execute the script.
    """
    
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            print(f"Automation completed in {message.num_turns} turns")


async def code_analysis_example():
    """
    Example 5: Code analysis and improvement
    Analyze existing code and suggest improvements.
    """
    print("\n" + "=" * 50)
    print("Example 5: Code Analysis")
    print("=" * 50)
    
    # First, create some sample code to analyze
    setup_options = ClaudeCodeOptions(
        allowed_tools=["Write"],
        permission_mode="acceptEdits"
    )
    
    setup_prompt = """
    Create a file called calculator.py with a basic calculator class
    that has some intentional issues (no error handling, poor structure)
    """
    
    print("Setting up sample code...")
    async for message in query(prompt=setup_prompt, options=setup_options):
        pass  # Just wait for completion
    
    # Now analyze and improve it
    analysis_options = ClaudeCodeOptions(
        allowed_tools=["Read", "Edit", "Write"],
        permission_mode="acceptEdits"
    )
    
    analysis_prompt = """
    Analyze calculator.py and:
    1. Identify issues and potential improvements
    2. Refactor the code with better structure
    3. Add comprehensive error handling
    4. Add docstrings and type hints
    5. Create unit tests in test_calculator.py
    """
    
    print("Analyzing and improving code...")
    async for message in query(prompt=analysis_prompt, options=analysis_options):
        if isinstance(message, ResultMessage):
            print(f"Analysis and refactoring complete!")
            print(f"Total cost: ${message.total_cost_usd:.4f}" if message.total_cost_usd else "")


async def main():
    """Run all examples."""
    print("Claude Code SDK Basic Usage Examples")
    print("=====================================\n")
    
    # Run examples
    await simple_query_example()
    await file_operations_example()
    await web_scraping_example()
    await bash_automation_example()
    await code_analysis_example()
    
    print("\n" + "=" * 50)
    print("All examples completed!")
    print("=" * 50)


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())
