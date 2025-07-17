from bedrock_agentcore.tools.browser_client import browser_session
from nova_act import NovaAct
from rich.console import Console
from rich.panel import Panel
import sys
import json
import argparse
sys.path.append("../interactive_tools")
from browser_viewer import BrowserViewerServer

console = Console()

from boto3.session import Session

boto_session = Session()
region = boto_session.region_name
print("using region", region)

def live_view_with_nova_act(prompt, starting_page, nova_act_key, region="us-west-2"):
    """Run the browser live viewer with display sizing."""
    console.print(
        Panel(
            "[bold cyan]Browser Live Viewer[/bold cyan]\n\n"
            "This demonstrates:\n"
            "• Live browser viewing with DCV\n"
            "• Configurable display sizes (not limited to 900×800)\n"
            "• Proper display layout callbacks\n\n"
            "[yellow]Note: Requires Amazon DCV SDK files[/yellow]",
            title="Browser Live Viewer",
            border_style="blue",
        )
    )

    try:
        # Step 1: Create browser session
        with browser_session(region) as client:
            ws_url, headers = client.generate_ws_headers()

            # Step 2: Start viewer server
            console.print("\n[cyan]Step 3: Starting viewer server...[/cyan]")
            viewer = BrowserViewerServer(client, port=8000)
            viewer_url = viewer.start(open_browser=True)

            # Step 3: Show features
            console.print("\n[bold green]Viewer Features:[/bold green]")
            console.print(
                "• Default display: 1600×900 (configured via displayLayout callback)"
            )
            console.print("• Size options: 720p, 900p, 1080p, 1440p")
            console.print("• Real-time display updates")
            console.print("• Take/Release control functionality")

            console.print("\n[yellow]Press Ctrl+C to stop[/yellow]")

            # Step 4: Use Nova Act to interact with the browser
            with NovaAct(
                cdp_endpoint_url=ws_url,
                cdp_headers=headers,
                preview={"playwright_actuation": True},
                nova_act_api_key=nova_act_key,
                starting_page=starting_page,
            ) as nova_act:
                result = nova_act.act(prompt)
                console.print(f"\n[bold green]Nova Act Result:[/bold green] {result}")
        
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
    finally:
        console.print("\n\n[yellow]Shutting down...[/yellow]")
        if "client" in locals():
            client.stop()
            console.print("✅ Browser session terminated")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, help="Browser Search instruction")
    parser.add_argument("--starting-page", required=True, help="Starting URL")
    parser.add_argument("--nova-act-key", required=True, help="Nova Act API key")
    parser.add_argument("--region", default="us-west-2", help="AWS region")
    args = parser.parse_args()

    result = live_view_with_nova_act(
        args.prompt, args.starting_page, args.nova_act_key, args.region
    )

    with open('result.txt', 'w') as f:
        f.write(str(result))

    console.print(f"\n[bold green]Nova Act Result:[/bold green] {result}")
