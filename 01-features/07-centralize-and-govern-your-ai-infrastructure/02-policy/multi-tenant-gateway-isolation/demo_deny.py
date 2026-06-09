"""
Demonstrate that ENFORCE mode denies cross-tenant tool calls at the Gateway.

This script intentionally calls a tool that belongs to a different tenant.
The call is expected to FAIL. This shows the second layer of defense:
even if a caller bypasses tools/list and crafts a direct call_tool request,
the Gateway still enforces the Cedar policy.

Prerequisites:
    - Run deploy.py first (creates config.json)
    - Run demo.py first to see the visibility filtering (happy path)

Usage:
    python demo_deny.py [--region REGION]
"""

import argparse
import json
import logging
from pathlib import Path

import requests

from utils.agent_with_gateway import call_tool_raw, list_tenant_tools

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


def main():
    parser = argparse.ArgumentParser(description="Demo cross-tenant call denial")
    parser.add_argument("--region", help="AWS region (override)", default=None)
    parser.parse_args()

    config = load_config()

    log.info("Cross-Tenant Tool Call Denial Demo")
    log.info("=" * 60)
    log.info("")
    log.info("  This script INTENTIONALLY triggers a policy denial.")
    log.info("  It demonstrates what happens when a caller attempts to invoke")
    log.info("  a tool that their Cedar policy does not permit.")
    log.info("")

    # Get banking tenant token
    cognito = config["cognito"]
    banking_cfg = cognito["clients"]["banking"]
    banking_token = get_token(
        token_endpoint=cognito["token_endpoint"],
        client_id=banking_cfg["client_id"],
        client_secret=banking_cfg["client_secret"],
        scope=banking_cfg["scope"],
    )
    log.info("  Banking tenant token obtained")

    # First, show what banking CAN see
    gateway_url = config["gateway"]["gateway_url"]
    banking_tools = list_tenant_tools(gateway_url, banking_token)
    banking_tool_names = {name for name, _ in banking_tools}
    log.info(f"  Banking tenant's visible tools: {sorted(banking_tool_names)}")

    # Find an insurance-only tool to attempt
    insurance_cfg = cognito["clients"]["insurance"]
    insurance_token = get_token(
        token_endpoint=cognito["token_endpoint"],
        client_id=insurance_cfg["client_id"],
        client_secret=insurance_cfg["client_secret"],
        scope=insurance_cfg["scope"],
    )
    insurance_tools = list_tenant_tools(gateway_url, insurance_token)
    insurance_tool_names = {name for name, _ in insurance_tools}
    insurance_only = insurance_tool_names - banking_tool_names

    if not insurance_only:
        log.info("\n  No insurance-only tools found. Cannot demonstrate denial.")
        log.info("  (Both tenants may have identical permissions in current config)")
        return

    target_tool = sorted(insurance_only)[0]

    # Attempt the cross-tenant call
    log.info(f"\n{'=' * 60}")
    log.info("  CROSS-TENANT CALL ATTEMPT")
    log.info(f"{'=' * 60}")
    log.info(f"  Caller:   Banking tenant (scope: {banking_cfg['scope']})")
    log.info(f"  Tool:     {target_tool}")
    log.info("  Belongs to: Insurance tenant only")
    log.info("  Expected: DENIED")
    log.info("")

    success, result = call_tool_raw(gateway_url, banking_token, target_tool, {"member_id": "test-123"})

    log.info(f"  Result: {'SUCCESS (unexpected)' if success else 'DENIED'}")
    log.info(f"  Detail: {result}")

    log.info(f"\n{'=' * 60}")
    log.info("  EXPLANATION")
    log.info(f"{'=' * 60}")

    if not success:
        log.info("  ENFORCE mode provides two layers of protection:")
        log.info("")
        log.info("    Layer 1 (visibility): tools/list is filtered by Cedar policy.")
        log.info("    The LLM never learns about unauthorized tools, so it cannot")
        log.info("    reason about calling them or be tricked via prompt injection.")
        log.info("")
        log.info("    Layer 2 (denial): even a direct call_tool request (bypassing")
        log.info("    the LLM entirely) is rejected. This defends against crafted")
        log.info("    requests from compromised clients or manual API calls.")
        log.info("")
        log.info("  Policy engine modes:")
        log.info("    ENFORCE:  Evaluates actions against policies and enforces")
        log.info("              decisions by allowing or denying operations.")
        log.info("    LOG_ONLY: Evaluates actions and adds traces on whether calls")
        log.info("              would be allowed or denied, but does not enforce")
        log.info("              the decision.")
    else:
        log.info("  WARNING: The call succeeded unexpectedly.")
        log.info("  Verify the Cedar policies are attached to the Gateway.")

    log.info("")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
