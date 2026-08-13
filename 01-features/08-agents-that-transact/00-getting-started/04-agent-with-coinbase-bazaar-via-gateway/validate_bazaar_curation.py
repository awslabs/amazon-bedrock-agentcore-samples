"""
Validate Bazaar Curation — standalone verification script.

Confirms that the Coinbase x402 Bazaar's **curation** layer is active and honored
through your AgentCore Gateway. Run after Step 1 of the README (Gateway deployed and
GATEWAY_URL in the shared .env).

What it checks (read-only — no payments, no wallet required):
  1. The Gateway exposes the three Bazaar tools (search_resources, proxy_tool_call,
     validate_endpoint), prefixed with the target name (e.g. CoinbaseBazaar___...).
  2. search_resources accepts the `curatedOnly` filter and the filter is HONORED —
     i.e. an uncurated search surfaces resources a curated search does not.

Note on counting: search_resources returns at most 20 results per call, sets
`partialResults=true` when more match, and has no offset/cursor — so the full catalog
cannot be enumerated. This script reports the number of DISTINCT curated endpoints it
discovered across a set of probe queries as a LOWER BOUND, not the catalog size.

Usage:
    python validate_bazaar_curation.py

Requires: GATEWAY_URL in the shared .env (00-getting-started/.env). If the Gateway uses
CUSTOM_JWT inbound auth, also CLIENT_ID / CLIENT_SECRET / TOKEN_URL (auto-detected, same
as bazaar_gateway_agent.py). NONE-auth gateways need no credentials.

Note: you may see MCP output-schema validation warnings on stderr. The Bazaar returns extra
fields (e.g. `bundleSlugs`) that its advertised _meta.x402/curation schema doesn't declare, so
strict validation rejects the response ("Additional properties are not allowed"). The warnings
are benign (server-side schema drift) and do not affect the verdict — they only make the
discovered count a conservative lower bound.
"""

import json
import os
import sys
from datetime import timedelta

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

# Shared Tutorial 00 .env (one directory up)
ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(ENV_FILE, override=True)

# Gateway target name used when the target was added (agentcore add gateway-target
# --name CoinbaseBazaar ...). Gateway prefixes each tool with "<target>___".
TARGET = os.environ.get("BAZAAR_TARGET_NAME", "CoinbaseBazaar")
SEARCH_TOOL = f"{TARGET}___search_resources"

# Probe queries — diverse terms so the 20-result-per-call cap surfaces a wide sample.
# More/broader queries discover more distinct endpoints; this is a sample, not a census.
QUERIES = [
    "",
    "search",
    "data",
    "weather",
    "email",
    "file",
    "image",
    "code",
    "travel",
    "finance",
    "ai",
    "api",
    "crypto",
    "stock",
    "market",
    "map",
    "price",
    "news",
]

# Rough category buckets for a human-readable breakdown of what curation surfaces.
CATEGORIES = {
    "web search": ["search", "tavily", "exa", "serp", "google"],
    "finance/markets": ["stock", "price", "sec", "earning", "market", "defi", "kalshi", "polymarket", "messari"],
    "crypto/onchain": ["wallet", "token", "dex", "chain", "nft", "blockchain", "solana", "eth"],
    "travel": ["flight", "travel", "hotel", "seats", "tripadvisor"],
    "maps/local": ["map", "nearby", "solar", "geo", "place"],
    "enrichment/contacts": ["contact", "whitepages", "reddit", "clado", "people"],
    "dev tools": ["screenshot", "upload", "openrouter", "lens", "render"],
    "weather": ["weather", "forecast", "climate"],
}


def _extract_json(tool_result):
    """Pull the JSON payload out of a Strands ToolResult (content is a list of blocks)."""
    for block in tool_result.get("content", []) or []:
        text = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except (ValueError, TypeError):
                continue
    return {}


def search(mcp_client, query, curated_only, idx):
    """Call search_resources through the Gateway; return (tools, partialResults).

    Some Bazaar responses fail Strands' output-schema validation (the server returns extra
    fields its advertised _meta.x402/curation schema doesn't declare, e.g. `bundleSlugs`),
    which raises here. We treat that as a skipped probe rather than a hard failure, so counts
    are a lower bound.
    """
    try:
        result = mcp_client.call_tool_sync(
            tool_use_id=f"validate-{idx}",
            name=SEARCH_TOOL,
            arguments={"query": query, "curatedOnly": curated_only, "limit": 20},
        )
    except Exception as e:  # noqa: BLE001 — one bad response shouldn't tank the run
        print(f"  (skipped query {query!r} curatedOnly={curated_only}: {type(e).__name__})")
        return None, False
    payload = _extract_json(result)
    return payload.get("tools", []), payload.get("partialResults", False)


