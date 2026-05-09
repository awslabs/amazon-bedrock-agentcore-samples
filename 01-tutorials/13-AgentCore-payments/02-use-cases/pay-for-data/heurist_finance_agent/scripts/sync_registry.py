#!/usr/bin/env python3
"""Fetch the live Heurist catalog and refresh the local cache.

Usage:
    python -m heurist_finance_agent.scripts.sync_registry
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from heurist_finance_agent.catalog import fetch_live_catalog, get_tools_for_agents
from heurist_finance_agent.config import LIVE_CATALOG_CACHE_PATH, get_config


def main() -> None:
    cfg = get_config()
    catalog = fetch_live_catalog()
    selected_tools = get_tools_for_agents(cfg.heurist_tool_agent_ids, refresh=False)
    print(f"Saved live catalog cache to {LIVE_CATALOG_CACHE_PATH}")
    print(f"Catalog agents: {catalog['count']}")
    print(f"Selected agents: {', '.join(cfg.heurist_tool_agent_ids)}")
    print(f"Selected tools: {len(selected_tools)}")


if __name__ == "__main__":
    main()
