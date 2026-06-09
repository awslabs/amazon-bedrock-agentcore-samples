"""
Demonstrate multi-tenant tool isolation via Cedar policies on AgentCore Gateway.

For each tenant:
  1. Obtain an OAuth2 token with tenant-specific scope
  2. Connect to the Gateway and list visible tools
  3. Show that Cedar policies (ENFORCE mode) filter tools/list per tenant

Usage:
    python demo.py [--region REGION]

See also: demo_deny.py (demonstrates call-time denial of cross-tenant tools)
"""

import argparse
import json
import logging
from pathlib import Path

import requests

from utils.agent_with_gateway import list_tenant_tools

CONFIG_FILE = Path(__file__).parent / "config.json"

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def load_config():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError("config.json not found. Run deploy.py first.")
    return json.loads(CONFIG_FILE.read_text())


def get_token(token_endpoint, client_id, client_secret, scope):
    """Get OAuth2 access token via client_credentials grant."""
    response = requests.post(
        token_endpoint,
        data=f"grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}&scope={scope}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Token request failed ({response.status_code}): {response.text}")
    return response.json()["access_token"]


def demo_tenant(config, tenant_name):
    """Show tool visibility for a single tenant."""
    cognito = config["cognito"]
    client_cfg = cognito["clients"][tenant_name]

    log.info(f"\n{'=' * 60}")
    log.info(f"  Tenant: {tenant_name.upper()}")
    log.info(f"  Scope:  {client_cfg['scope']}")
    log.info(f"{'=' * 60}")

    token = get_token(
        token_endpoint=cognito["token_endpoint"],
        client_id=client_cfg["client_id"],
        client_secret=client_cfg["client_secret"],
        scope=client_cfg["scope"],
    )
    log.info("  Token obtained via client_credentials grant")

    gateway_url = config["gateway"]["gateway_url"]
    tools = list_tenant_tools(gateway_url, token)

    log.info(f"\n  Visible tools ({len(tools)}):")
    for name, desc in tools:
        log.info(f"    - {name}: {desc}")

    return {name for name, _ in tools}


def main():
    parser = argparse.ArgumentParser(description="Demo multi-tenant tool isolation")
    parser.add_argument("--region", help="AWS region (override)", default=None)
    parser.parse_args()

    config = load_config()

    log.info("Multi-Tenant Gateway Isolation Demo")
    log.info("=" * 60)
    log.info("")
    log.info("  Policy engine mode: ENFORCE")
    log.info("    ENFORCE  = policies enforced (allow or deny operations)")
    log.info("    LOG_ONLY = policies evaluated and traced, not enforced")
    log.info("")
    log.info("  This demo shows visibility filtering (tools/list per tenant).")
    log.info("  Run demo_deny.py to see call-time denial of cross-tenant tools.")

    banking_tools = demo_tenant(config, "banking")
    insurance_tools = demo_tenant(config, "insurance")

    # Summary
    log.info(f"\n{'=' * 60}")
    log.info("  VISIBILITY SUMMARY")
    log.info(f"{'=' * 60}")
    log.info(f"  Insurance sees: {sorted(insurance_tools)}")
    log.info(f"  Banking sees:   {sorted(banking_tools)}")

    insurance_only = insurance_tools - banking_tools
    banking_only = banking_tools - insurance_tools
    shared = insurance_tools & banking_tools

    if insurance_only:
        log.info(f"  Insurance-only:  {sorted(insurance_only)}")
    if banking_only:
        log.info(f"  Banking-only:    {sorted(banking_only)}")
    if shared:
        log.info(f"  Shared:          {sorted(shared)}")

    # Takeaway
    log.info(f"\n{'=' * 60}")
    log.info("  TAKEAWAY")
    log.info(f"{'=' * 60}")
    log.info("  Each tenant's Cedar policy defines which tools appear in tools/list.")
    log.info("  The LLM prompt only contains permitted tools. Unauthorized tools")
    log.info("  are not denied at call time; they simply do not exist in the LLM's")
    log.info("  context. The agent code has zero tenant logic.")
    log.info("")
    log.info("  To add a new tenant: one Cognito client + one Cedar policy.")
    log.info("  No agent code change. No redeploy. Runtime operation.")
    log.info("")
    log.info("  Next: python demo_deny.py  (cross-tenant call denial)")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