def discover(mcp_client, curated_only):
    """Run every probe query; return {tool_name: description} deduped, whether any call
    reported partialResults, and how many probes were skipped."""
    found, partial_seen, skipped = {}, False, 0
    for i, q in enumerate(QUERIES):
        tools, partial = search(mcp_client, q, curated_only, i)
        if tools is None:
            skipped += 1
            continue
        partial_seen = partial_seen or bool(partial)
        for t in tools:
            found[t["name"]] = t.get("description", "") or ""
    return found, partial_seen, skipped


def categorize(tools):
    counts = {c: 0 for c in CATEGORIES}
    for name, desc in tools.items():
        hay = f"{name} {desc}".lower()
        for cat, kws in CATEGORIES.items():
            if any(kw in hay for kw in kws):
                counts[cat] += 1
    return {c: n for c, n in counts.items() if n}


def main():
    gateway_url = os.environ.get("GATEWAY_URL", "")
    if not gateway_url:
        print("ERROR: GATEWAY_URL not set in .env. Deploy the Gateway first (README Step 1).")
        sys.exit(1)

    # Gateway auth — auto-detect from .env (same logic as bazaar_gateway_agent.py)
    gateway_headers = {}
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")
    token_url = os.environ.get("TOKEN_URL")
    if client_id and client_secret and token_url:
        from utils import get_oauth_token

        token = get_oauth_token(token_url, client_id, client_secret)
        gateway_headers = {"Authorization": f"Bearer {token}"}
        print("Gateway auth: CUSTOM_JWT (OAuth token acquired)")
    else:
        print("Gateway auth: NONE (no CLIENT_ID/CLIENT_SECRET/TOKEN_URL in .env)")

    print(f"Gateway: {gateway_url}")

    mcp_client = MCPClient(
        lambda: streamablehttp_client(
            gateway_url,
            headers=gateway_headers,
            timeout=timedelta(seconds=120),
        )
    )

    with mcp_client:
        # 1) Tool surface check
        tool_names = [t.tool_name for t in mcp_client.list_tools_sync()]
        print(f"\nGateway exposes {len(tool_names)} tool(s): {tool_names}")
        expected = {f"{TARGET}___search_resources", f"{TARGET}___proxy_tool_call", f"{TARGET}___validate_endpoint"}
        missing = expected - set(tool_names)
        if missing:
            print(f"⚠️  Expected Bazaar tools not found: {sorted(missing)}")

        # 2) Curated vs. uncurated
        print(f"\nProbing search_resources with {len(QUERIES)} queries (curatedOnly=true and false)...")
        curated, curated_partial, curated_skipped = discover(mcp_client, True)
        uncurated, uncurated_partial, uncurated_skipped = discover(mcp_client, False)

    curated_only_names = set(curated) - set(uncurated)
    uncurated_only_names = set(uncurated) - set(curated)

    print(f"\n{'=' * 64}")
    print(f"Distinct curated endpoints discovered:   {len(curated)}  (lower bound)")
    print(f"Distinct uncurated endpoints discovered: {len(uncurated)}  (lower bound)")
    print(f"partialResults seen (more exist):        curated={curated_partial}, uncurated={uncurated_partial}")
    if curated_skipped or uncurated_skipped:
        print(f"probes skipped (output-schema validation):curated={curated_skipped}, uncurated={uncurated_skipped}")
    print(f"{'=' * 64}")

    cats = categorize(curated)
    if cats:
        print("\nCurated endpoints by category (sample):")
        for cat, n in sorted(cats.items(), key=lambda kv: -kv[1]):
            print(f"  {n:3}  {cat}")

    # Verdict: curation is ENABLED and HONORED if curated returns results AND the
    # uncurated search surfaces resources the curated search excludes.
    print(f"\n{'=' * 64}")
    curation_returns = len(curated) > 0
    filter_narrows = len(uncurated_only_names) > 0
    if curation_returns and filter_narrows:
        print("✅ PASS — curation is enabled and the curatedOnly filter is honored.")
        print(
            f"   curated set is distinct from uncurated ({len(uncurated_only_names)} "
            f"uncurated-only endpoints excluded by the filter)."
        )
        print("   NOTE: the count above is a query-dependent lower bound, not the catalog size")
        print("   (search_resources caps at 20 results/call with no pagination).")
        code = 0
    elif curation_returns and not filter_narrows:
        print("⚠️  INCONCLUSIVE — curatedOnly=true returned results, but curated and uncurated")
        print("   sets were identical across these probes. Curation may not be enabled on this")
        print("   endpoint, or the probe set was too narrow. Try broadening QUERIES.")
        code = 2
    else:
        print("❌ FAIL — curatedOnly=true returned no endpoints. Check that the Bazaar target is")
        print("   reachable and that curation is enabled for this endpoint.")
        code = 1
    print(f"{'=' * 64}")
    sys.exit(code)


if __name__ == "__main__":
    main()
