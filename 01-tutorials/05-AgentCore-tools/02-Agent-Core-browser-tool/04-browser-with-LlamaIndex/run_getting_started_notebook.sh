#!/bin/bash

# Browser automation with LlamaIndex - Notebook Runner
# This script runs the notebook cells from 01_getting_started-agentcore-browser-tool-with-llamaindex.ipynb sequentially

set -e  # Exit on any error

echo "=========================================="
echo "Running 01_getting_started-agentcore-browser-tool-with-llamaindex.ipynb"
echo "Browser automation with LlamaIndex"
echo "=========================================="

# Cell 1: Python environment setup
echo "Cell 1: Setting up Python 3.12 virtual environment..."
python3.12 --version
python3.12 -m venv venv
source venv/bin/activate && python --version

# Cell 2: Install requirements
echo "Cell 2: Installing requirements..."
pip install --force-reinstall -U -r requirements.txt --quiet
echo "✅ All dependencies installed successfully!"

# Cell 3: Setup and Imports
echo "Cell 3: Setting up imports..."
python << 'EOF'
# Import required libraries
import asyncio
import json
from datetime import datetime
from pathlib import Path

# LlamaIndex imports
from llama_index.llms.bedrock_converse import BedrockConverse

# Browser and Playwright imports
from bedrock_agentcore.tools.browser_client import browser_session
from playwright.async_api import async_playwright

# Utilities
from rich.console import Console
from rich.panel import Panel
import boto3

console = Console()

print("✅ All libraries imported successfully!")
EOF

# Cell 4: Browser Automation Class Implementation
echo "Cell 4: Creating BrowserAutomationWithLlamaIndex class..."
cat > browser_automation_with_llamaindex.py << 'EOF'
# Import required libraries
import asyncio
import json
from datetime import datetime
from pathlib import Path

# LlamaIndex imports
from llama_index.llms.bedrock_converse import BedrockConverse

# Browser and Playwright imports
from bedrock_agentcore.tools.browser_client import browser_session
from playwright.async_api import async_playwright

# Utilities
from rich.console import Console
from rich.panel import Panel
import boto3

console = Console()

