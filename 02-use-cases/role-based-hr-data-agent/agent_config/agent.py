"""
HRDataAgent — Strands-based agent that connects to Amazon Bedrock AgentCore Gateway via MCP/JSON-RPC.

Discovers tools dynamically from the Gateway (filtered per OAuth scope) and
invokes them over HTTP JSON-RPC. All field-level DLP redaction is applied
transparently by the Gateway Response Interceptor before data reaches here.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from strands import Agent
from strands.models import BedrockModel
from strands.types.tools import AgentTool, ToolResult, ToolUse
from strands.types._events import ToolResultEvent

logger = logging.getLogger(__name__)

MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

_SAFE_NAME = re.compile(r"[^A-Za-z0-9_-]+")


def _safe_tool_name(name: str) -> str:
    safe = _SAFE_NAME.sub("_", name).strip("_")
    return safe or "tool"


def _normalize_input_schema(tool_schema: Dict[str, Any]) -> Dict[str, Any]:
    schema = tool_schema.get("inputSchema") or tool_schema.get("input_schema") or {}
    if isinstance(schema, dict) and "json" in schema and isinstance(schema["json"], dict):
        return schema
    if isinstance(schema, dict):
        return {"json": schema}
    return {"json": {"type": "object", "properties": {}}}


async def _call_gateway_jsonrpc(
    gateway_url: str,
    access_token: str,
    method: str,
    params: Optional[dict] = None,
) -> Any:
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": method,
            "params": params or {},
        }
        resp = await client.post(
            gateway_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("error") is not None:
            raise RuntimeError(f"Gateway error: {body['error']}")
        return body.get("result")


async def _list_tools(gateway_url: str, access_token: str) -> List[Dict[str, Any]]:
    result = await _call_gateway_jsonrpc(gateway_url, access_token, "tools/list", {})
    if result is None:
        return []
    if isinstance(result, list):
        return result
    if isinstance(result, dict) and isinstance(result.get("tools"), list):
        return result["tools"]
    return []


class _HTTPGatewayTool(AgentTool):
    """Wraps a single MCP tool from the Gateway as a Strands AgentTool."""

    def __init__(
        self,
        tool_schema: Dict[str, Any],
        gateway_url: str,
        access_token: str,
        name_map: Dict[str, str],
    ):
        original_name = tool_schema.get("name")
        if not original_name:
            raise ValueError(f"Tool schema missing 'name': {tool_schema}")

        self._original_name = original_name
        self._name = _safe_tool_name(original_name)
        self._description = tool_schema.get("description", "")
        self._input_schema = _normalize_input_schema(tool_schema)
        self._gateway_url = gateway_url
        self._access_token = access_token
        name_map[self._name] = self._original_name
        super().__init__()

    @property
    def tool_name(self) -> str:
        return self._name

    @property
    def tool_spec(self) -> Dict[str, Any]:
        return {
            "name": self._name,
            "description": self._description,
            "inputSchema": self._input_schema,
        }

    @property
    def tool_type(self) -> str:
        return "agentcore_gateway_http_jsonrpc"

    async def stream(
        self,
        tool_use: ToolUse,
        invocation_state: Dict[str, Any],
        **kwargs,
    ) -> AsyncGenerator[ToolResultEvent, None]:
        tool_input = tool_use.get("input", {})
        params = {"name": self._original_name, "arguments": tool_input}
        result = await _call_gateway_jsonrpc(
            self._gateway_url, self._access_token, "tools/call", params
        )

        result_text = ""
        if isinstance(result, dict):
            content = result.get("content", [])
            if isinstance(content, list):
                parts = [
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                result_text = "\n".join(p for p in parts if p) or str(result)
            else:
                result_text = str(result)
        else:
            result_text = str(result)

        tool_result: ToolResult = {
            "toolUseId": tool_use["toolUseId"],
            "status": "success",
            "content": [{"text": result_text}],
        }
        yield ToolResultEvent(tool_result)


SYSTEM_PROMPT = """You are a secure HR Assistant with role-based data access control.

You help users access HR information through the Amazon Bedrock AgentCore Gateway.
The Gateway enforces OAuth scope-based authorization and applies field-level DLP
redaction automatically — you receive data that is already correctly filtered for
the current user's role.

IMPORTANT RULES:
- Always call tools FIRST before responding. Never fabricate data.
- Present tool responses directly. Do not invent placeholder values.
- If a field contains [REDACTED - Insufficient Permissions], display it exactly.
- Never assume parameter values. Ask the user if required information is missing.
- Only explain redaction AFTER presenting data, and only if the user asks.

Available tools (shown based on your OAuth scopes):
- search_employee: Search employees by name, department, or role
- get_employee_profile: Get detailed employee profile (PII/address may be redacted)
- get_employee_compensation: Get salary and compensation data (requires comp scope)

Role capabilities:
- HR Manager / Admin: Full access — all fields visible
- HR Specialist: Profiles + PII visible; compensation and address redacted
- Employee: Search only — all PII, address, and compensation redacted
"""


class HRDataAgent:
    """
    Strands agent wired to AgentCore Gateway via JSON-RPC.

    Discovers tools dynamically on each invocation so tool visibility
    always reflects the caller's current OAuth scopes.
    """

    def __init__(self, gateway_url: str, access_token: str):
        self.gateway_url = gateway_url
        self.access_token = access_token

    async def process(self, user_prompt: str) -> Dict[str, Any]:
        model = BedrockModel(model_id=MODEL_ID, temperature=0.0, streaming=False)

        tool_schemas = await _list_tools(self.gateway_url, self.access_token)
        logger.info(f"Loaded {len(tool_schemas)} tools from Gateway")

        name_map: Dict[str, str] = {}
        tools = [
            _HTTPGatewayTool(schema, self.gateway_url, self.access_token, name_map)
            for schema in tool_schemas
        ]

        agent = Agent(model=model, system_prompt=SYSTEM_PROMPT, tools=tools)
        result = await asyncio.to_thread(agent, user_prompt)

        return {
            "result": result.message,
            "model": MODEL_ID,
            "tool_count": len(tools),
        }
