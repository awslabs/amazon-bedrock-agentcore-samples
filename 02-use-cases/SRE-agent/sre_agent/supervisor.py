#!/usr/bin/env python3

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Literal

from langchain_anthropic import ChatAnthropic
from langchain_aws import ChatBedrock

from .llm_utils import create_llm_with_error_handling
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from .agent_state import AgentState
from .constants import SREConstants
from .output_formatter import create_formatter
from .prompt_loader import prompt_loader

# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,  # Set the log level to INFO
    # Define log message format
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

# Enable HTTP and MCP protocol logs for debugging
# Comment out the following lines to suppress these logs if needed
# mcp_loggers = ["streamable_http", "mcp.client.streamable_http", "httpx", "httpcore"]
#
# for logger_name in mcp_loggers:
#     mcp_logger = logging.getLogger(logger_name)
#     mcp_logger.setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class InvestigationPlan(BaseModel):
    """Investigation plan created by supervisor."""

    steps: List[str] = Field(
        description="List of 3-5 investigation steps to be executed"
    )
    agents_sequence: List[str] = Field(
        description="Sequence of agents to invoke (kubernetes, logs, metrics, runbooks)"
    )
    complexity: Literal["simple", "complex"] = Field(
        description="Whether this plan is simple (auto-execute) or complex (needs approval)"
    )
    auto_execute: bool = Field(
        description="Whether to execute automatically or ask for user approval"
    )
    reasoning: str = Field(
        description="Brief explanation of the investigation approach"
    )


class RouteDecision(BaseModel):
    """Decision made by supervisor for routing."""

    next: Literal["kubernetes", "logs", "metrics", "runbooks", "FINISH"] = Field(
        description="The next agent to route to, or FINISH if done"
    )
    reasoning: str = Field(
        description="Brief explanation of why this routing decision was made"
    )


def _read_supervisor_prompt() -> str:
    """Read supervisor system prompt from file."""
    try:
        prompt_path = (
            Path(__file__).parent
            / "config"
            / "prompts"
            / "supervisor_multi_agent_prompt.txt"
        )
        if prompt_path.exists():
            return prompt_path.read_text().strip()
    except Exception as e:
        logger.warning(f"Could not read supervisor prompt file: {e}")

    # Default prompt if file not found
    return """You are the Supervisor Agent orchestrating a team of specialized SRE agents.

Your team consists of:
1. Kubernetes Infrastructure Agent - Handles K8s cluster operations, pod status, deployments, and resource monitoring
2. Application Logs Agent - Analyzes logs, searches for patterns, and identifies errors
3. Performance Metrics Agent - Monitors application performance, resource usage, and availability
4. Operational Runbooks Agent - Provides troubleshooting guides and operational procedures

Your responsibilities:
- Analyze incoming queries and determine which agent(s) should handle them
- Route queries to the most appropriate agent based on the query content
- Determine if multiple agents need to collaborate
- Aggregate responses when multiple agents are involved
- Provide clear, actionable responses to users

Routing guidelines:
- For Kubernetes/infrastructure issues → kubernetes agent
- For log analysis or error investigation → logs agent  
- For performance/metrics questions → metrics agent
- For procedures/troubleshooting guides → runbooks agent
- For complex issues spanning multiple domains → multiple agents

Always consider if a query requires multiple perspectives. For example:
- "Why is my service down?" might need kubernetes (pod status) + logs (errors) + metrics (performance)
- "Debug high latency" might need metrics (performance data) + logs (error patterns)"""


