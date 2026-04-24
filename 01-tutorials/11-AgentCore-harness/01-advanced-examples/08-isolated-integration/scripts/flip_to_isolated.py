#!/usr/bin/env python3
"""Flip an existing AgentCore Harness from ``networkMode: VPC`` to
``networkMode: ISOLATED`` via a direct ``UpdateHarness`` call.

Why this script exists
----------------------
The ``agentcore`` CLI (v1.0.0-preview.1 as of this writing) accepts only
``PUBLIC`` and ``VPC`` for ``--network-mode`` — both in its flag parser and
in its ``harness.json`` schema validator. The service API, however,
enumerates ``PUBLIC``, ``VPC``, and ``ISOLATED`` as valid values for
``networkMode`` on both ``CreateHarness`` and ``UpdateHarness``.

Workflow for the 08 tutorial:

1. ``agentcore create --network-mode VPC ...`` + ``agentcore deploy``
   → creates a VPC-mode harness attached to your isolated VPC infra.
2. Run this script → calls ``UpdateHarness`` with
   ``networkMode=ISOLATED`` (and the same subnets/SG) to flip the
   API-level network mode. Infrastructure doesn't change; only the
   harness's mode declaration does.
3. Verify with ``verify_harness.py``.

The microVM continues to run in the same private subnets with the same
security group — this call only updates the API-level declaration. The
isolation guarantees come from your infra (no IGW, no NAT, PrivateLink
endpoints), which are already in place from the earlier agentcore deploy.

Python compatibility: 3.12+.
"""

from __future__ import annotations

import argparse
import json
import sys

import boto3
from botocore.exceptions import ClientError
from botocore.parsers import ResponseParserError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Flip an AgentCore Harness to networkMode=ISOLATED via UpdateHarness."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--harness-id",
        required=True,
        help="Harness ID (e.g. <Project>_<HarnessName>-XXXXXXX).",
    )
    p.add_argument(
        "--subnets",
        required=True,
        help="Comma-separated list of private subnet IDs the harness runs in.",
    )
    p.add_argument(
        "--security-groups",
        required=True,
        help="Comma-separated list of security group IDs.",
    )
    p.add_argument(
        "--region",
        default="us-west-2",
        help="AWS region (default: us-west-2).",
    )
    p.add_argument(
        "--profile",
        default=None,
        help="AWS profile name (default: environment default).",
    )
    return p


def main() -> int:
    args = build_parser().parse_args()

    subnets = [s.strip() for s in args.subnets.split(",") if s.strip()]
    security_groups = [s.strip() for s in args.security_groups.split(",") if s.strip()]
    if not subnets or not security_groups:
        print(
            "error: --subnets and --security-groups must each list at least one ID",
            file=sys.stderr,
        )
        return 2

    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    session = boto3.Session(**session_kwargs)
    cp = session.client("bedrock-agentcore-control")

    # Note: we do NOT include requireServiceS3Endpoint here. The public boto3
    # service model for VpcConfig in this preview window doesn't know about
    # that field yet. Omitting it lets the service apply its default; the S3
    # gateway endpoint in your VPC satisfies the underlying requirement
    # regardless of whether this flag is set.
    payload = {
        "harnessId": args.harness_id,
        "environment": {
            "agentCoreRuntimeEnvironment": {
                "networkConfiguration": {
                    "networkMode": "ISOLATED",
                    "networkModeConfig": {
                        "subnets": subnets,
                        "securityGroups": security_groups,
                    },
                },
            },
        },
    }
    print("UpdateHarness payload:")
    print(json.dumps(payload, indent=2))
    print()

    try:
        cp.update_harness(**payload)
        print("UpdateHarness accepted (response parsed cleanly).")
        return 0
    except ResponseParserError as e:
        # In preview, GetHarness / UpdateHarness responses sometimes carry a
        # tagged-union (HarnessMemoryConfiguration) with no members populated.
        # The public boto3 parser rejects that, but the service HAS accepted
        # the request (HTTP 200) by the time parsing runs. Treat as success.
        print("UpdateHarness likely accepted (HTTP 200; client-side parse error "
              "on a tagged-union response field is a known preview quirk):")
        print(f"  {e}")
        print()
        print("Run verify_harness.py to confirm the live networkMode.")
        return 0
    except ClientError as e:
        err = e.response.get("Error", {})
        print("UpdateHarness REJECTED by the service:", file=sys.stderr)
        print(f"  Code:    {err.get('Code')}", file=sys.stderr)
        print(f"  Message: {err.get('Message')}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
