#!/usr/bin/env python3
"""
DLP redaction verification test — calls the Amazon Bedrock AgentCore Gateway directly as each persona
and verifies that the correct fields are (or are not) redacted.

Usage:
  python test/test_dlp_redaction.py
  python test/test_dlp_redaction.py --persona hr-manager
"""

import argparse
import json
import sys
import uuid

import requests

sys.path.insert(0, ".")
from scripts.utils import get_ssm_parameter

REDACTED_MARKER = "[REDACTED - Insufficient Permissions]"

# Expected redaction behaviour per persona
PERSONA_EXPECTATIONS = {
    "hr-manager": {
        "pii_visible": True,
        "address_visible": True,
        "comp_visible": True,
        "comp_tool_visible": True,
    },
    "hr-specialist": {
        "pii_visible": True,
        "address_visible": False,
        "comp_visible": False,
        "comp_tool_visible": False,
    },
    "employee": {
        "pii_visible": False,
        "address_visible": False,
        "comp_visible": False,
        "comp_tool_visible": False,
    },
    "admin": {
        "pii_visible": True,
        "address_visible": True,
        "comp_visible": True,
        "comp_tool_visible": True,
    },
}


def get_token(persona: str, token_url: str) -> str:
    client_id = get_ssm_parameter(f"/app/hrdlp/personas/{persona}/client-id")
    client_secret = get_ssm_parameter(f"/app/hrdlp/personas/{persona}/client-secret")
    resp = requests.post(
        token_url,
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def jsonrpc(gateway_url: str, token: str, method: str, params: dict = None) -> dict:
    resp = requests.post(
        gateway_url,
        json={"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": method, "params": params or {}},
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def test_persona(persona: str, gateway_url: str, token_url: str) -> bool:
    expected = PERSONA_EXPECTATIONS[persona]
    token = get_token(persona, token_url)
    print(f"\n{'='*60}")
    print(f"Testing persona: {persona}")
    print(f"{'='*60}")

    passed = True

    # 1. Tool discovery
    tools_result = jsonrpc(gateway_url, token, "tools/list")
    tools = tools_result.get("result", {}).get("tools", [])
    tool_names = [t["name"] for t in tools]
    comp_visible = any("compensation" in n for n in tool_names)

    if comp_visible == expected["comp_tool_visible"]:
        print(f"  ✓ Compensation tool visibility: {comp_visible}")
    else:
        print(f"  ✗ Compensation tool visibility: expected={expected['comp_tool_visible']}, got={comp_visible}")
        passed = False

    # 2. Search employee
    search_result = jsonrpc(gateway_url, token, "tools/call", {
        "name": "hr-lambda-target___search_employee",
        "arguments": {"query": "John"},
    })
    content = search_result.get("result", {}).get("content", [])
    body = {}
    if content:
        try:
            lr = json.loads(content[0]["text"])
            body = json.loads(lr.get("body", "{}"))
        except Exception:
            pass

    employees = body.get("employees", [])
    if not employees:
        print("  ⚠ No employees returned from search — check Lambda deployment")
        return passed

    emp = employees[0]

    # Check PII
    email = emp.get("email", "")
    pii_redacted = email == REDACTED_MARKER
    pii_ok = (not pii_redacted) == expected["pii_visible"]
    print(f"  {'✓' if pii_ok else '✗'} PII (email): {'visible' if not pii_redacted else 'redacted'}")
    if not pii_ok:
        passed = False

    # Check address
    city = emp.get("city", "")
    addr_redacted = city == REDACTED_MARKER
    addr_ok = (not addr_redacted) == expected["address_visible"]
    print(f"  {'✓' if addr_ok else '✗'} Address (city): {'visible' if not addr_redacted else 'redacted'}")
    if not addr_ok:
        passed = False

    # Check compensation
    salary = emp.get("salary", "")
    comp_redacted = salary == REDACTED_MARKER
    comp_ok = (not comp_redacted) == expected["comp_visible"]
    print(f"  {'✓' if comp_ok else '✗'} Compensation (salary): {'visible' if not comp_redacted else 'redacted'}")
    if not comp_ok:
        passed = False

    print(f"  Result: {'PASS' if passed else 'FAIL'}")
    return passed


def main():
    parser = argparse.ArgumentParser(description="DLP redaction verification")
    parser.add_argument("--persona", default=None,
                        choices=["hr-manager", "hr-specialist", "employee", "admin"],
                        help="Test a single persona (default: all)")
    args = parser.parse_args()

    gateway_url = get_ssm_parameter("/app/hrdlp/gateway-url")
    token_url = get_ssm_parameter("/app/hrdlp/cognito-token-url")

    if not gateway_url or not token_url:
        print("ERROR: Required SSM parameters missing. Run prereq.sh first.")
        sys.exit(1)

    personas = [args.persona] if args.persona else list(PERSONA_EXPECTATIONS.keys())
    results = {}
    for p in personas:
        results[p] = test_persona(p, gateway_url, token_url)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    all_passed = True
    for p, ok in results.items():
        print(f"  {p:20s}  {'PASS' if ok else 'FAIL'}")
        if not ok:
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