class SupervisorAgent:
    """Supervisor agent that orchestrates other agents."""

    def __init__(self, llm_provider: str = "bedrock", **llm_kwargs):
        self.llm_provider = llm_provider
        self.llm = self._create_llm(**llm_kwargs)
        self.system_prompt = _read_supervisor_prompt()
        self.formatter = create_formatter(llm_provider=llm_provider)

    def _create_llm(self, **kwargs):
        """Create LLM instance with improved error handling."""
        return create_llm_with_error_handling(self.llm_provider, **kwargs)

    async def create_investigation_plan(self, state: AgentState) -> InvestigationPlan:
        """Create an investigation plan for the user's query."""
        current_query = state.get("current_query", "No query provided")

        planning_prompt = f"""{self.system_prompt}

User's query: {current_query}

Create a simple, focused investigation plan with 2-3 steps maximum. Consider:
- Start with the most relevant single agent
- Add one follow-up agent only if clearly needed
- Keep it simple - most queries need only 1-2 agents
- Mark as simple unless it involves production changes or multiple domains

Return a structured plan."""

        structured_llm = self.llm.with_structured_output(InvestigationPlan)

        plan = await structured_llm.ainvoke(
            [
                SystemMessage(content=planning_prompt),
                HumanMessage(content=current_query),
            ]
        )

        logger.info(
            f"Created investigation plan: {len(plan.steps)} steps, complexity: {plan.complexity}"
        )
        return plan

    def _format_plan_markdown(self, plan: InvestigationPlan) -> str:
        """Format investigation plan as properly formatted markdown."""
        plan_text = "## 🔍 Investigation Plan\n\n"

        # Add steps with proper numbering and formatting
        for i, step in enumerate(plan.steps, 1):
            plan_text += f"**{i}.** {step}\n\n"

        # Add metadata
        plan_text += f"**📊 Complexity:** {plan.complexity.title()}\n"
        plan_text += f"**🤖 Auto-execute:** {'Yes' if plan.auto_execute else 'No'}\n"
        if plan.reasoning:
            plan_text += f"**💭 Reasoning:** {plan.reasoning}\n"

        # Add agents involved
        if plan.agents_sequence:
            agents_list = ", ".join(
                [agent.replace("_", " ").title() for agent in plan.agents_sequence]
            )
            plan_text += f"**👥 Agents involved:** {agents_list}\n"

        return plan_text

    async def route(self, state: AgentState) -> Dict[str, Any]:
        """Determine which agent should handle the query next."""
        agents_invoked = state.get("agents_invoked", [])

        # Check if we have an existing plan
        existing_plan = state.get("metadata", {}).get("investigation_plan")

        if not existing_plan:
            # First time - create investigation plan
            plan = await self.create_investigation_plan(state)

            # Check if we should auto-approve the plan (defaults to False if not set)
            auto_approve = state.get("auto_approve_plan", False)

            if not plan.auto_execute and not auto_approve:
                # Complex plan - present to user for approval
                plan_text = self._format_plan_markdown(plan)
                return {
                    "next": "FINISH",
                    "metadata": {
                        **state.get("metadata", {}),
                        "investigation_plan": plan.model_dump(),
                        "routing_reasoning": f"Created investigation plan. Complexity: {plan.complexity}",
                        "plan_pending_approval": True,
                        "plan_text": plan_text,
                    },
                }
            else:
                # Simple plan - start execution
                next_agent = (
                    plan.agents_sequence[0] if plan.agents_sequence else "FINISH"
                )
                plan_text = self._format_plan_markdown(plan)
                return {
                    "next": next_agent,
                    "metadata": {
                        **state.get("metadata", {}),
                        "investigation_plan": plan.model_dump(),
                        "routing_reasoning": f"Executing plan step 1: {plan.steps[0] if plan.steps else 'Start'}",
                        "plan_step": 0,
                        "plan_text": plan_text,
                        "show_plan": True,
                    },
                }
        else:
            # Continue executing existing plan
            plan = InvestigationPlan(**existing_plan)
            current_step = state.get("metadata", {}).get("plan_step", 0)

            # Check if plan is complete
            if current_step >= len(plan.agents_sequence) or not agents_invoked:
                next_step = current_step
            else:
                next_step = current_step + 1

            if next_step >= len(plan.agents_sequence):
                # Plan complete
                return {
                    "next": "FINISH",
                    "metadata": {
                        **state.get("metadata", {}),
                        "routing_reasoning": "Investigation plan completed. Presenting results.",
                        "plan_step": next_step,
                    },
                }
            else:
                # Continue with next agent in plan
                next_agent = plan.agents_sequence[next_step]
                step_description = (
                    plan.steps[next_step]
                    if next_step < len(plan.steps)
                    else f"Execute {next_agent}"
                )

                return {
                    "next": next_agent,
                    "metadata": {
                        **state.get("metadata", {}),
                        "routing_reasoning": f"Executing plan step {next_step + 1}: {step_description}",
                        "plan_step": next_step,
                    },
                }

    async def aggregate_responses(self, state: AgentState) -> Dict[str, Any]:
        """Aggregate responses from multiple agents into a final response."""
        agent_results = state.get("agent_results", {})
        metadata = state.get("metadata", {})

        # Check if this is a plan approval request
        if metadata.get("plan_pending_approval"):
            plan = metadata.get("investigation_plan", {})
            query = state.get("current_query", "Investigation") or "Investigation"

            # Use enhanced formatting for plan approval
            try:
                approval_response = self.formatter.format_plan_approval(plan, query)
            except Exception as e:
                logger.warning(
                    f"Failed to use enhanced formatting: {e}, falling back to plain text"
                )
                plan_text = metadata.get("plan_text", "")
                approval_response = f"""## Investigation Plan

I've analyzed your query and created the following investigation plan:

{plan_text}

**Complexity:** {plan.get('complexity', 'unknown').title()}
**Reasoning:** {plan.get('reasoning', 'Standard investigation approach')}

This plan will help systematically investigate your issue. Would you like me to proceed with this plan, or would you prefer to modify it?

You can:
- Type "proceed" or "yes" to execute the plan
- Type "modify" to suggest changes
- Ask specific questions about any step"""

            return {"final_response": approval_response, "next": "FINISH"}

        if not agent_results:
            return {"final_response": "No agent responses to aggregate."}

        # Use enhanced formatting for investigation results
        query = state.get("current_query", "Investigation") or "Investigation"
        plan = metadata.get("investigation_plan")

        try:
            # Try enhanced formatting first
            final_response = self.formatter.format_investigation_response(
                query=query, agent_results=agent_results, metadata=metadata, plan=plan
            )
        except Exception as e:
            logger.warning(
                f"Failed to use enhanced formatting: {e}, falling back to LLM aggregation"
            )

            # Fallback to LLM-based aggregation
            try:
                # Get system message from prompt loader
                system_prompt = prompt_loader.load_prompt(
                    "supervisor_aggregation_system"
                )

                # Determine if this is plan-based or standard aggregation
                is_plan_based = plan is not None

                # Prepare template variables
                query = (
                    state.get("current_query", "No query provided")
                    or "No query provided"
                )
                agent_results_json = json.dumps(agent_results, indent=2)
                auto_approve_plan = state.get("auto_approve_plan", False) or False

                if is_plan_based:
                    current_step = metadata.get("plan_step", 0)
                    total_steps = len(plan.get("steps", []))
                    plan_json = json.dumps(plan.get("steps", []), indent=2)

                    aggregation_prompt = (
                        prompt_loader.get_supervisor_aggregation_prompt(
                            is_plan_based=True,
                            query=query,
                            agent_results=agent_results_json,
                            auto_approve_plan=auto_approve_plan,
                            current_step=current_step + 1,
                            total_steps=total_steps,
                            plan=plan_json,
                        )
                    )
                else:
                    aggregation_prompt = (
                        prompt_loader.get_supervisor_aggregation_prompt(
                            is_plan_based=False,
                            query=query,
                            agent_results=agent_results_json,
                            auto_approve_plan=auto_approve_plan,
                        )
                    )

            except Exception as e:
                logger.error(f"Error loading aggregation prompts: {e}")
                # Fallback to simple prompt
                system_prompt = "You are an expert at presenting technical investigation results clearly and professionally."
                aggregation_prompt = (
                    f"Summarize these findings: {json.dumps(agent_results, indent=2)}"
                )

            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=aggregation_prompt),
                ]
            )

            final_response = response.content

        return {"final_response": final_response, "next": "FINISH"}
