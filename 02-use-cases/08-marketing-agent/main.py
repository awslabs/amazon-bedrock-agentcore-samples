"""
Marketing Agent System

An interactive command-line interface for the Marketing Agent System.
This application uses a dynamic, plan-based execution model where a planner agent
determines the steps required to fulfill a user's request. These steps are then
executed by a series of specialized agents.

Features:
- Rich terminal UI with progress indicators and formatted output.
- Dynamic task planning based on user queries.
- Environment validation and system health checks.
- Interactive chat mode.
"""

import os
import sys
import json
import asyncio
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# --- Pre-computation and Configuration ---
# Must be set before importing strands to enable rich output for tools
os.environ["STRANDS_TOOL_CONSOLE_MODE"] = "enabled"
# Bypass the confirmation prompt for potentially risky tools like python_repl
os.environ["BYPASS_TOOL_CONSENT"] = "true"

from strands import Agent
from strands_tools import workflow, python_repl, file_write, editor, mem0_memory
from strands.telemetry import StrandsTelemetry

# Import custom tools and agent configurations
from tools.tavily_tool import web_search, web_extract, web_crawl
from tools.knowledge_base_tool import get_schema
from tools.sqllite_tool import run_sqlite_query
import agents.planner_agent as planner_config
import agents.researcher_agent as researcher_config
import agents.text2sql_agent as text2sql_config
import agents.python_agent as python_config
import agents.report_agent as report_config
import agents.reflection_agent as reflection_config
import agents.memory_agent as memory_config
from constants import BEDROCK_MODEL

# Ignore deprecation warnings
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Load environment variables from .env file
load_dotenv()

# --- Global Configurations ---
console = Console()
user_id = "marketing_user"


class Config:
    """Manages application configuration and environment validation."""

    def __init__(self):
        self.tavily_api_key: Optional[str] = os.getenv("TAVILY_API_KEY")
        self.otel_exporter_endpoint: Optional[str] = os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT"
        )

        # Map agent names from the planner to their configuration modules.
        self.agent_configs = {
            "researcher_agent": researcher_config,
            "text2sql_agent": text2sql_config,
            "python_agent": python_config,
            "report_agent": report_config,
            "reflection_agent": reflection_config,
        }

    def validate(self) -> bool:
        """Validates that required environment variables are set."""
        if not self.tavily_api_key:
            console.print("[bold red]❌ TAVILY_API_KEY is not set.[/bold red]")
            return False
        return True