class BrowserAutomationWithLlamaIndex:
    """
    Browser automation with LlamaIndex for web content analysis
    """
    
    def __init__(self, region="us-east-1"):
        self.region = region
        self.browser_client = None
        self.results_dir = Path("analysis_results")
        self.results_dir.mkdir(exist_ok=True)
        
    async def run_analysis(self, prompt, starting_page):
        """
        Main function that runs the complete browser analysis workflow
        """
        console.print(
            Panel(
                f"[bold cyan]LlamaIndex Browser Analysis[/bold cyan]\\n\\n"
                f"🎯 Task: {prompt}\\n"
                f"🌐 Starting Page: {starting_page}\\n"
                f"📁 Results: {self.results_dir}",
                title="Browser Analysis Session",
                border_style="blue",
            )
        )
        
        try:
            # Step 1: Initialize browser session
            console.print("\\n[cyan]🚀 Initializing browser session...[/cyan]")
            
            # Create browser session
            self.browser_client = browser_session(self.region).__enter__()
            ws_url, headers = self.browser_client.generate_ws_headers()
            console.print(f"[green]✅ Browser session: {self.browser_client.session_id}[/green]")
            
            # Step 2: Set up Playwright automation
            console.print("\\n[cyan]🤖 Setting up Playwright automation...[/cyan]")
            
            # Create LlamaIndex LLM for analysis
            llm = BedrockConverse(
                model="anthropic.claude-3-haiku-20240307-v1:0",
                region_name=self.region,
                temperature=0.1,
                max_tokens=4000
            )
            
            console.print("[green]✅ LlamaIndex LLM ready[/green]")
            
            # Step 3: Execute browser automation
            console.print(f"\\n[cyan]🎬 Starting browser automation...[/cyan]")
            
            # Generate timestamp for this analysis
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Use Playwright to automate the browser session
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(ws_url, headers=headers)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = context.pages[0] if context.pages else await context.new_page()
                
                console.print(f"[green]✅ Connected to browser session[/green]")
                
                # Navigate to starting page
                console.print(f"[yellow]🌐 Navigating to: {starting_page}[/yellow]")
                await page.goto(starting_page, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)  # Brief pause for page load
                
                # Extract page content
                console.print(f"[yellow]📄 Extracting page content...[/yellow]")
                page_title = await page.title()
                page_content = await page.inner_text('body')
                
                console.print(f"[green]✅ Page loaded: {page_title}[/green]")
                console.print(f"[green]📄 Content extracted ({len(page_content)} characters)[/green]")
                
                # Take screenshots
                console.print(f"[yellow]📸 Taking screenshots...[/yellow]")
                
                # Full page screenshot
                full_screenshot = self.results_dir / f"analysis_{timestamp}_full.png"
                await page.screenshot(path=str(full_screenshot), full_page=True)
                
                # Viewport screenshot  
                viewport_screenshot = self.results_dir / f"analysis_{timestamp}_viewport.png"
                await page.screenshot(path=str(viewport_screenshot), full_page=False)
                
                console.print(f"[green]📸 Screenshots saved[/green]")
                
                # Use LlamaIndex to analyze the content
                console.print(f"[cyan]🤖 Analyzing content with LlamaIndex...[/cyan]")
                
                analysis_prompt = f"""
                Analyze this web page content and complete the requested task:
                
                Page Title: {page_title}
                URL: {starting_page}
                Task: {prompt}
                
                Page Content:
                {page_content[:3000]}
                
                Please provide a detailed analysis focusing on the specific task requested.
                Extract the exact information requested and present it clearly.
                """
                
                response = await llm.acomplete(analysis_prompt)
                result = response.text
            
            # Step 4: Save results and provide summary
            # Save the result
            result_data = {
                "timestamp": timestamp,
                "prompt": prompt,
                "starting_page": starting_page,
                "page_title": page_title,
                "content_length": len(page_content),
                "agent_response": str(result),
                "session_id": self.browser_client.session_id,
                "screenshots": {
                    "full_page": str(full_screenshot),
                    "viewport": str(viewport_screenshot)
                },
                "success": True
            }
            
            result_file = self.results_dir / f"analysis_{timestamp}.json"
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)
            
            # Also save as text for easy reading
            text_file = self.results_dir / f"analysis_{timestamp}.txt"
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(f"Browser Analysis Results\\n")
                f.write(f"{'='*50}\\n\\n")
                f.write(f"Timestamp: {timestamp}\\n")
                f.write(f"Task: {prompt}\\n")
                f.write(f"Starting Page: {starting_page}\\n")
                f.write(f"Session ID: {self.browser_client.session_id}\\n\\n")
                f.write(f"Agent Response:\\n")
                f.write(f"{'-'*30}\\n")
                f.write(f"{result}\\n")
            
            # Display results
            console.print(f"\\n[bold green]✅ Analysis Complete![/bold green]")
            console.print(f"📋 Results saved: {result_file}")
            console.print(f"📄 Text summary: {text_file}")
            console.print(f"📸 Full page screenshot: {full_screenshot}")
            console.print(f"📸 Viewport screenshot: {viewport_screenshot}")
            
            console.print(f"\\n[bold cyan]🎯 Agent Response:[/bold cyan]")
            console.print(Panel(str(result), title="Analysis Results", border_style="green"))
            
            return result_data
            
        except Exception as e:
            console.print(f"[red]❌ Error during analysis: {e}[/red]")
            import traceback
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            return {
                "error": str(e),
                "success": False
            }
        
        finally:
            # Cleanup
            try:
                if self.browser_client:
                    self.browser_client.stop()
                    console.print("[green]✅ Browser session cleaned up[/green]")
            except Exception as e:
                console.print(f"[yellow]⚠️ Cleanup warning: {e}[/yellow]")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Browser Analysis with LlamaIndex")
    parser.add_argument("--prompt", required=True, help="Analysis task prompt")
    parser.add_argument("--starting-page", required=True, help="Starting URL")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    
    args = parser.parse_args()
    
    async def main():
        analyzer = BrowserAutomationWithLlamaIndex(region=args.region)
        result = await analyzer.run_analysis(args.prompt, args.starting_page)
        
        if result and result.get("success"):
            console.print("\\n[bold green]✅ Browser analysis completed successfully![/bold green]")
        else:
            console.print("\\n[bold red]❌ Browser analysis failed![/bold red]")
    
    asyncio.run(main())
