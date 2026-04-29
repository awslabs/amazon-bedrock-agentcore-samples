#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Post-deploy smoke test for the unified AgentCore MCP runtime via Gateway.

Authenticates to the Gateway using a Pool A Cognito JWT, then sends MCP
requests through the Gateway URL. The Gateway handles SigV4 signing to
the Runtime via GATEWAY_IAM_ROLE -- the client only needs the JWT.

Auth flow:
  1. Set a temporary password on the Pool A test user via admin_set_user_password
  2. Authenticate with USER_PASSWORD_AUTH to get an ID token
  3. Send requests to the Gateway URL with Authorization: Bearer <id_token>

Checks:
  runtime_health  -- MCP initialize via Gateway, verify non-424
  runtime_tools   -- MCP tools/list via Gateway, verify expected tool count (6)

Usage:
    python scripts/smoke-test.py --region us-east-1
    python scripts/smoke-test.py --region us-east-1 --profile my-profile
    python scripts/smoke-test.py --region us-east-1 --checks runtime_health
    python scripts/smoke-test.py --region us-east-1 --timeout 300
"""

from __future__ import annotations

import argparse
import json
import secrets
import string
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import boto3

# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------

_CHECKS: Dict[str, Callable] = {}


def smoke_check(fn: Callable) -> Callable:
    _CHECKS[fn.__name__] = fn
    return fn


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    name: str
    passed: bool
    elapsed_s: float = 0.0
    error: Optional[str] = None
    detail: Optional[str] = None


@dataclass
class RuntimeInfo:
    name: str
    expected_tool_count: int
    # App tools we expect to be present (Gateway may add its own, e.g. the
    # built-in ``x_amz_bedrock_agentcore_search`` semantic-search tool).
    expected_tool_names: Optional[List[str]] = None


@dataclass
class SmokeContext:
    session: boto3.Session
    region: str
    timeout: int
    gateway_url: str
    jwt_token: str
    runtimes: List[RuntimeInfo] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_stack_output(cfn_client, stack_name: str, output_key: str) -> str:
    resp = cfn_client.describe_stacks(StackName=stack_name)
    for output in resp["Stacks"][0].get("Outputs", []):
        if output["OutputKey"] == output_key:
            return output["OutputValue"]
    raise KeyError(f"Output '{output_key}' not found in stack '{stack_name}'")


def acquire_cognito_jwt(
    session: boto3.Session,
    user_pool_id: str,
    client_id: str,
    username: str,
) -> str:
    """Get a Cognito ID token for the test user via USER_PASSWORD_AUTH.

    Sets a temporary password on the user, then authenticates to get the token.
    """
    cognito_idp = session.client("cognito-idp")

    # Generate a random password that meets Cognito requirements
    # Guarantee at least one char from each required class
    temp_password = (
        "S"  # uppercase
        + "m"  # lowercase
        + "0"  # digit
        + "!"  # symbol
        + "".join(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*") for _ in range(16))
    )

    # Set permanent password on the test user
    cognito_idp.admin_set_user_password(
        UserPoolId=user_pool_id,
        Username=username,
        Password=temp_password,
        Permanent=True,
    )

    # Authenticate with USER_PASSWORD_AUTH to get tokens
    auth_resp = cognito_idp.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": username,
            "PASSWORD": temp_password,
        },
    )

    return auth_resp["AuthenticationResult"]["IdToken"]


# ---------------------------------------------------------------------------
# MCP request helpers -- returns (parsed_body, mcp_session_id)
# ---------------------------------------------------------------------------


def _mcp_request(
    gateway_url: str,
    method: str,
    params: dict,
    jwt_token: str,
    timeout: int,
    request_id: int = 1,
    mcp_session_id: str = "",
) -> tuple[dict, str]:
    """Send a JSON-RPC MCP request to the Gateway with a Cognito JWT.

    The Gateway handles SigV4 signing to the Runtime via GATEWAY_IAM_ROLE.
    Returns (parsed_response, mcp_session_id).
    """
    body = json.dumps({
        "jsonrpc": "2.0", "id": request_id,
        "method": method, "params": params,
    }).encode()

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {jwt_token}",
    }
    if mcp_session_id:
        headers["Mcp-Session-Id"] = mcp_session_id

    req = urllib.request.Request(
        gateway_url, data=body, method="POST", headers=headers,
    )

    resp = urllib.request.urlopen(req, timeout=timeout)
    raw = resp.read().decode()
    session_id = resp.headers.get("Mcp-Session-Id", mcp_session_id)

    # Parse SSE or plain JSON
    if "text/event-stream" in resp.headers.get("Content-Type", ""):
        last_data = ""
        for line in raw.splitlines():
            if line.startswith("data:"):
                last_data = line[len("data:"):].strip()
        if last_data:
            return json.loads(last_data), session_id
    return json.loads(raw), session_id


# ---------------------------------------------------------------------------
# Smoke checks
# ---------------------------------------------------------------------------


@smoke_check
def runtime_health(ctx: SmokeContext) -> List[CheckResult]:
    """MCP initialize via Gateway -- verify non-424 and valid response."""
    results: List[CheckResult] = []
    for rt in ctx.runtimes:
        start = time.time()
        try:
            resp, _ = _mcp_request(
                ctx.gateway_url, "initialize",
                {"protocolVersion": "2024-11-05", "capabilities": {},
                 "clientInfo": {"name": "smoke-test", "version": "1.0"}},
                ctx.jwt_token, ctx.timeout,
            )
            elapsed = time.time() - start
            if "error" in resp:
                results.append(CheckResult(
                    name=f"health:{rt.name}", passed=False, elapsed_s=elapsed,
                    error=f"JSON-RPC error: {resp['error']}",
                ))
            else:
                server = resp.get("result", {}).get("serverInfo", {}).get("name", "?")
                results.append(CheckResult(
                    name=f"health:{rt.name}", passed=True, elapsed_s=elapsed,
                    detail=f"server={server}, time={elapsed:.1f}s",
                ))
        except urllib.error.HTTPError as e:
            elapsed = time.time() - start
            body = ""
            try:
                body = e.read().decode()[:200]
            except Exception:
                pass
            results.append(CheckResult(
                name=f"health:{rt.name}", passed=False, elapsed_s=elapsed,
                error=f"HTTP {e.code} after {elapsed:.1f}s: {body}",
            ))
        except Exception as exc:
            elapsed = time.time() - start
            results.append(CheckResult(
                name=f"health:{rt.name}", passed=False, elapsed_s=elapsed,
                error=f"{type(exc).__name__}: {exc}",
            ))
    return results


@smoke_check
def runtime_tools(ctx: SmokeContext) -> List[CheckResult]:
    """MCP initialize + tools/list via Gateway -- verify expected tool counts."""
    results: List[CheckResult] = []
    for rt in ctx.runtimes:
        start = time.time()
        try:
            # initialize first to get Mcp-Session-Id
            _, session_id = _mcp_request(
                ctx.gateway_url, "initialize",
                {"protocolVersion": "2024-11-05", "capabilities": {},
                 "clientInfo": {"name": "smoke-test", "version": "1.0"}},
                ctx.jwt_token, ctx.timeout,
            )
            # tools/list with session ID
            resp, _ = _mcp_request(
                ctx.gateway_url, "tools/list", {},
                ctx.jwt_token, ctx.timeout,
                request_id=2, mcp_session_id=session_id,
            )
            elapsed = time.time() - start

            if "error" in resp:
                results.append(CheckResult(
                    name=f"tools:{rt.name}", passed=False, elapsed_s=elapsed,
                    error=f"JSON-RPC error: {resp['error']}",
                ))
                continue

            tools = resp.get("result", {}).get("tools", [])
            names = [t.get("name", "?") for t in tools]

            # Prefer name-based check (tolerates Gateway-injected platform
            # tools like ``x_amz_bedrock_agentcore_search``). Fall back to
            # exact count when ``expected_tool_names`` is not set.
            if rt.expected_tool_names is not None:
                missing = [n for n in rt.expected_tool_names if n not in names]
                passed = not missing
                err = (
                    f"missing expected tools: {missing} (got {names})"
                    if missing else None
                )
            else:
                passed = len(tools) == rt.expected_tool_count
                err = (
                    f"expected {rt.expected_tool_count}, got {len(tools)}"
                    if not passed else None
                )

            results.append(CheckResult(
                name=f"tools:{rt.name}", passed=passed, elapsed_s=elapsed,
                detail=f"tools={names}",
                error=err,
            ))
        except urllib.error.HTTPError as e:
            elapsed = time.time() - start
            body = ""
            try:
                body = e.read().decode()[:200]
            except Exception:
                pass
            results.append(CheckResult(
                name=f"tools:{rt.name}", passed=False, elapsed_s=elapsed,
                error=f"HTTP {e.code} after {elapsed:.1f}s: {body}",
            ))
        except Exception as exc:
            elapsed = time.time() - start
            results.append(CheckResult(
                name=f"tools:{rt.name}", passed=False, elapsed_s=elapsed,
                error=f"{type(exc).__name__}: {exc}",
            ))
    return results


@smoke_check
def tool_list_tasks(ctx: SmokeContext) -> List[CheckResult]:
    """MCP tools/call opencode___list_tasks -- verify tool invocation works end-to-end."""
    results: List[CheckResult] = []
    for rt in ctx.runtimes:
        start = time.time()
        try:
            # initialize to get session
            _, session_id = _mcp_request(
                ctx.gateway_url, "initialize",
                {"protocolVersion": "2024-11-05", "capabilities": {},
                 "clientInfo": {"name": "smoke-test", "version": "1.0"}},
                ctx.jwt_token, ctx.timeout,
            )
            # call list_tasks — pass _user_id explicitly since the
            # interceptor may not inject it for all request patterns
            resp, _ = _mcp_request(
                ctx.gateway_url, "tools/call",
                {"name": "opencode___list_tasks", "arguments": {"_user_id": "smoke-test-user"}},
                ctx.jwt_token, ctx.timeout,
                request_id=2, mcp_session_id=session_id,
            )
            elapsed = time.time() - start

            if "error" in resp:
                results.append(CheckResult(
                    name=f"list_tasks:{rt.name}", passed=False, elapsed_s=elapsed,
                    error=f"JSON-RPC error: {resp['error']}",
                ))
                continue

            # Tool should return a result with content containing a tasks list
            result = resp.get("result", {})
            content = result.get("content", [])
            text = content[0].get("text", "") if content else ""

            tool_executed = len(content) > 0 and not result.get("isError", False)
            has_error = "error" in text.lower() and "No user_id" in text
            passed = tool_executed and not has_error

            detail = text[:120] + "..." if len(text) > 120 else text
            results.append(CheckResult(
                name=f"list_tasks:{rt.name}", passed=passed, elapsed_s=elapsed,
                detail=detail,
                error=None if passed else f"isError={result.get('isError')}, content={text[:200]}",
            ))
        except urllib.error.HTTPError as e:
            elapsed = time.time() - start
            body = ""
            try:
                body = e.read().decode()[:200]
            except Exception:
                pass
            results.append(CheckResult(
                name=f"list_tasks:{rt.name}", passed=False, elapsed_s=elapsed,
                error=f"HTTP {e.code} after {elapsed:.1f}s: {body}",
            ))
        except Exception as exc:
            elapsed = time.time() - start
            results.append(CheckResult(
                name=f"list_tasks:{rt.name}", passed=False, elapsed_s=elapsed,
                error=f"{type(exc).__name__}: {exc}",
            ))
    return results


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"


def print_summary(results: List[CheckResult]) -> None:
    name_w = max((len(r.name) for r in results), default=10)
    name_w = max(name_w, 6)
    header = f"{'Check':<{name_w}}  {'Status':>6}  {'Time':>8}  Detail"
    sep = "-" * len(header.expandtabs())
    print(f"\n{sep}")
    print(header)
    print(sep)
    for r in results:
        status = _PASS if r.passed else _FAIL
        detail = r.error if r.error else (r.detail or "")
        print(f"{r.name:<{name_w}}  {status:>15}  {r.elapsed_s:>7.1f}s  {detail}")
    print(sep)
    passed = sum(1 for r in results if r.passed)
    print(f"\n{passed}/{len(results)} checks passed.\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Fallback smoke test user UUID (used if --username and OPENCODE_SMOKE_TEST_USER
# are both unset). Created during the initial us-east-1 deployment; fresh pools
# in other regions won't have it, so set --username or OPENCODE_SMOKE_TEST_USER.
POOL_A_TEST_USER = "a4c8f428-f031-7072-7229-b7574ea6eeaf"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post-deploy smoke tests for the unified AgentCore MCP runtime via Gateway.",
    )
    parser.add_argument("--region", required=True)
    parser.add_argument("--profile", default=None)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--username",
        default=None,
        help=(
            "Cognito username (email) of the smoke-test user in the Pool A "
            "user pool. If omitted, defaults to the OPENCODE_SMOKE_TEST_USER "
            "env var, then to the hardcoded fallback."
        ),
    )
    parser.add_argument("--checks", nargs="*", default=None,
                        help=f"Available: {', '.join(_CHECKS.keys())}")
    args = parser.parse_args()

    import os as _os
    username = (
        args.username
        or _os.environ.get("OPENCODE_SMOKE_TEST_USER")
        or POOL_A_TEST_USER
    )

    if args.checks:
        for name in args.checks:
            if name not in _CHECKS:
                print(f"ERROR: Unknown check '{name}'. Available: {', '.join(_CHECKS.keys())}")
                return 1

    checks_to_run = args.checks or list(_CHECKS.keys())

    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    session = boto3.Session(**session_kwargs)

    print("Discovering infrastructure...")
    cfn = session.client("cloudformation")

    gateway_url = get_stack_output(cfn, "OpenCodeGateway", "GatewayUrl")
    print(f"  Gateway URL: {gateway_url}")

    # Read Cognito config from stack outputs (not hardcoded)
    user_pool_id = get_stack_output(cfn, "OpenCodeSecurity", "UserPoolId")
    client_id = get_stack_output(cfn, "OpenCodeSecurity", "UserPoolClientId")

    print("\nAcquiring Pool A Cognito JWT...")
    jwt_token = acquire_cognito_jwt(
        session, user_pool_id, client_id, username,
    )
    print(f"  JWT acquired successfully (user: {username}).")

    runtimes = [
        RuntimeInfo(
            name="opencode",
            expected_tool_count=6,
            expected_tool_names=[
                "opencode___code",
                "opencode___run_coding_task",
                "opencode___connect_git_host",
                "opencode___get_task_status",
                "opencode___list_tasks",
                "opencode___cancel_task",
            ],
        ),
    ]

    ctx = SmokeContext(
        session=session, region=args.region, timeout=args.timeout,
        gateway_url=gateway_url, jwt_token=jwt_token,
        runtimes=runtimes,
    )

    all_results: List[CheckResult] = []
    for check_name in checks_to_run:
        print(f"\nRunning: {check_name} ...")
        try:
            all_results.extend(_CHECKS[check_name](ctx))
        except Exception as exc:
            all_results.append(CheckResult(
                name=check_name, passed=False,
                error=f"Crashed: {type(exc).__name__}: {exc}",
            ))

    print_summary(all_results)
    return 0 if all(r.passed for r in all_results) else 1


if __name__ == "__main__":
    sys.exit(main())