class Application:
    """Orchestrates the marketing agent system and manages the CLI."""

    def __init__(self):
        self.config = Config()
        self.console = console
        if self.config.otel_exporter_endpoint:
            telemetry = StrandsTelemetry()
            telemetry.setup_otlp_exporter().setup_console_exporter()
            self.console.print("[bold green]🔍 Telemetry enabled.[/bold green]")

    def print_banner(self):
        """Prints the application banner."""
        banner_text = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                   Marketing Agent System                     ║
    ║                                                              ║
    ║        Powered by Strands, Tavily, and Amazon Bedrock        ║
    ║                                                              ║
    ║  🧠 Planner → 🔍 Researcher → 📊 Analyst → 📄 Reporter       ║
    ╚══════════════════════════════════════════════════════════════╝
        """
        self.console.print(
            Panel(banner_text, title="[bold]Welcome[/bold]", border_style="bright_blue")
        )

    def show_example_queries(self):
        """Shows a table of example queries."""
        table = Table(
            title="💡 Example Queries", show_header=True, header_style="bold magenta"
        )
        table.add_column("Query", style="cyan")
        table.add_column("Expected Agents", style="yellow")

        examples = [
            (
                "Research the latest trends in AI-powered marketing. Include diagram if possible.",
                "Planner, Researcher, Python (for analysis), Reporter",
            ),
            (
                "Analyze the market share of top cloud providers.",
                "Planner, Researcher, Python (for analysis), Reporter",
            ),
            (
                "Generate a report on the benefits of serverless computing.",
                "Planner, Researcher, Reporter",
            ),
            (
                "Analyze John's recent purchases and suggest potential items to advertise to him.",
                "Planner, Researcher, Python (for analysis), Text2SQL, Reporter",
            ),
        ]

        for query, agents in examples:
            table.add_row(query, agents)

        self.console.print(table)

    def show_memory_info(self):
        """Shows information about automatic memory management."""
        info_panel = Panel(
            "[bold cyan]🧠 Smart Memory Management[/bold cyan]\n\n"
            "The system now automatically detects and stores:\n"
            "• Your preferences and likes/dislikes\n"
            "• Business context and company information\n"
            "• Goals and objectives you mention\n"
            "• Important facts and constraints\n\n"
            "[dim]Just speak naturally - no special keywords needed![/dim]",
            border_style="blue",
        )
        self.console.print(info_panel)

    def run_planner(self, query: str) -> Optional[list]:
        """Runs the planner agent to generate a task list."""
        # Create a fresh planner agent for each execution to avoid state conflicts
        planner_agent = Agent(
            model=BEDROCK_MODEL, system_prompt=planner_config.system_prompt, messages=[]
        )

        try:
            raw_output = str(
                planner_agent(f"Create a plan for the following user request: {query}")
            )

            json_start = raw_output.find("{")
            json_end = raw_output.rfind("}") + 1
            if json_start == -1 or json_end == 0:
                raise json.JSONDecodeError(
                    "No JSON object found in planner's output.", raw_output, 0
                )

            plan_str = raw_output[json_start:json_end]
            plan = json.loads(plan_str)
            return plan.get("tasks")
        except (json.JSONDecodeError, KeyError) as e:
            self.console.print(f"[bold red]❌ Failed to parse plan:[/bold red] {e}")
            self.console.print(f"[dim]LLM Output:\n{raw_output}[/dim]")
            return None
        except Exception as e:
            self.console.print(f"[bold red]❌ Planner execution failed:[/bold red] {e}")
            return None

    def execute_plan_direct(self, tasks: list, user_query: str):
        """Executes the generated plan by running agents with parallel execution and reflection."""
        completed_tasks = {}
        task_results = {}
        max_retries = 2

        for retry_count in range(max_retries + 1):
            if retry_count == 0:
                self.console.print(
                    f"\n[bold blue]🚀 Starting workflow execution[/bold blue]"
                )
            else:
                self.console.print(
                    f"\n[bold blue]🔄 Retry attempt {retry_count + 1}/{max_retries + 1}[/bold blue]"
                )

            # Reset for retry
            if retry_count > 0:
                completed_tasks = {}
                task_results = {}
                execution_order = []

            # Sort tasks by dependencies (simple topological sort)
            remaining_tasks = tasks.copy()
            execution_order = []

            while remaining_tasks:
                # Find tasks with no unmet dependencies
                ready_tasks = []
                for task in remaining_tasks:
                    deps = task.get("dependencies", [])
                    if all(dep in completed_tasks for dep in deps):
                        ready_tasks.append(task)

                if not ready_tasks:
                    self.console.print(
                        "[bold red]❌ Circular dependency detected or invalid dependencies![/bold red]"
                    )
                    return

                # Execute ready tasks in parallel if there are multiple
                if len(ready_tasks) > 1:
                    self.console.print(
                        f"[bold cyan]⚡ Executing {len(ready_tasks)} tasks in parallel[/bold cyan]"
                    )
                    import concurrent.futures
                    import threading

                    with concurrent.futures.ThreadPoolExecutor(
                        max_workers=min(len(ready_tasks), 3)
                    ) as executor:
                        future_to_task = {}
                        for task in ready_tasks:
                            future = executor.submit(
                                self._execute_single_task,
                                task,
                                task_results,
                                user_query,
                                tasks,
                            )
                            future_to_task[future] = task

                        for future in concurrent.futures.as_completed(future_to_task):
                            task = future_to_task[future]
                            try:
                                result = future.result()
                                task_results[task["task_id"]] = result
                                completed_tasks[task["task_id"]] = "COMPLETED"
                                execution_order.append(task)
                                remaining_tasks.remove(task)
                                self.console.print(
                                    f"[bold green]✅ Completed:[/bold green] {task['task_id']}"
                                )
                            except Exception as e:
                                self.console.print(
                                    f"[bold red]❌ Failed:[/bold red] {task['task_id']} - {e}"
                                )
                                completed_tasks[task["task_id"]] = "FAILED"
                                task_results[task["task_id"]] = f"Error: {e}"
                                execution_order.append(task)
                                remaining_tasks.remove(task)
                else:
                    # Single task execution
                    task = ready_tasks[0]
                    execution_order.append(task)
                    remaining_tasks.remove(task)

                    try:
                        result = self._execute_single_task(
                            task, task_results, user_query, tasks
                        )
                        task_results[task["task_id"]] = result
                        completed_tasks[task["task_id"]] = "COMPLETED"
                        self.console.print(
                            f"[bold green]✅ Completed:[/bold green] {task['task_id']}"
                        )
                    except Exception as e:
                        self.console.print(
                            f"[bold red]❌ Failed:[/bold red] {task['task_id']} - {e}"
                        )
                        completed_tasks[task["task_id"]] = "FAILED"
                        task_results[task["task_id"]] = f"Error: {e}"

            # Run reflection after all tasks complete
            if self._should_run_reflection(tasks):
                reflection_result = self._run_reflection(
                    user_query, task_results, execution_order
                )
                if "PROCEED" in reflection_result.upper():
                    self.console.print(
                        "[bold green]🎯 Reflection: Quality approved - PROCEED[/bold green]"
                    )
                    break
                elif "RETRY" in reflection_result.upper() and retry_count < max_retries:
                    self.console.print(
                        f"[bold yellow]🔄 Reflection: Quality needs improvement - RETRY (attempt {retry_count + 2}/{max_retries + 1})[/bold yellow]"
                    )
                    self.console.print(
                        "[bold cyan]🔄 Restarting workflow from the beginning...[/bold cyan]"
                    )
                    # Clear execution order for clean restart display
                    execution_order = []
                    continue  # This will restart the for loop with retry_count + 1
                else:
                    if retry_count >= max_retries:
                        self.console.print(
                            "[bold red]⚠️ Max retries reached - proceeding with current results[/bold red]"
                        )
                    else:
                        self.console.print(
                            "[bold red]⚠️ Reflection result unclear - proceeding with current results[/bold red]"
                        )
                    break
            else:
                # No reflection needed, proceed
                break

        # Show final summary
        self.console.print("\n[bold green]🎉 Plan Execution Complete![/bold green]")

        summary_table = Table(
            title="Task Execution Summary",
            show_header=True,
            header_style="bold magenta",
        )
        summary_table.add_column("Task ID", style="cyan")
        summary_table.add_column("Agent", style="yellow")
        summary_table.add_column("Status", style="green")

        for task in execution_order:
            status = completed_tasks.get(task["task_id"], "UNKNOWN")
            if status == "COMPLETED":
                status_style = "green"
            elif status == "TIMEOUT":
                status_style = "yellow"
            else:
                status_style = "red"
            summary_table.add_row(
                task["task_id"],
                task["agent"],
                f"[{status_style}]{status}[/{status_style}]",
            )

        self.console.print(summary_table)

    def _execute_single_task(
        self, task: dict, task_results: dict, user_query: str, all_tasks: list
    ) -> str:
        """Execute a single task and return the result."""
        agent_name = task.get("agent")
        if agent_name not in self.config.agent_configs:
            raise Exception(f"Unknown agent: '{agent_name}'")

        self.console.print(
            f"[bold blue]🔄 Executing:[/bold blue] {task['task_id']} ({agent_name})"
        )

        # Create agent with appropriate tools
        agent_cfg = self.config.agent_configs[agent_name]

        # Determine which tools this agent needs
        agent_tools = []
        if agent_name == "researcher_agent":
            agent_tools = [web_search, web_extract, web_crawl]
        elif agent_name == "python_agent":
            agent_tools = [python_repl]
        elif agent_name == "report_agent":
            agent_tools = [file_write, editor]
        elif agent_name == "text2sql_agent":
            agent_tools = [get_schema, run_sqlite_query]  # No special tools needed
        elif agent_name == "reflection_agent":
            agent_tools = []  # No special tools needed

        # Create fresh agent instance with configured Bedrock model
        agent = Agent(
            model=BEDROCK_MODEL,
            system_prompt=agent_cfg.system_prompt,
            tools=agent_tools,
            messages=[],  # Fresh message history
        )

        # Build context from dependent tasks with better structure
        context_parts = []
        for dep_id in task.get("dependencies", []):
            if dep_id in task_results:
                # Find the original task info for better context
                dep_task_info = next(
                    (t for t in all_tasks if t["task_id"] == dep_id), None
                )
                if dep_task_info:
                    context_parts.append(
                        f"=== RESULTS FROM: {dep_id.upper()} ({dep_task_info.get('agent', 'unknown')}) ===\n"
                        f"Task Description: {dep_task_info.get('description', 'N/A')}\n"
                        f"Results:\n{task_results[dep_id]}\n"
                        f"{'='*60}"
                    )
                else:
                    context_parts.append(
                        f"Results from {dep_id}:\n{task_results[dep_id]}"
                    )

        # Create the prompt with better structure
        if context_parts:
            task_prompt = (
                f"CONTEXT FROM PREVIOUS TASKS:\n"
                f"{'='*80}\n"
                f"\n\n".join(context_parts) + f"\n\n{'='*80}\n"
                f"YOUR CURRENT TASK:\n"
                f"{task['description']}\n\n"
                f"IMPORTANT: Use the context above to inform your work. "
                f"Reference specific findings and build upon previous results."
            )
        else:
            task_prompt = task["description"]

        # Execute the task with additional context for report agent
        if agent_name == "report_agent":
            # For report agent, also pass the original user query for context
            full_prompt = f"ORIGINAL USER REQUEST: {user_query}\n\n{task_prompt}"
            result = agent(full_prompt)
        else:
            result = agent(task_prompt)

        # Show a preview of the result
        result_preview = (
            str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
        )
        self.console.print(f"[dim]Result preview: {result_preview}[/dim]")

        return str(result)

    def _should_run_reflection(self, tasks: list) -> bool:
        """Determine if reflection should be run based on task types."""
        # Run reflection if there are multiple research/analysis tasks
        research_tasks = [
            t
            for t in tasks
            if t.get("agent") in ["researcher_agent", "python_agent", "text2sql_agent"]
        ]
        return len(research_tasks) >= 2

    def _run_reflection(
        self, user_query: str, task_results: dict, execution_order: list
    ) -> str:
        """Run the reflection agent to evaluate task quality."""
        self.console.print(
            "[bold purple]🔍 Running quality reflection...[/bold purple]"
        )

        # Create reflection agent
        reflection_agent = Agent(
            model=BEDROCK_MODEL,
            system_prompt=reflection_config.system_prompt,
            tools=[],
            messages=[],
        )

        # Build reflection prompt
        results_summary = "\n\n".join(
            [
                f"Task: {task['task_id']} ({task.get('agent', 'unknown')})\nResult: {task_results.get(task['task_id'], 'No result')}"
                for task in execution_order
            ]
        )

        reflection_prompt = f"""Original Request: {user_query}

