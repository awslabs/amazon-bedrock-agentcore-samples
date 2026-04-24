#!/usr/bin/env python3
"""Inspect the live state of an AgentCore Harness, bypassing the
boto3 response parser.

Why this script exists
----------------------
In the AgentCore preview window, ``GetHarness`` sometimes returns a
``HarnessMemoryConfiguration`` tagged-union with no member populated.
Public boto3 rejects this as invalid (``ResponseParserError``), so
``control.get_harness(...)`` and ``aws bedrock-agentcore-control
get-harness`` both fail with a parsing error even when the service
returned a valid HTTP 200 body.

This script works around that by:

1. Building the request with ``botocore.awsrequest.AWSRequest``.
2. Signing it with ``SigV4Auth`` using the signing service name
   ``bedrock-agentcore`` (note: the hostname is
   ``bedrock-agentcore-control.<region>.amazonaws.com`` but the service
   rejects requests signed with ``bedrock-agentcore-control``; both
   hostnames share one SigV4 signing service).
3. Sending it with botocore's bundled ``urllib3`` client.
4. Parsing the JSON body directly — no botocore response parser
   involved, so the tagged-union quirk doesn't matter.

Python compatibility: 3.12+.
"""

from __future__ import annotations

import argparse
import json
import sys

import boto3
import urllib3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Read the live AgentCore Harness state via raw signed HTTPS GET.",
    )
    p.add_argument("--harness-id", required=True, help="Harness ID to fetch.")
    p.add_argument("--region", default="us-west-2", help="AWS region.")
    p.add_argument("--profile", default=None, help="AWS profile name.")
    p.add_argument(
        "--field",
        choices=["all", "network", "memory", "status"],
        default="all",
        help="Which part of the response to print (default: all).",
    )
    return p


def main() -> int:
    args = build_parser().parse_args()

    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    session = boto3.Session(**session_kwargs)
    creds = session.get_credentials()
    if creds is None:
        print(
            "error: no AWS credentials available for the given profile/env",
            file=sys.stderr,
        )
        return 2
    frozen = creds.get_frozen_credentials()

    url = (
        f"https://bedrock-agentcore-control.{args.region}.amazonaws.com"
        f"/harnesses/{args.harness_id}"
    )
    req = AWSRequest(method="GET", url=url, data=b"", headers={})
    # Sign with the service name "bedrock-agentcore" — NOT "bedrock-agentcore-control".
    # The service rejects the latter even though it's what the hostname says.
    SigV4Auth(frozen, "bedrock-agentcore", args.region).add_auth(req)
    prepared = req.prepare()

    http = urllib3.PoolManager()
    response = http.request("GET", prepared.url, headers=dict(prepared.headers))

    print(f"HTTP {response.status}")
    body = response.data.decode("utf-8", errors="replace")
    if response.status != 200:
        print(body)
        return 1

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        print(body)
        return 1

    harness = parsed.get("harness", parsed)
    if args.field == "all":
        print(json.dumps(harness, indent=2, default=str))
    elif args.field == "status":
        print(harness.get("status"))
    elif args.field == "network":
        netcfg = (
            harness.get("environment", {})
            .get("agentCoreRuntimeEnvironment", {})
            .get("networkConfiguration", {})
        )
        print(json.dumps(netcfg, indent=2))
    elif args.field == "memory":
        print(json.dumps(harness.get("memory", {}), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
