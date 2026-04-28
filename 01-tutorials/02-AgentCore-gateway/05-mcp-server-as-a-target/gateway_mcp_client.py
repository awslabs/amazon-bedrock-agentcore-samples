"""Lightweight raw-HTTP client for AgentCore Gateway's MCP endpoint.

Used by the prompts/resources demos in the notebooks in this directory so
the cells can stay focused on the MCP method being demonstrated rather
than transport plumbing (bearer auth, MCP-Protocol-Version negotiation,
JSON-RPC envelope, cross-target pagination).

SDK clients (Strands MCPClient, the official mcp client) negotiate the
protocol version automatically; raw `requests.post` does not — hence the
explicit `MCP-Protocol-Version` header. The default matches the version
the gateway is created with in `01-mcp-server-target.ipynb` (Step 2.3).

Pagination note: `tools/list` (and the other list methods) page **per
target**. With one DEFAULT target plus one DYNAMIC target attached to the
same gateway, the first call returns one target's items plus a
`nextCursor`; calling again with that cursor returns the next target's
items, and so on. The `list_all_*` helpers below follow `nextCursor`
until exhausted and return the merged list.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import requests

DEFAULT_PROTOCOL_VERSION = "2025-11-25"


class GatewayMCPClient:
    """Tiny client wrapping JSON-RPC POSTs to the gateway's MCP endpoint."""

    def __init__(
        self,
        gateway_url: str,
        get_token: Callable[[], str],
        protocol_version: str = DEFAULT_PROTOCOL_VERSION,
    ) -> None:
        self.gateway_url = gateway_url
        self._get_token = get_token
        self._protocol_version = protocol_version

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self._protocol_version,
            "Authorization": f"Bearer {self._get_token()}",
        }

    def _rpc(
        self, method: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": method.replace("/", "-") + "-request",
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        return requests.post(
            self.gateway_url, headers=self._headers(), json=payload
        ).json()

    def _paginate(self, method: str, items_key: str) -> List[Dict[str, Any]]:
        """Follow ``result.nextCursor`` across pages and return merged items."""
        items: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        while True:
            params = {"cursor": cursor} if cursor else None
            resp = self._rpc(method, params)
            result = resp.get("result", {})
            items.extend(result.get(items_key, []))
            cursor = result.get("nextCursor")
            if not cursor:
                return items

    # --- Tools ----------------------------------------------------------

    def list_tools(self, cursor: Optional[str] = None) -> Dict[str, Any]:
        params = {"cursor": cursor} if cursor else None
        return self._rpc("tools/list", params)

    def list_all_tools(self) -> List[Dict[str, Any]]:
        """Return tools from every target, following per-target pagination."""
        return self._paginate("tools/list", "tools")

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self._rpc("tools/call", {"name": name, "arguments": arguments})

    # --- Prompts --------------------------------------------------------

    def list_prompts(self, cursor: Optional[str] = None) -> Dict[str, Any]:
        params = {"cursor": cursor} if cursor else None
        return self._rpc("prompts/list", params)

    def list_all_prompts(self) -> List[Dict[str, Any]]:
        return self._paginate("prompts/list", "prompts")

    def get_prompt(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self._rpc("prompts/get", {"name": name, "arguments": arguments})

    # --- Resources ------------------------------------------------------

    def list_resources(self, cursor: Optional[str] = None) -> Dict[str, Any]:
        params = {"cursor": cursor} if cursor else None
        return self._rpc("resources/list", params)

    def list_all_resources(self) -> List[Dict[str, Any]]:
        return self._paginate("resources/list", "resources")

    def read_resource(self, uri: str) -> Dict[str, Any]:
        return self._rpc("resources/read", {"uri": uri})

    def list_resource_templates(self, cursor: Optional[str] = None) -> Dict[str, Any]:
        params = {"cursor": cursor} if cursor else None
        return self._rpc("resources/templates/list", params)

    def list_all_resource_templates(self) -> List[Dict[str, Any]]:
        return self._paginate("resources/templates/list", "resourceTemplates")
