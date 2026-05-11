#!/usr/bin/env python3
"""Load the Heurist tool catalog and format it for the agent system prompt."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import requests

from heurist_finance_agent.config import LIVE_CATALOG_CACHE_PATH, get_config

# --- Safety limits ---------------------------------------------------------
# These caps are intentionally generous for a sample but prevent accidental
# memory blow-ups from a misconfigured endpoint or disk corruption.
MAX_CATALOG_BYTES = 5 * 1024 * 1024  # 5 MiB on-disk cache
MAX_CATALOG_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MiB network payload
MAX_PROMPT_FIELD_LEN = 500  # per-field cap when rendered into the system prompt

# Sentinel used when an external field is dropped because it cannot be safely
# rendered inside a markdown table.
_UNSAFE_FIELD_PLACEHOLDER = "(unavailable)"

# Characters we refuse to echo back into the system prompt because they can
# be used to break the markdown table or inject links / code fences.
_UNSAFE_PROMPT_CHARS = re.compile(r"[\x00-\x1f\x7f`|\[\]]")


def _sanitize_prompt_text(value: Any, max_len: int = MAX_PROMPT_FIELD_LEN) -> str:
    """Return a markdown-safe single-line string derived from ``value``.

    External catalog data is interpolated into the agent's system prompt.
    Without sanitization a malicious registry entry could inject links,
    code fences, or table pipes that alter the prompt structure.
    """
    if value is None:
        return ""
    text = str(value)
    # Strip control characters and markdown metacharacters that would break
    # the rendered table or allow link/code-fence injection.
    text = _UNSAFE_PROMPT_CHARS.sub(" ", text)
    # Collapse whitespace so the line stays on a single row.
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "…"
    return text


def _sanitize_url(value: Any) -> str:
    """Only accept http(s) URLs; otherwise return a placeholder."""
    text = _sanitize_prompt_text(value, max_len=MAX_PROMPT_FIELD_LEN)
    if not text:
        return _UNSAFE_FIELD_PLACEHOLDER
    if not re.match(r"^https?://[^\s]+$", text, re.IGNORECASE):
        return _UNSAFE_FIELD_PLACEHOLDER
    return text


def _coerce_price(raw: Any) -> float:
    """Convert a raw price value into a finite, non-negative float.

    Rejects ``NaN``, infinities and negative values since they break
    comparisons and downstream arithmetic.
    """
    try:
        price = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid price value {raw!r}") from exc
    if not math.isfinite(price) or price < 0:
        raise ValueError(
            f"Invalid price value {raw!r}: must be a finite, non-negative number"
        )
    return price


def _atomic_write_text(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically via a same-directory temp file.

    Using ``tempfile.mkstemp`` + ``os.replace`` prevents concurrent readers and
    writers from seeing a half-written file (the TOCTOU bug flagged by the
    validator).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        # Best-effort cleanup of the temp file on failure.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def fetch_live_catalog(session: requests.Session | None = None) -> dict[str, Any]:
    """Fetch the live Heurist mesh registry and cache it locally."""
    cfg = get_config()
    http = session or requests.Session()
    response = http.get(cfg.heurist_catalog_url, timeout=30, stream=True)
    response.raise_for_status()

    # Enforce a size cap on the streamed response before JSON-decoding it.
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_CATALOG_RESPONSE_BYTES:
            raise ValueError(
                f"Heurist catalog response exceeded {MAX_CATALOG_RESPONSE_BYTES} bytes"
            )
        chunks.append(chunk)
    body = b"".join(chunks).decode(response.encoding or "utf-8")
    payload = json.loads(body)

    _atomic_write_text(LIVE_CATALOG_CACHE_PATH, json.dumps(payload, indent=2))
    return payload


def load_live_catalog(path: Path | None = None) -> dict[str, Any]:
    input_path = path or LIVE_CATALOG_CACHE_PATH
    if not input_path.exists():
        raise FileNotFoundError(f"Live catalog cache not found: {input_path}")
    size = input_path.stat().st_size
    if size > MAX_CATALOG_BYTES:
        raise ValueError(
            f"Catalog cache at {input_path} is {size} bytes which exceeds the "
            f"{MAX_CATALOG_BYTES} byte limit. Delete or regenerate the file."
        )
    return json.loads(input_path.read_text(encoding="utf-8"))


def get_live_catalog(
    refresh: bool = False, session: requests.Session | None = None
) -> dict[str, Any]:
    if refresh or not LIVE_CATALOG_CACHE_PATH.exists():
        return fetch_live_catalog(session=session)
    return load_live_catalog()


def get_tools_for_agents(
    agent_ids: tuple[str, ...] | list[str],
    refresh: bool = False,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    """Return normalized tool definitions for the selected Heurist agents."""
    selected = set(agent_ids)
    live_catalog = get_live_catalog(refresh=refresh, session=session)
    tools: list[dict[str, Any]] = []

    for agent in live_catalog.get("agents", []):
        agent_id = agent.get("agentId")
        if not agent_id or agent_id not in selected:
            continue
        for tool in agent.get("tools", []):
            try:
                price_usd = _coerce_price(tool["priceUsd"])
            except (KeyError, ValueError):
                # Skip tools with an invalid or missing price rather than
                # letting NaN/Infinity/negative values leak into the prompt.
                continue
            tools.append(
                {
                    "agent_id": agent_id,
                    "tool_name": tool.get("name", ""),
                    "resource_url": tool.get("resourceUrl", ""),
                    "price_usd": price_usd,
                    "method": tool.get("method", "POST"),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}) or {},
                }
            )

    return tools


def format_catalog_for_prompt(tools: list[dict[str, Any]]) -> str:
    """Format the tool catalog as a reference table for the agent system prompt.

    The agent uses this to know which URLs to call via http_request. All
    externally-sourced fields are sanitized so that untrusted registry data
    cannot inject markdown links, code fences, or extra table columns into
    the agent's system prompt.
    """
    lines = ["## Available Paid Endpoints (Heurist x402)", ""]
    lines.append("| Agent | Tool | URL | Method | Price | Description |")
    lines.append("|-------|------|-----|--------|-------|-------------|")

    for t in tools:
        agent_id = _sanitize_prompt_text(t.get("agent_id"), max_len=80)
        tool_name = _sanitize_prompt_text(t.get("tool_name"), max_len=80)
        url = _sanitize_url(t.get("resource_url"))
        method = _sanitize_prompt_text(t.get("method"), max_len=10) or "POST"
        desc = _sanitize_prompt_text(t.get("description"), max_len=80)
        price = t.get("price_usd")
        price_str = (
            f"${price:.3f}"
            if isinstance(price, (int, float)) and math.isfinite(price)
            else "n/a"
        )
        lines.append(
            f"| {agent_id} | {tool_name} | {url} | {method} | {price_str} | {desc} |"
        )

    lines.append("")
    lines.append("### Parameter Schemas")
    lines.append("")
    for t in tools:
        params = t.get("parameters", {}) or {}
        props = params.get("properties", {}) or {}
        if not props:
            continue
        agent_id = _sanitize_prompt_text(t.get("agent_id"), max_len=80)
        tool_name = _sanitize_prompt_text(t.get("tool_name"), max_len=80)
        method = _sanitize_prompt_text(t.get("method"), max_len=10) or "POST"
        url = _sanitize_url(t.get("resource_url"))
        lines.append(f"**{agent_id}/{tool_name}** (`{method} {url}`)")
        required_fields = params.get("required", []) or []
        for name, schema in props.items():
            if not isinstance(schema, dict):
                schema = {}
            safe_name = _sanitize_prompt_text(name, max_len=80)
            required = safe_name in {
                _sanitize_prompt_text(r, max_len=80) for r in required_fields
            }
            req_marker = " (required)" if required else ""
            type_name = _sanitize_prompt_text(schema.get("type", "any"), max_len=40)
            desc = _sanitize_prompt_text(schema.get("description", ""), max_len=120)
            lines.append(f"  - `{safe_name}`: {type_name}{req_marker} — {desc}")
        lines.append("")

    return "\n".join(lines)
