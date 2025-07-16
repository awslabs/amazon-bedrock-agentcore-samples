"""
Dynamic LangGraph Research Agent with Bedrock-AgentCore 1P Tools
The LLM generates all analysis code based on the research query
"""

import asyncio
import json
import time
from typing import Dict, List, TypedDict, Optional
from datetime import datetime

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_aws import ChatBedrockConverse
from bedrock_agentcore.tools.browser_client import BrowserClient
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
from rich.console import Console
from rich.panel import Panel

console = Console()


class AgentState(TypedDict):
    """State for the research agent"""
    messages: List
    research_query: str
    browser_session_id: Optional[str]
    code_session_id: Optional[str]
    research_data: Dict[str, any]
    completed_tasks: List[str]


class DynamicResearchAgent:
    """Research agent where LLM generates all code dynamically"""
    
    def __init__(self, region: str = "us-west-2"):
        self.region = region
        self.llm = ChatBedrockConverse(
            model="anthropic.claude-3-5-sonnet-20240620-v1:0",
            region_name=region
        )
        
        console.print("[cyan]Initializing Bedrock-AgentCore 1P Tools...[/cyan]")
        
        # Initialize persistent sessions
        self.code_client = CodeInterpreter(region)
        self.code_session_id = self.code_client.start()
        console.print(f"✅ Code Interpreter session: {self.code_session_id}")
        
        self.browser_client = BrowserClient(region)
        self.browser_session_id = self.browser_client.start()
        console.print(f"✅ Browser session: {self.browser_session_id}")
        
        time.sleep(20)  # Browser initialization
        self.ws_url, self.headers = self.browser_client.generate_ws_headers()
        console.print("✅ Browser ready\n")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
    
    def cleanup(self):
        console.print("\n[yellow]Cleaning up...[/yellow]")
        if self.browser_client:
            self.browser_client.stop()
        if self.code_client:
            self.code_client.stop()
    
    def execute_llm_generated_code(self, task_description: str, context: Dict = None) -> str:
        """Have LLM generate and execute code for the task"""
        console.print(f"\n[bold blue]🤖 LLM generating code for:[/bold blue] {task_description}")
        
        # Build prompt with context
        prompt = f"""You are working in a Python code interpreter sandbox. 
Task: {task_description}

Available context:
{json.dumps(context, indent=2) if context else 'No previous context'}

Generate Python code to accomplish this task. Be specific and include:
- Any necessary imports (pandas, numpy, matplotlib, json, etc are available)
- Error handling
- Clear output with print statements
- Save any results to files for later use

Return ONLY the Python code, no explanations."""
        
        # Get code from LLM
        response = self.llm.invoke([HumanMessage(content=prompt)])
        generated_code = response.content
        
        console.print("[dim]Generated code:[/dim]")
        console.print(f"[cyan]{generated_code[:200]}...[/cyan]" if len(generated_code) > 200 else f"[cyan]{generated_code}[/cyan]")
        
        # Execute the code
        result = self.code_client.invoke("executeCode", {
            "code": generated_code,
            "language": "python",
            "clearContext": False
        })
        
        # Extract output
        output = self._extract_output(result)
        
        if result.get("isError", False):
            console.print(f"[red]Execution error: {output}[/red]")
        else:
            console.print(f"[green]✅ Code executed successfully[/green]")
        
        return output
    
    def _extract_output(self, result: Dict) -> str:
        """Extract output from code execution result"""
        if "structuredContent" in result:
            stdout = result["structuredContent"].get("stdout", "")
            stderr = result["structuredContent"].get("stderr", "")
            return stdout + (f"\nSTDERR: {stderr}" if stderr else "")
        
        output_parts = []
        if "content" in result:
            for item in result["content"]:
                if item.get("type") == "text":
                    output_parts.append(item.get("text", ""))
        return "\n".join(output_parts)
    
    def create_workflow(self) -> StateGraph:
        """Create the workflow"""
        workflow = StateGraph(AgentState)
        
        workflow.add_node("understand_query", self.understand_query)
        workflow.add_node("collect_data", self.collect_data)
        workflow.add_node("process_data", self.process_data)
        workflow.add_node("analyze_data", self.analyze_data)
        workflow.add_node("generate_insights", self.generate_insights)
        
        workflow.set_entry_point("understand_query")
        workflow.add_edge("understand_query", "collect_data")
        workflow.add_edge("collect_data", "process_data")
        workflow.add_edge("process_data", "analyze_data")
        workflow.add_edge("analyze_data", "generate_insights")
        workflow.add_edge("generate_insights", END)
        
        return workflow.compile()
    
    def understand_query(self, state: AgentState) -> Dict:
        """Understand what the user wants to research"""
        console.print(f"\n[bold magenta]🎯 Understanding research query:[/bold magenta] {state['research_query']}")
        
        # Have LLM break down the query
        prompt = f"""Analyze this research query: '{state['research_query']}'
        
Break it down into:
1. What data needs to be collected
2. What analysis should be performed  
3. What insights are expected

Respond in JSON format."""
        
        response = self.llm.invoke([HumanMessage(content=prompt)])
        understanding = response.content
        
        console.print(f"[dim]LLM understanding: {understanding[:200]}...[/dim]")
        
        return {
            **state,
            "research_data": {"query_understanding": understanding},
            "completed_tasks": ["understand_query"]
        }
    
    def collect_data(self, state: AgentState) -> Dict:
        """Collect data based on the research query"""
        console.print("\n[bold magenta]📊 Collecting data...[/bold magenta]")
        
        # LLM generates code to create or fetch data
        output = self.execute_llm_generated_code(
            f"Create sample data for researching: {state['research_query']}. "
            "Generate realistic synthetic data with at least 100 records. "
            "Save the data as 'research_data.csv'.",
            context={"query": state['research_query']}
        )
        
        return {
            **state,
            "research_data": {
                **state["research_data"],
                "data_collection_output": output
            },
            "completed_tasks": state["completed_tasks"] + ["collect_data"]
        }
    
    def process_data(self, state: AgentState) -> Dict:
        """Process and clean the collected data"""
        console.print("\n[bold magenta]🔧 Processing data...[/bold magenta]")
        
        # LLM generates data processing code
        output = self.execute_llm_generated_code(
            "Load 'research_data.csv' and perform data processing: "
            "1. Check for missing values and handle them "
            "2. Create summary statistics "
            "3. Add any derived features that would be useful "
            "4. Save processed data as 'processed_data.csv' "
            "5. Print key statistics about the dataset",
            context=state["research_data"]
        )
        
        return {
            **state,
            "research_data": {
                **state["research_data"],
                "processing_output": output
            },
            "completed_tasks": state["completed_tasks"] + ["process_data"]
        }
    
    def analyze_data(self, state: AgentState) -> Dict:
        """Perform analysis on the processed data"""
        console.print("\n[bold magenta]📈 Analyzing data...[/bold magenta]")
        
        # LLM generates analysis code based on the research query
        output = self.execute_llm_generated_code(
            f"Load 'processed_data.csv' and perform analysis for: {state['research_query']}. "
            "Include: "
            "1. Statistical analysis relevant to the research question "
            "2. Create at least 2 visualizations and save as PNG files "
            "3. If applicable, perform clustering or classification "
            "4. Identify key patterns and trends "
            "5. Save analysis results as 'analysis_results.json'",
            context=state["research_data"]
        )
        
        return {
            **state,
            "research_data": {
                **state["research_data"],
                "analysis_output": output
            },
            "completed_tasks": state["completed_tasks"] + ["analyze_data"]
        }
    
    def generate_insights(self, state: AgentState) -> Dict:
        """Generate final report with insights"""
        console.print("\n[bold magenta]💡 Generating insights and report...[/bold magenta]")
        
        # LLM generates code to create final report
        output = self.execute_llm_generated_code(
            f"Create a comprehensive report for: {state['research_query']}. "
            "1. Load all previous results (analysis_results.json, any PNG files) "
            "2. Generate a markdown report with: "
            "   - Executive summary "
            "   - Key findings with supporting data "
            "   - Visualizations (reference the PNG files) "
            "   - Actionable recommendations "
            "   - Methodology section "
            "3. Save as 'final_report.md' "
            "4. Also create a presentation-ready summary as 'executive_summary.txt'",
            context=state["research_data"]
        )
        
        # Read and display the final report
        read_result = self.code_client.invoke("readFiles", {"paths": ["final_report.md"]})
        report_content = self._extract_output(read_result)
        
        console.print("\n[bold green]📄 Final Report:[/bold green]")
        console.print("="*60)
        console.print(report_content[:1000] + "..." if len(report_content) > 1000 else report_content)
        console.print("="*60)
        
        return {
            **state,
            "messages": state["messages"] + [AIMessage(content=report_content)],
            "completed_tasks": state["completed_tasks"] + ["generate_insights"]
        }


