#!/usr/bin/env python3
"""Seed an AgentCore Harness with conversational turns via the
data-plane ``invoke_harness`` API so Memory events are written and
extractors have material to work with.

Why this script exists
----------------------
The CLI's ``agentcore invoke`` goes through a runtime invocation path
that, in the current preview, is less reliable at producing the Memory
events downstream extractors consume. The data-plane ``invoke_harness``
API is what the harness sample notebooks use, and what production
clients (SDKs, FastAPI proxies, etc.) are built on top of — it writes
events into the bound memory resource reliably.

This script takes one or more prompts, runs them as a multi-turn
conversation under a single ``runtimeSessionId`` so SUMMARIZATION /
EPISODIC strategies have intra-session context to work with, and prints
each streamed response.

Pair this with ``inspect_memory.py`` (run after ~60-90 seconds) to see
the extracted records.

Python compatibility: 3.12+.
"""

from __future__ import annotations

import argparse
import sys
import uuid

import boto3
from botocore.exceptions import ClientError

DEFAULT_MODEL_ID = "global.anthropic.claude-sonnet-4-6"

# Two turns that give the extractors something to pull out:
# - a fact (name / job)
# - a preference (bullet points)
# - a follow-up that lets the model demonstrate memory retrieval within
#   the same session
DEFAULT_PROMPTS = [
    "Hi, my name is Raj and I work on AWS AgentCore. I prefer bullet-point answers.",
    "Quick check — can you confirm what you know about me?",
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Seed memory by invoking a harness with one or more prompts in a "
            "single runtimeSession, via the data-plane invoke_harness API."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--harness-arn",
        required=True,
        help="Full ARN of the harness.",
    )
    p.add_argument(
        "--prompt",
        action="append",
        metavar="TEXT",
        help=(
            "Prompt to send. Repeat to add multiple turns within the same "
            "session. If omitted, a small default pair is used."
        ),
    )
    p.add_argument(
        "--session-id",
        default=None,
        help="Runtime session ID (default: auto-generated UUID).",
    )
    p.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        help=f"Bedrock model ID (default: {DEFAULT_MODEL_ID}).",
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


def stream_and_print(resp) -> None:
    """Stream tokens to stdout from an invoke_harness response."""
    for event in resp.get("stream", []):
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            text = delta.get("text")
            if text:
                sys.stdout.write(text)
                sys.stdout.flush()
        elif "messageStop" in event:
            print()
            return


def main() -> int:
    args = build_parser().parse_args()
    prompts = args.prompt or DEFAULT_PROMPTS
    session_id = args.session_id or str(uuid.uuid4()).upper()

    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    session = boto3.Session(**session_kwargs)
    dp = session.client("bedrock-agentcore")

    print(f"runtimeSessionId: {session_id}")
    print(f"harnessArn:       {args.harness_arn}")
    print(f"modelId:          {args.model_id}")
    print(f"turns:            {len(prompts)}")
    print()

    for idx, text in enumerate(prompts, start=1):
        print(f"--- turn {idx}: {text}")
        try:
            resp = dp.invoke_harness(
                harnessArn=args.harness_arn,
                runtimeSessionId=session_id,
                messages=[{"role": "user", "content": [{"text": text}]}],
                model={"bedrockModelConfig": {"modelId": args.model_id}},
            )
        except ClientError as e:
            err = e.response.get("Error", {})
            print(f"\ninvoke_harness failed on turn {idx}:", file=sys.stderr)
            print(f"  Code:    {err.get('Code')}", file=sys.stderr)
            print(f"  Message: {err.get('Message')}", file=sys.stderr)
            return 1
        stream_and_print(resp)
        print()

    print()
    print("Done. Wait ~60-90 seconds for extractors, then run:")
    print("  python scripts/inspect_memory.py --memory-id <MEMORY_ID> \\")
    print(f"      --session-id {session_id} \\")
    print(f"      --region {args.region} --profile {args.profile or '<your-profile>'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
