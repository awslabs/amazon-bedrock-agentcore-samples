# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Role-Based Access Control - deploy verification and test.

Verifies that role-based access control (RBAC) works end-to-end against a
deployed Amazon Bedrock AgentCore agent + MCP server stack:

  1. Sets permanent passwords for the two pre-created Cognito users
     (CDK creates them in FORCE_CHANGE_PASSWORD status).
  2. Waits for the agent and MCP server containers to start.
  3. Authenticates as each user, invokes the agent, and checks that role-gated
     tools are reachable only by the matching role.

Test matrix:

    | User   | Role        | get_stock_price | get_employee_count | Public |
    |--------|-------------|:---------------:|:------------------:|:------:|
    | user-a | FinanceUser | Allowed         | Denied             | Yes    |
    | user-b | HRUser      | Denied          | Allowed            | Yes    |

Usage:
    # Deploy the stack first (see README "Deployment"), then:
    python deploy_and_test_rbac.py --password '<password>' [--outputs ../outputs.json]

    # The password may also be supplied via the TEST_USER_PASSWORD environment
    # variable, or entered interactively when neither is provided. It must meet
    # the Cognito password policy (12+ chars, upper, lower, digit, symbol).

Prerequisites:
    - The CDK stack is deployed and outputs.json has been written
      (cdk deploy --outputs-file outputs.json).
    - AWS credentials configured with access to the deployed account/region.

Exit status:
    0 if every RBAC test passes, 1 otherwise.
"""

import argparse
import getpass
import json
import os
import sys
import time
import urllib.parse
import uuid

import boto3
import requests

REGION = "ap-southeast-2"
STACK_NAME = "AgentCoreCICDStack-dev"
TEST_USERS = ("user-a", "user-b")
CONTAINER_WARMUP_SECONDS = 30

# Test matrix: (user, prompt, must_contain, must_not_contain, description)
TEST_CASES = [
    # Public tools - accessible to both users
    ("user-a", "What is the current time in UTC?", ["202"], [], "user-a: get_current_datetime (public)"),
    ("user-b", "How much is 15 * 7?", ["105"], [], "user-b: calculator (public)"),
    # get_stock_price - only FinanceUser
    ("user-a", "What is the stock price of AAPL?", ["175.50"], [], "user-a (FinanceUser): get_stock_price ALLOWED"),
    ("user-b", "What is the stock price of AAPL?", [], ["175.50"], "user-b (HRUser): get_stock_price DENIED"),
    # get_employee_count - only HRUser
    ("user-b", "How many employees are in engineering?", ["150"], [], "user-b (HRUser): get_employee_count ALLOWED"),
    (
        "user-a",
        "How many employees are in engineering?",
        [],
        ["150"],
        "user-a (FinanceUser): get_employee_count DENIED",
    ),
]


def load_outputs(outputs_path: str) -> dict:
    """Load the CDK stack outputs written by `cdk deploy --outputs-file`."""
    with open(outputs_path) as f:
        return json.load(f)[STACK_NAME]


def set_user_passwords(pool_id: str, password: str) -> None:
    """Set a permanent password for each test user.

    CDK creates user-a and user-b in FORCE_CHANGE_PASSWORD status; they cannot
    authenticate until a permanent password is set.
    """
    cog = boto3.client("cognito-idp", region_name=REGION)
    for user in TEST_USERS:
        cog.admin_set_user_password(UserPoolId=pool_id, Username=user, Password=password, Permanent=True)
        print(f"Password set for {user}")


def get_access_token(pool_id: str, client_id: str, username: str, password: str) -> str:
    """Authenticate a Cognito user and return their access token."""
    cog = boto3.client("cognito-idp", region_name=REGION)
    resp = cog.admin_initiate_auth(
        UserPoolId=pool_id,
        ClientId=client_id,
        AuthFlow="ADMIN_NO_SRP_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )
    return resp["AuthenticationResult"]["AccessToken"]


def invoke(agent_arn: str, prompt: str, token: str, timeout: int = 120) -> dict:
    """Invoke the agent via HTTPS with a Bearer token.

    Each call uses a unique session ID to get a fresh container.
    """
    escaped = urllib.parse.quote(agent_arn, safe="")
    url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{escaped}/invocations?qualifier=DEFAULT"
    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": str(uuid.uuid4()),
        },
        data=json.dumps({"prompt": prompt}),
        timeout=timeout,
    )
    return {"status": r.status_code, "body": r.text}


def check(result: dict, should_contain=None, should_not_contain=None) -> bool:
    """Check if the response contains/excludes expected strings."""
    body = result["body"].lower()
    ok = result["status"] == 200
    for s in should_contain or []:
        if s.lower() not in body:
            ok = False
    for s in should_not_contain or []:
        if s.lower() in body:
            ok = False
    return ok


def run_tests(agent_arn: str, tokens: dict) -> tuple[int, int]:
    """Run the RBAC test matrix and return (passed, failed) counts."""
    passed = failed = 0
    for user, prompt, should_contain, should_not_contain, desc in TEST_CASES:
        print(f"\n{'─' * 60}")
        print(f"  {desc}")
        print(f"  Q: {prompt}")
        start = time.time()
        try:
            result = invoke(agent_arn, prompt, tokens[user])
            elapsed = time.time() - start
            snippet = result["body"][:200].replace("\n", " ")
            print(f"  A: [{result['status']}] ({elapsed:.1f}s) {snippet}")
            if check(result, should_contain, should_not_contain):
                print("  ✅ PASS")
                passed += 1
            else:
                print("  ❌ FAIL")
                failed += 1
        except Exception as e:
            print(f"  ❌ FAIL - {e}")
            failed += 1
    return passed, failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy verification + RBAC tests for the AgentCore eval sample.")
    parser.add_argument(
        "--outputs",
        default="../outputs.json",
        help="Path to the CDK outputs file (default: ../outputs.json).",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("TEST_USER_PASSWORD"),
        help="Password to set for the test users (or set TEST_USER_PASSWORD; prompted if omitted).",
    )
    args = parser.parse_args()

    outputs = load_outputs(args.outputs)
    pool_id = outputs["SharedUserPoolId"]
    client_id = outputs["UserClientId"]
    agent_arn = outputs["AgentRuntimeArn"]

    password = args.password or getpass.getpass("Enter password for test users: ")

    # Step 1: set permanent passwords for the pre-created users.
    set_user_passwords(pool_id, password)

    # Step 2: give the agent and MCP server containers time to start.
    print(f"\nWaiting {CONTAINER_WARMUP_SECONDS}s for containers to start...")
    time.sleep(CONTAINER_WARMUP_SECONDS)

    # Step 3: authenticate both users and run the RBAC test matrix.
    tokens = {user: get_access_token(pool_id, client_id, user, password) for user in TEST_USERS}
    passed, failed = run_tests(agent_arn, tokens)

    print(f"\n{'═' * 60}")
    print(f"  Results: {passed} passed, {failed} failed, {passed + failed} total")
    print(f"{'═' * 60}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
