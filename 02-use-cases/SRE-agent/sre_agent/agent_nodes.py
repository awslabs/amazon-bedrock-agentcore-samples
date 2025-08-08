#!/usr/bin/env python3

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml
from langchain_anthropic import ChatAnthropic
from langchain_aws import ChatBedrock

from .llm_utils import create_llm_with_error_handling
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from .agent_state import AgentState
from .constants import SREConstants
from .prompt_loader import prompt_loader

# Logging will be configured by the main entry point
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_agent_config() -> Dict[str, Any]:
    """Load agent configuration from YAML file."""
    config_path = Path(__file__).parent / "config" / "agent_config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def _create_llm(provider: str = "bedrock", **kwargs):
    """Create LLM instance with improved error handling."""
    return create_llm_with_error_handling(provider, **kwargs)


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
        llm_provider: str = "bedrock",
        **llm_kwargs,
    ):
        self.name = name
        self.description = description
        self.tools = tools
        self.llm_provider = llm_provider

        logger.info(f"Initializing {name} with LLM provider: {llm_provider}")
        self.llm = _create_llm(llm_provider, **llm_kwargs)

        # Create the react agent
        self.agent = create_react_agent(self.llm, self.tools)

    def _get_system_prompt(self) -> str:
        """Get system prompt for this agent using prompt loader."""
        try:
            # Determine agent type based on name
            agent_type = self._get_agent_type()

            # Use prompt loader to get complete prompt
            return prompt_loader.get_agent_prompt(
                agent_type=agent_type,
                agent_name=self.name,
                agent_description=self.description,
            )
        except Exception as e:
            logger.error(f"Error loading prompt for agent {self.name}: {e}")
            # Fallback to basic prompt if loading fails
            return f"You are the {self.name}. {self.description}"

    def _get_agent_type(self) -> str:
        """Determine agent type based on agent name."""
        name_lower = self.name.lower()

        if "kubernetes" in name_lower:
            return "kubernetes"
        elif "logs" in name_lower or "application" in name_lower:
            return "logs"
        elif "metrics" in name_lower or "performance" in name_lower:
            return "metrics"
        elif "runbooks" in name_lower or "operational" in name_lower:
            return "runbooks"
        else:
            logger.warning(f"Unknown agent type for agent: {self.name}")
            return "unknown"

    async def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Process the current state and return updated state."""
        try:
            # Get the last user message
            messages = state["messages"]

            # Create a focused query for this agent
            agent_prompt = (
                f"As the {self.name}, help with: {state.get('current_query', '')}"
            )

            # If auto_approve_plan is set, add instruction to not ask follow-up questions
            if state.get("auto_approve_plan", False):
                agent_prompt += "\n\nIMPORTANT: Provide a complete, actionable response without asking any follow-up questions. Do not ask if the user wants more details or if they would like you to investigate further."

            # We'll collect all messages and the final response
            all_messages = []
            agent_response = ""

            # Add system prompt and user prompt
            system_message = SystemMessage(content=self._get_system_prompt())
            user_message = HumanMessage(content=agent_prompt)

            # Stream the agent execution to capture tool calls with timeout
            logger.info(f"{self.name} - Starting agent execution")

            try:
                # Add timeout to prevent infinite hanging (120 seconds)
                timeout_seconds = 120

                async def execute_agent():
                    nonlocal agent_response  # Fix scope issue - allow access to outer variable
                    chunk_count = 0
                    async for chunk in self.agent.astream(
                        {"messages": [system_message] + messages + [user_message]}
                    ):
                        chunk_count += 1
                        logger.info(
                            f"{self.name} - Processing chunk #{chunk_count}: {list(chunk.keys())}"
                        )

                        if "agent" in chunk:
                            agent_step = chunk["agent"]
                            if "messages" in agent_step:
                                for msg in agent_step["messages"]:
                                    all_messages.append(msg)
                                    # Log tool calls being made
                                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                                        logger.info(
                                            f"{self.name} - Agent making {len(msg.tool_calls)} tool calls"
                                        )
                                        for tc in msg.tool_calls:
                                            tool_name = tc.get("name", "unknown")
                                            tool_args = tc.get("args", {})
                                            tool_id = tc.get("id", "unknown")
                                            logger.info(
                                                f"{self.name} - Tool call: {tool_name} (id: {tool_id})"
                                            )
                                            logger.debug(
                                                f"{self.name} - Tool args: {tool_args}"
                                            )
                                    # Always capture the latest content from AIMessages
                                    if (
                                        hasattr(msg, "content")
                                        and hasattr(msg, "__class__")
                                        and "AIMessage" in str(msg.__class__)
                                    ):
                                        agent_response = msg.content
                                        logger.info(
                                            f"{self.name} - Agent response captured: {agent_response[:100]}... (total: {len(str(agent_response))} chars)"
                                        )

                        elif "tools" in chunk:
                            tools_step = chunk["tools"]
                            logger.info(
                                f"{self.name} - Tools chunk received, processing {len(tools_step.get('messages', []))} messages"
                            )
                            if "messages" in tools_step:
                                for msg in tools_step["messages"]:
                                    all_messages.append(msg)
                                    # Log tool executions
                                    if hasattr(msg, "tool_call_id"):
                                        tool_name = getattr(msg, "name", "unknown")
                                        tool_call_id = getattr(
                                            msg, "tool_call_id", "unknown"
                                        )
                                        content_preview = (
                                            str(msg.content)[:200]
                                            if hasattr(msg, "content")
                                            else "No content"
                                        )
                                        logger.info(
                                            f"{self.name} - Tool response received: {tool_name} (id: {tool_call_id}), content: {content_preview}..."
                                        )
                                        logger.debug(
                                            f"{self.name} - Full tool response: {msg.content if hasattr(msg, 'content') else 'No content'}"
                                        )

                logger.info(
                    f"{self.name} - Executing agent with timeout of {timeout_seconds} seconds"
                )
                await asyncio.wait_for(execute_agent(), timeout=timeout_seconds)
                logger.info(f"{self.name} - Agent execution completed")

            except asyncio.TimeoutError:
                logger.error(
                    f"{self.name} - Agent execution timed out after {timeout_seconds} seconds"
                )
                agent_response = f"Agent execution timed out after {timeout_seconds} seconds. The agent may be stuck on a tool call or LLM response."

            except Exception as e:
                logger.error(f"{self.name} - Agent execution failed: {e}")
                logger.exception("Full exception details:")
                agent_response = f"Agent execution failed: {str(e)}"

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
