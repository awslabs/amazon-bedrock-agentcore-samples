#!/usr/bin/env python3
"""
Set PERMANENT passwords for the Cognito test personas (test/demo convenience).

⚠️  DEMO DETERMINISM ONLY — NOT PRODUCTION PRACTICE.
    This helper calls AdminSetUserPassword(Permanent=True) so the multi-user
    isolation test (07-optional-multi-user-isolation-test.ipynb) and the manual
    Streamlit walkthrough (08) can log in as each persona deterministically,
    without an interactive first-login / NEW_PASSWORD_REQUIRED dance.

    A REAL deployment MUST NOT do this. Production should use the Cognito
    first-login flow (NEW_PASSWORD_REQUIRED), the hosted UI, or SRP — and enable
    MFA. NEVER ship a shared or hardcoded password. This file therefore does NOT
    hardcode a password: it reads LAKEHOUSE_TEST_PASSWORD from the environment,
    or generates a random policy-compliant one at runtime and returns it in
    memory to the caller (it is never printed or written to disk).

    It is deliberately kept OUT of setup_cognito.py's happy path so the primary
    tutorial still models the production first-login flow; it is invoked only by
    the optional isolation-test prep.

Usage (standalone):
    python set_test_user_passwords.py         # generates a random password (not shown)
    LAKEHOUSE_TEST_PASSWORD=... python set_test_user_passwords.py

Usage (imported, e.g. from notebook 07 prep):
    from set_test_user_passwords import set_test_user_passwords, TEST_PERSONAS
    password = set_test_user_passwords(ssm_client, cognito_client)  # in-memory only
"""

import os
import secrets
import string
import sys

import boto3

# The five seeded personas (created by setup_cognito.py create_test_users).
TEST_PERSONAS = [
    "policyholder001@example.com",
    "policyholder002@example.com",
    "adjuster001@example.com",
    "adjuster002@example.com",
    "admin@example.com",
]


def _generate_password() -> str:
    """Generate a random password satisfying the pool policy
    (>=8, upper, lower, digit, symbol). Never printed."""
    aln = string.ascii_letters + string.digits
    body = "".join(secrets.choice(aln) for _ in range(20))
    # Guarantee one of each required class.
    return "Aa1!" + body


def set_test_user_passwords(ssm_client, cognito_client, password: str | None = None) -> str:
    """
    Set a PERMANENT password (Permanent=True) for each test persona so they are
    CONFIRMED and usable with ADMIN_USER_PASSWORD_AUTH / SRP.

    password: if None, read LAKEHOUSE_TEST_PASSWORD env or generate a random one.
    Returns the password IN MEMORY (never printed) so the caller can mint tokens.
    """
    if password is None:
        password = os.environ.get("LAKEHOUSE_TEST_PASSWORD") or _generate_password()

    pool_id = ssm_client.get_parameter(Name="/app/lakehouse-agent/cognito-user-pool-id")["Parameter"]["Value"]

    set_count = 0
    for username in TEST_PERSONAS:
        try:
            cognito_client.admin_set_user_password(
                UserPoolId=pool_id,
                Username=username,
                Password=password,
                Permanent=True,
            )
            set_count += 1
        except Exception as e:  # keep going; report per-user without leaking the password
            print(f"   ⚠️  Could not set password for {username}: {type(e).__name__}")
    # Status only — NEVER print the password value.
    print(f"✅ Set permanent password for {set_count}/{len(TEST_PERSONAS)} test personas (value not shown).")
    return password


def main():
    region = boto3.Session().region_name or "us-east-1"
    ssm = boto3.client("ssm", region_name=region)
    cognito = boto3.client("cognito-idp", region_name=region)
    set_test_user_passwords(ssm, cognito)
    print("   (Demo convenience only — production must use first-login/hosted-UI/SRP + MFA.)")


if __name__ == "__main__":
    sys.exit(main())
