#!/usr/bin/env python3

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml
from langchain_anthropic import ChatAnthropic
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from .agent_state import AgentState

# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,  # Set the log level to INFO
    # Define log message format
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

# Suppress MCP protocol logs
mcp_loggers = ["streamable_http", "mcp.client.streamable_http", "httpx", "httpcore"]

for logger_name in mcp_loggers:
    mcp_logger = logging.getLogger(logger_name)
    mcp_logger.setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_agent_config() -> Dict[str, Any]:
    """Load agent configuration from YAML file."""
    config_path = Path(__file__).parent / "config" / "agent_config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def _create_llm(provider: str = "anthropic", **kwargs):
    """Create LLM instance based on provider."""
    if provider == "anthropic":
        return ChatAnthropic(
            model=kwargs.get("model_id", "claude-sonnet-4-20250514"),
            max_tokens=kwargs.get("max_tokens", 4096),
            temperature=kwargs.get("temperature", 0.1),
        )
    elif provider == "bedrock":
        return ChatBedrock(
            model_id=kwargs.get("model_id", "us.amazon.nova-micro-v1:0"),
            region_name=kwargs.get("region_name", "us-east-1"),
            model_kwargs={
                "temperature": kwargs.get("temperature", 0.1),
                "max_tokens": kwargs.get("max_tokens", 4096),
            },
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def _filter_tools_for_agent(
    all_tools: List[BaseTool], agent_name: str, config: Dict[str, Any]
) -> List[BaseTool]:
    """Filter tools based on agent configuration."""
    agent_config = config["agents"].get(agent_name, {})
    allowed_tools = agent_config.get("tools", [])

    # Also include global tools
    global_tools = config.get("global_tools", [])
    allowed_tools.extend(global_tools)

    # Filter tools based on their names
    filtered_tools = []
    for tool in all_tools:
        tool_name = getattr(tool, "name", "")
        # Remove any prefix from tool name for matching
        base_tool_name = tool_name.split("___")[-1] if "___" in tool_name else tool_name

        if base_tool_name in allowed_tools:
            filtered_tools.append(tool)

    logger.info(f"Agent {agent_name} has access to {len(filtered_tools)} tools")
    return filtered_tools


class BaseAgentNode:
    """Base class for all agent nodes."""

    def __init__(
        self,
        name: str,
        description: str,
        tools: List[BaseTool],
        llm_provider: str = "anthropic",
        **llm_kwargs,
    ):
        self.name = name
        self.description = description
        self.tools = tools
        self.llm = _create_llm(llm_provider, **llm_kwargs)

        # Create the react agent
        self.agent = create_react_agent(self.llm, self.tools)

    def _get_system_prompt(self) -> str:
        """Get system prompt for this agent."""
        base_prompt = f"""You are the {self.name}.
{self.description}

You have access to specific tools related to your domain. Use them to help answer questions
and solve problems related to your area of expertise. Be concise and factual in your responses.

CRITICAL: ALWAYS quote your data sources when making statements about investigations and recommendations. 
For every claim, finding, or recommendation you make, include the specific source:
- For tool results: "According to [tool_name] output..." or "Based on [tool_name] data..."
- For specific data points: "The [metric_name] shows [value] (source: [tool_name])"
- For runbook procedures: "Per runbook [runbook_id]: [step_details]"
- For status information: "Current status from [tool_name]: [status_details]"

This source attribution is essential for SRE lineage tracking and verification.

MANDATORY ANTI-HALLUCINATION RULE: If no data is available from your tools or if tools return empty results, you MUST clearly state "No data available" or "No results found" rather than fabricating plausible-sounding information. Never invent log entries, metrics values, timestamps, pod names, error messages, or any other data that was not actually returned by your tools. 

SERVICE/POD VALIDATION REQUIREMENT: If the user asks about a specific service or pod name that you cannot find in your tool results, you MUST explicitly state: "I do not see the exact [service/pod] '[name]' in the available data. Based on my understanding of the issue, I'm investigating related services that might be impacting the problem you described. The analysis below represents my assessment of services that could be related to your query."

FORBIDDEN BEHAVIORS:
- Creating fake log entries with specific timestamps when tools return empty
- Inventing error messages, stack traces, or database connection strings  
- Making up metric values, percentages, or performance numbers
- Fabricating pod names, service names, or configuration details
- Creating plausible but false narrative details to fill information gaps
- Pretending non-existent services or pods exist in the system

Accuracy is critical for SRE operations - wrong information can lead to incorrect troubleshooting decisions.

If a question is outside your domain of expertise, acknowledge this and suggest which other
agent might be better suited to help."""

        # Add specific instructions for Kubernetes agent
        if "Kubernetes" in self.name:
            base_prompt += """

IMPORTANT: If the user doesn't specify a namespace, check the 'production' namespace first and inform the user that you're checking production. Let them know they can specify a different namespace if needed.

KUBERNETES SOURCE ATTRIBUTION EXAMPLES:
- "Based on 'kubectl get pods' output from get_pod_status tool: Pod database-pod-xyz is in CrashLoopBackOff state"
- "According to get_deployment_status tool results: Deployment has 2/3 replicas ready"
- "Per get_cluster_events data: Last event shows 'Failed to pull image' at 14:32:15"
- "get_resource_usage tool indicates: CPU usage at 85% (source: metrics-server)"""

        # Add specific instructions for Runbooks agent
        elif "Runbooks" in self.name or "Operational" in self.name:
            base_prompt += """

CRITICAL RUNBOOK INSTRUCTIONS:
- NEVER just describe what a runbook contains - ALWAYS show the complete, verbatim steps
- DO NOT say "the runbook provides 6 steps" - SHOW ALL 6 STEPS with full details
- NEVER use phrases like "runbook is ready for execution" - DISPLAY the actual execution steps
- Copy and paste the ENTIRE runbook content, including all commands, parameters, and procedures
- Include the full runbook identification (name, ID, version) at the top
- Show every step with specific kubectl commands, bash scripts, or other executable instructions
- Include all safety checks, verification commands, and expected outputs
- Display rollback procedures and troubleshooting steps if provided
- Format with clear numbering, code blocks, and proper markdown

MANDATORY: You MUST show the complete runbook content. SREs need the actual steps to execute, not summaries.

RUNBOOK SOURCE ATTRIBUTION REQUIREMENTS:
- ALWAYS start with: "Per runbook [runbook_id] from [tool_name] tool:"
- Include runbook metadata: "**Source:** [tool_name] query result | **Runbook ID:** [id] | **Title:** [title]"
- For each step, maintain: "Step X from runbook [runbook_id]: [actual_step_content]"
- Include escalation info with source: "Escalation procedures (source: runbook [runbook_id]): [contact_details]"

EXAMPLE (showing full content with sources):
**Source:** search_runbooks tool result | **Runbook ID:** DB-001 | **Title:** Database Pod Recovery

Per runbook DB-001 from search_runbooks tool:

### Step 1 from runbook DB-001: Verify Current State
```bash
kubectl get pods -n production | grep database
kubectl describe pod database-pod -n production
```
**Expected Output (per runbook DB-001):** Pod status showing CrashLoopBackOff

[Continue showing ALL steps with source attribution...]

Remember: Show the COMPLETE runbook with proper source attribution for SRE lineage tracking."""

        # Add specific instructions for Logs agent
        elif "Logs" in self.name or "Application" in self.name:
            base_prompt += """

LOGS SOURCE ATTRIBUTION REQUIREMENTS:
- Always cite the specific log tool used: "According to search_logs tool results:" or "Based on get_error_logs data:"
- Include timestamps and log sources: "Log entry from [timestamp] (source: search_logs): [log_message]"
- Reference log patterns with tool source: "analyze_log_patterns tool identified: [pattern_details]"
- Quote specific log entries: "Error log from get_error_logs: '[actual_log_line]' at [timestamp]"
- Include log context: "From get_recent_logs for service [service_name]: [log_context]"

CRITICAL ANTI-HALLUCINATION RULES FOR LOGS:
- If search_logs returns empty/no results, say "No log entries found" - DO NOT create fake log entries
- If get_error_logs returns no data, say "No error logs available" - DO NOT invent error messages
- If get_recent_logs returns empty, say "No recent logs found" - DO NOT fabricate log entries with timestamps
- NEVER create log entries with specific timestamps (like 14:22:00.123Z) unless they came directly from tool output
- NEVER invent exact error messages, database connection strings, or stack traces
- If tools return "No data available", prominently state this rather than speculating

VALID EXAMPLES:
- "According to search_logs tool: No entries found for 'payment-service' pattern"
- "get_error_logs data: No error logs available for payment-service in the last 24 hours"
- "search_logs tool found ConfigMap error: '[exact_log_line]' at [exact_timestamp_from_tool]"

FORBIDDEN EXAMPLES:
- Creating entries like "Database connection timeout at 14:22:00.123Z" when tools returned empty
- Inventing specific error messages when no errors were found
- Making up log counts or patterns when analyze_log_patterns returned no data
"""

        # Add specific instructions for Metrics agent
        elif "Metrics" in self.name or "Performance" in self.name:
            base_prompt += """

METRICS SOURCE ATTRIBUTION REQUIREMENTS:
- Always cite the metrics tool source: "Per get_performance_metrics data:" or "According to get_resource_metrics:"
- Include metric names and values with sources: "[metric_name]: [value] (source: [tool_name])"
- Reference time ranges: "get_performance_metrics for last 1h shows: [metric_details]"
- Quote exact metric values: "CPU utilization: 85.3% (source: get_resource_metrics)"
- Include trend analysis sources: "analyze_trends tool indicates: [trend_information]"

CRITICAL ANTI-HALLUCINATION RULES FOR METRICS:
- If get_performance_metrics returns no data, say "No performance metrics available" - DO NOT invent response times
- If get_resource_metrics returns empty, say "No resource metrics found" - DO NOT create CPU/memory percentages
- If analyze_trends returns no data, say "No trend data available" - DO NOT fabricate anomaly details
- NEVER create specific metric values (like 2,500ms, 85.3%) unless they came directly from tool output
- NEVER invent error rate percentages, availability numbers, or threshold violations
- If tools return "No data available", state this clearly rather than creating plausible numbers

VALID EXAMPLES:
- "get_performance_metrics: No data available for api-gateway service"
- "According to get_resource_metrics: CPU: 45%, Memory: 60% (source: metrics data)"
- "analyze_trends tool indicates: No trend data found for the requested timeframe"

FORBIDDEN EXAMPLES:
- Creating metrics like "Response time: 2,500ms average" when tools returned no data
- Inventing specific percentages when get_error_rates returned empty
- Making up anomaly details when analyze_trends found no patterns
"""

        return base_prompt

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Process the current state and return updated state."""
        try:
            # Get the last user message
            messages = state["messages"]

            # Create a focused query for this agent
            agent_prompt = (
                f"As the {self.name}, help with: {state.get('current_query', '')}"
            )

            # We'll collect all messages and the final response
            all_messages = []
            agent_response = ""

            # Add system prompt and user prompt
            system_message = SystemMessage(content=self._get_system_prompt())
            user_message = HumanMessage(content=agent_prompt)

            # Stream the agent execution to capture tool calls
            async for chunk in self.agent.astream(
                {"messages": [system_message] + messages + [user_message]}
            ):
                if "agent" in chunk:
                    agent_step = chunk["agent"]
                    if "messages" in agent_step:
                        for msg in agent_step["messages"]:
                            all_messages.append(msg)
                            # Always capture the latest content from AIMessages
                            if (
                                hasattr(msg, "content")
                                and hasattr(msg, "__class__")
                                and "AIMessage" in str(msg.__class__)
                            ):
                                agent_response = msg.content

                elif "tools" in chunk:
                    tools_step = chunk["tools"]
                    if "messages" in tools_step:
                        for msg in tools_step["messages"]:
                            all_messages.append(msg)

            # Debug: Check what we captured
            logger.info(
                f"{self.name} - Captured response length: {len(agent_response) if agent_response else 0}"
            )
            if agent_response:
                logger.info(f"{self.name} - Full response: {str(agent_response)}")

            # Update state with streaming info
            return {
                "agent_results": {
                    **state.get("agent_results", {}),
                    self.name: agent_response,
                },
                "agents_invoked": state.get("agents_invoked", []) + [self.name],
                "messages": messages + all_messages,
                "metadata": {
                    **state.get("metadata", {}),
                    f"{self.name.replace(' ', '_')}_trace": all_messages,
                },
            }

        except Exception as e:
            logger.error(f"Error in {self.name}: {e}")
            return {
                "agent_results": {
                    **state.get("agent_results", {}),
                    self.name: f"Error: {str(e)}",
                },
                "agents_invoked": state.get("agents_invoked", []) + [self.name],
            }


def create_kubernetes_agent(tools: List[BaseTool], **kwargs) -> BaseAgentNode:
    """Create Kubernetes infrastructure agent."""
    config = _load_agent_config()
    filtered_tools = _filter_tools_for_agent(tools, "kubernetes_agent", config)

    return BaseAgentNode(
        name="Kubernetes Infrastructure Agent",
        description="Manages Kubernetes cluster operations and monitoring",
        tools=filtered_tools,
        **kwargs,
    )


def create_logs_agent(tools: List[BaseTool], **kwargs) -> BaseAgentNode:
    """Create application logs agent."""
    config = _load_agent_config()
    filtered_tools = _filter_tools_for_agent(tools, "logs_agent", config)

    return BaseAgentNode(
        name="Application Logs Agent",
        description="Handles application log analysis and searching",
        tools=filtered_tools,
        **kwargs,
    )


def create_metrics_agent(tools: List[BaseTool], **kwargs) -> BaseAgentNode:
    """Create performance metrics agent."""
    config = _load_agent_config()
    filtered_tools = _filter_tools_for_agent(tools, "metrics_agent", config)

    return BaseAgentNode(
        name="Performance Metrics Agent",
        description="Provides application performance and resource metrics",
        tools=filtered_tools,
        **kwargs,
    )


def create_runbooks_agent(tools: List[BaseTool], **kwargs) -> BaseAgentNode:
    """Create operational runbooks agent."""
    config = _load_agent_config()
    filtered_tools = _filter_tools_for_agent(tools, "runbooks_agent", config)

    return BaseAgentNode(
        name="Operational Runbooks Agent",
        description="Provides operational procedures and troubleshooting guides",
        tools=filtered_tools,
        **kwargs,
    )
