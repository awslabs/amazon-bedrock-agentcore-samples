#!/usr/bin/env python3
"""Inspect an AgentCore Memory resource: list actors, list memory
records for the global-scoped strategies (SEMANTIC, USER_PREFERENCE),
and optionally list session-scoped records (SUMMARIZATION, EPISODIC)
for a given session.

Why this script exists
----------------------
In the preview window, the runtime persists memory events under
``actorId = "default"`` regardless of any user/session IDs you pass at
invocation time. So the "expected" namespaces (e.g.
``/users/<your-user-id>/facts``) will appear empty unless you query
the actual actor — which is almost always just ``default``.

This script:

1. Calls ``list_actors`` to discover what actor IDs exist in the memory
   resource, printing each.
2. For each actor, lists ``/users/<actor>/facts`` and
   ``/users/<actor>/preferences`` (these are not session-scoped).
3. If ``--session-id`` is provided, also lists
   ``/summaries/<actor>/<session>`` and
   ``/episodes/<actor>/<session>`` for each actor.

Pair this with ``seed_memory.py`` (run ~60-90 seconds after seeding) to
watch the asynchronous extractors produce records.

Python compatibility: 3.12+.
"""

from __future__ import annotations

import argparse
import sys

import boto3
from botocore.exceptions import ClientError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="List AgentCore Memory records across all actors and namespaces.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--memory-id",
        required=True,
        help="Memory ID (e.g. <Project>_<HarnessName>Memory-YYYYYYY).",
    )
    p.add_argument(
        "--session-id",
        default=None,
        help=(
            "Optional session ID. When present, session-scoped namespaces "
            "(/summaries/<actor>/<session>, /episodes/<actor>/<session>) "
            "are inspected in addition to the global ones."
        ),
    )
    p.add_argument(
        "--actor-id",
        default=None,
        help=(
            "Only inspect this actor ID. By default, all actors discovered "
            "via list_actors are inspected."
        ),
    )
    p.add_argument(
        "--max-text",
        type=int,
        default=250,
        help=(
            "Maximum characters of each record's content.text to print "
            "(default: 250)."
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


def list_records(dp, memory_id: str, namespace: str, max_text: int) -> None:
    print(f"\n=== {namespace} ===")
    try:
        resp = dp.list_memory_records(memoryId=memory_id, namespace=namespace)
    except ClientError as e:
        err = e.response.get("Error", {})
        print(f"  ERROR: {err.get('Code')}: {err.get('Message')}")
        return
    records = resp.get("memoryRecordSummaries", [])
    if not records:
        print("  (empty)")
        return
    for r in records:
        rid = r.get("memoryRecordId", "<no-id>")
        content = r.get("content", {})
        text = content.get("text", "")
        print(f"  {rid}")
        print(f"    {text[:max_text]}")


def main() -> int:
    args = build_parser().parse_args()

    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    session = boto3.Session(**session_kwargs)
    dp = session.client("bedrock-agentcore")

    # Discover actors (unless one was passed explicitly).
    if args.actor_id:
        actors = [args.actor_id]
        print(f"Actors (provided): {actors}")
    else:
        try:
            resp = dp.list_actors(memoryId=args.memory_id)
        except ClientError as e:
            err = e.response.get("Error", {})
            print(f"list_actors failed: {err.get('Code')}: {err.get('Message')}",
                  file=sys.stderr)
            return 1
        actors = [
            a.get("actorId")
            for a in resp.get("actorSummaries", [])
            if a.get("actorId")
        ]
        if not actors:
            print("No actors found in memory resource. Nothing to inspect.")
            return 0
        print(f"Actors discovered: {actors}")

    for actor in actors:
        print(f"\n\n========== actor '{actor}' ==========")
        list_records(dp, args.memory_id, f"/users/{actor}/facts", args.max_text)
        list_records(dp, args.memory_id, f"/users/{actor}/preferences", args.max_text)
        if args.session_id:
            list_records(dp, args.memory_id,
                         f"/summaries/{actor}/{args.session_id}", args.max_text)
            list_records(dp, args.memory_id,
                         f"/episodes/{actor}/{args.session_id}", args.max_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
