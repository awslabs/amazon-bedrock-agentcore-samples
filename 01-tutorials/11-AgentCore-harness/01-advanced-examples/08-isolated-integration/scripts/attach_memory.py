#!/usr/bin/env python3
"""Bind an AgentCore Memory resource to an existing Harness via
``UpdateHarness``, configuring retrieval for all four default strategies
(SEMANTIC, USER_PREFERENCE, SUMMARIZATION, EPISODIC).

Why this script exists
----------------------
When ``agentcore deploy`` provisions a Harness with a ``memory:`` block in
its project config, it creates the memory resource but does **not**
attach the memory to the harness on the control-plane side. ``GetHarness``
reports ``"memory": {}`` on the live harness until you run this script
(or an equivalent API call).

Without the binding, conversational turns are not persisted as memory
events, which means the asynchronous strategies (SEMANTIC etc.) have no
input to extract from. Running this once after deploy wires things up.

Retrieval config
----------------
The service retrieval config is a map keyed by namespace template. The
defaults here (topK=5 for users, topK=3 for session-scoped strategies)
are sensible starting points. Adjust with CLI flags if you need different
behavior for your use case.

Python compatibility: 3.12+.
"""

from __future__ import annotations

import argparse
import json
import sys

import boto3
from botocore.exceptions import ClientError
from botocore.parsers import ResponseParserError

DEFAULT_RETRIEVAL_CONFIG = {
    "/users/{actorId}/facts": {"topK": 5, "relevanceScore": 0.3},
    "/users/{actorId}/preferences": {"topK": 5, "relevanceScore": 0.3},
    "/summaries/{actorId}/{sessionId}": {"topK": 3, "relevanceScore": 0.3},
    "/episodes/{actorId}/{sessionId}": {"topK": 3, "relevanceScore": 0.3},
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Attach an AgentCore Memory resource to a Harness.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--harness-id",
        required=True,
        help="Harness ID to attach memory to.",
    )
    p.add_argument(
        "--memory-arn",
        required=True,
        help="ARN of the AgentCore Memory resource to bind.",
    )
    p.add_argument(
        "--messages-count",
        type=int,
        default=20,
        help="How many recent messages to inject into prompts (default: 20).",
    )
    p.add_argument(
        "--retrieval-config-file",
        help=(
            "Optional path to a JSON file overriding the default retrieval "
            "config. Structure: a dict keyed by namespace template whose "
            "values have 'topK' and 'relevanceScore'."
        ),
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

    retrieval_config = DEFAULT_RETRIEVAL_CONFIG
    if args.retrieval_config_file:
        try:
            with open(args.retrieval_config_file, encoding="utf-8") as f:
                retrieval_config = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"error: could not load retrieval-config-file: {e}", file=sys.stderr)
            return 2

    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    session = boto3.Session(**session_kwargs)
    cp = session.client("bedrock-agentcore-control")

    payload = {
        "harnessId": args.harness_id,
        "memory": {
            "optionalValue": {
                "agentCoreMemoryConfiguration": {
                    "arn": args.memory_arn,
                    "messagesCount": args.messages_count,
                    "retrievalConfig": retrieval_config,
                }
            }
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
        print("UpdateHarness likely accepted (HTTP 200; known preview quirk on "
              "tagged-union response fields):")
        print(f"  {e}")
        print()
        print("Run verify_harness.py to confirm the memory block is now bound.")
        return 0
    except ClientError as e:
        err = e.response.get("Error", {})
        print("UpdateHarness REJECTED:", file=sys.stderr)
        print(f"  Code:    {err.get('Code')}", file=sys.stderr)
        print(f"  Message: {err.get('Message')}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