async def run_dynamic_research(query: str):
    """Run research with dynamic LLM-generated code"""
    console.print(Panel(
        f"[bold cyan]🚀 Dynamic Research Agent[/bold cyan]\n\n"
        f"Research Query: {query}\n\n"
        "[dim]The LLM will generate all analysis code dynamically[/dim]",
        border_style="blue"
    ))
    
    with DynamicResearchAgent() as agent:
        workflow = agent.create_workflow()
        
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "research_query": query,
            "browser_session_id": agent.browser_session_id,
            "code_session_id": agent.code_session_id,
            "research_data": {},
            "completed_tasks": []
        }
        
        final_state = await workflow.ainvoke(initial_state)
        
        # List all files created
        console.print("\n[bold]Files created by LLM:[/bold]")
        list_result = agent.code_client.invoke("listFiles", {"path": ""})
        files = agent._extract_output(list_result)
        console.print(files)
        
        console.print(f"\n[bold green]✅ Research completed![/bold green]")
        console.print(f"Tasks: {final_state['completed_tasks']}")


if __name__ == "__main__":
    import sys
    
    # Get query from command line or use default
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
        "Analyze customer satisfaction trends in e-commerce and identify factors that drive repeat purchases"
    
    asyncio.run(run_dynamic_research(query))