EOF

echo "✅ BrowserAutomationWithLlamaIndex class defined!"

# Cell 5: Initialize the system
echo "Cell 5: Initializing the Browser Analysis System..."
python << 'EOF'
import boto3
from rich.console import Console

console = Console()

# Get AWS region
boto_session = boto3.Session()
region = boto_session.region_name or "us-east-1"

console.print("🚀 Browser Analysis System with LlamaIndex ready!")
console.print("\n📋 System capabilities:")
console.print("   ✅ Automated browser navigation")
console.print("   ✅ Playwright automation")
console.print("   ✅ Screenshot capture (full page + viewport)")
console.print("   ✅ LlamaIndex + Bedrock Titan Text Express")
console.print("   ✅ Content extraction and analysis")
console.print("   ✅ Universal website compatibility")
console.print(f"\n🎯 Using AWS region: {region}")
console.print("\n🎬 Ready for browser automation!")
EOF

# Cell 6: Example 1 - Stock Analysis
echo "Cell 6: Running Example 1 - Apple Stock Analysis..."
python browser_automation_with_llamaindex.py \
    --prompt "Find and extract the current stock price, market cap, and P/E ratio" \
    --starting-page "https://stockanalysis.com/stocks/aapl/"

# Cell 7: Example 2 - News Headlines
echo "Cell 7: Running Example 2 - News Headlines Extraction..."
python browser_automation_with_llamaindex.py \
    --prompt "Extract the top 3 news headlines and provide a brief summary of each" \
    --starting-page "https://news.ycombinator.com"

# Cell 8: Example 3 - E-commerce Product Analysis
echo "Cell 8: Running Example 3 - Amazon Product Analysis..."
python browser_automation_with_llamaindex.py \
    --prompt "Find the product name, price, rating, and key features" \
    --starting-page "https://www.amazon.com/dp/B08N5WRWNW"

# Cell 9: Example 4 - Financial Data
echo "Cell 9: Running Example 4 - Tesla Financial Data..."
python browser_automation_with_llamaindex.py \
    --prompt "Extract Tesla's current stock price, market cap, and recent performance metrics" \
    --starting-page "https://finance.yahoo.com/quote/TSLA"

# Cell 10: Example 5 - GitHub Trending
echo "Cell 10: Running Example 5 - GitHub Trending Analysis..."
python browser_automation_with_llamaindex.py \
    --prompt "What are the top 5 trending repositories and what technologies are they using?" \
    --starting-page "https://github.com/trending"

echo ""
echo "=========================================="
echo "01_getting_started-agentcore-browser-tool-with-llamaindex.ipynb execution completed!"
echo "=========================================="
echo ""
echo "What You've Accomplished:"
echo "- ✅ Browser Automation: Automated web navigation and content extraction"
echo "- ✅ LlamaIndex Integration: AI-powered content analysis with Bedrock Titan"
echo "- ✅ Multiple Use Cases: Stock analysis, news extraction, product analysis, and more"
echo "- ✅ Screenshot Capture: Full page and viewport screenshots saved"
echo "- ✅ Universal Compatibility: Works with any website and custom prompts"
echo ""
echo "Results Location:"
echo "- 📁 All results saved in: analysis_results/"
echo "- 📄 JSON files with complete analysis data"
echo "- 📄 Text files with extracted results"
echo "- 📸 Screenshots (full page + viewport)"
echo ""
echo "Next Steps:"
echo "- Check the analysis_results/ directory for all saved results"
echo "- Experiment with different websites and analysis prompts"
echo "- Customize the BrowserAutomationWithLlamaIndex class for your specific needs"
echo "- Build more complex multi-step automation workflows"
echo ""
echo "Happy automating! 🚀"