Task Results:
{results_summary}

Please evaluate the quality and completeness of these results."""

        result = reflection_agent(reflection_prompt)
        self.console.print(f"[dim]Reflection result: {str(result)[:300]}...[/dim]")
        return str(result)

    def execute_plan(self, tasks: list, user_query: str):
        """Executes the generated plan using direct agent execution."""
        return self.execute_plan_direct(tasks, user_query)

    def generate_query_from_memories(self, query: str, memories: List[Dict]) -> str:
        # Format memories into a string for the LLM
        memories_str = "\n".join([f"- {mem['memory']}" for mem in memories])

        # Create a prompt that includes user context
        prompt = f"""
    User ID: "{user_id}"
    User question: "{query}"

    Relevant memories for user "{user_id}":
    {memories_str}

    Please generate a helpful response using the memories as context.
    All generated files should be saved to appropriate output directories:
    - Images: output/images/
    - Reports: output/reports/
    - Data files: output/
    """

        return prompt

    async def run(self):
        """Main application loop."""
        self.print_banner()
        if not self.config.validate():
            self.console.print(
                "\nPlease set the required environment variables and restart."
            )
            return

        self.show_example_queries()

        print("\n")

        self.show_memory_info()

        print(
            "\nTry mentioning your preferences or company details naturally in conversation!\n"
        )

        # create mem0 Agent
        mem0agent = memory_config.create_memory_agent()

        while True:
            try:
                user_query = Prompt.ask(
                    "\n[bold green]Please enter your request[/bold green]",
                    console=self.console,
                )

                if user_query.lower() in ["quit", "exit", "bye"]:
                    self.console.print("[bold yellow]👋 Goodbye![/bold yellow]")
                    break
                if not user_query.strip():
                    continue

                # Automatically analyze and store valuable information
                try:
                    was_stored = memory_config.analyze_and_store_if_valuable(
                        mem0agent, user_query, user_id
                    )
                    if was_stored:
                        self.console.print(
                            "\n[dim]💾 Stored valuable information from your input[/dim]\n"
                        )
                except Exception as e:
                    self.console.print(f"\n[dim]⚠️ Memory analysis failed: {e}[/dim]\n")

                # Retrieve relevant memories for context
                try:
                    relevant_memories = memory_config.retrieve_memories(
                        mem0agent, user_query, user_id
                    )

                    if relevant_memories:
                        self.console.print(
                            f"[bold cyan]🧠 Found {len(relevant_memories)} relevant memories[/bold cyan]"
                        )
                        user_query = self.generate_query_from_memories(
                            user_query, relevant_memories
                        )
                    else:
                        self.console.print(
                            "[dim]No relevant memories found for this query[/dim]"
                        )
                except Exception as e:
                    self.console.print(
                        f"[bold yellow]⚠️ Memory retrieval failed: {e}[/bold yellow]"
                    )
                    # Continue without memories if retrieval fails

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=self.console,
                    transient=True,
                ) as progress:
                    task_id = progress.add_task(
                        "Generating a dynamic plan...", total=None
                    )
                    planned_tasks = self.run_planner(user_query)
                    progress.stop()

                if planned_tasks:
                    self.console.print(
                        f"[bold green]✅ Plan Generated:[/bold green] {len(planned_tasks)} tasks."
                    )

                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        console=self.console,
                        transient=True,
                    ) as progress:
                        progress.add_task("Executing plan...", total=None)
                        self.execute_plan(planned_tasks, user_query)

            except (KeyboardInterrupt, EOFError):
                self.console.print("\n[bold yellow]👋 Goodbye![/bold yellow]")
                break
            except Exception as e:
                self.console.print(
                    f"\n[bold red]❌ An unexpected error occurred: {e}[/bold red]"
                )


if __name__ == "__main__":
    app = Application()
    asyncio.run(app.run())
