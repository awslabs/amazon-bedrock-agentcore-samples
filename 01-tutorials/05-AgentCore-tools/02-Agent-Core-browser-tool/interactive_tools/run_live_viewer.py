#!/usr/bin/env python3
"""
Standalone script to run the Bedrock-AgentCore Browser Live Viewer.
This shows how to use the interactive_tools modules.
"""


import time
from pathlib import Path


from rich.console import Console
from rich.panel import Panel
from bedrock_agentcore.tools.browser_client import BrowserClient
from .browser_viewer import BrowserViewerServer

console = Console()

def main():
    """Run the browser live viewer with display sizing."""
    console.print(Panel(
        "[bold cyan]Bedrock-AgentCore Browser Live Viewer[/bold cyan]\n\n"
        "This demonstrates:\n"
        "• Live browser viewing with DCV\n"
        "• Configurable display sizes (not limited to 900×800)\n"
        "• Proper display layout callbacks\n\n"
        "[yellow]Note: Requires Amazon DCV SDK files[/yellow]",
        title="Browser Live Viewer",
        border_style="blue"
    ))
    
    try:
        # Step 1: Create browser session
        console.print("\n[cyan]Step 1: Creating browser session...[/cyan]")
        browser_client = BrowserClient(region="us-west-2")
        session_id = browser_client.start()
        console.print(f"✅ Session created: {session_id}")
        
        # Step 2: Wait for browser initialization
        console.print("\n[cyan]Step 2: Waiting for browser initialization...[/cyan]")
        console.print("[dim]This 20-second wait is required (will be removed after 6/20)[/dim]")
        for i in range(2, 0, -1):
            print(f"\r   {i} seconds remaining...", end='', flush=True)
            time.sleep(1)
        print("\r   ✅ Browser ready!                    ")
        
        # Step 3: Start viewer server
        console.print("\n[cyan]Step 3: Starting viewer server...[/cyan]")
        viewer = BrowserViewerServer(browser_client, port=8000)
        viewer_url = viewer.start(open_browser=True)
        
        # Step 4: Show features
        console.print("\n[bold green]Viewer Features:[/bold green]")
        console.print("• Default display: 1600×900 (configured via displayLayout callback)")
        console.print("• Size options: 720p, 900p, 1080p, 1440p")
        console.print("• Real-time display updates")
        console.print("• Take/Release control functionality")
        
        console.print("\n[yellow]Press Ctrl+C to stop[/yellow]")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Shutting down...[/yellow]")
        if 'browser_client' in locals():
            browser_client.stop()
            console.print("✅ Browser session terminated")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
