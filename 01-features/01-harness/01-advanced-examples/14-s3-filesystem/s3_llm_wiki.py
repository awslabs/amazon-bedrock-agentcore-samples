#!/usr/bin/env python3
"""
S3-Backed LLM Wiki (a persistent, compounding markdown wiki)

A use case for the S3 filesystem mount: an agent that maintains its own
persistent markdown wiki. It implements the pattern Andrej Karpathy describes in
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f :
instead of re-deriving answers from raw documents on every query (classic RAG),
an LLM agent **incrementally builds and maintains a persistent markdown wiki** —
knowledge is compiled once and kept current, becoming a compounding artifact.

(Note: this is a self-maintained markdown wiki on the agent's filesystem — it is
unrelated to the Amazon Bedrock Knowledge Bases feature.)

Why the harness S3 mount is a natural fit: the wiki must outlive any single
session and be shared across invocations. Mounting an S3 Files access point at
`/mnt/wiki` gives the agent a normal POSIX directory that is backed by S3, so the
wiki it writes in one session is still there in the next — and the agent picks up
exactly where it left off.

The three layers from the gist, mapped onto the mount:

    /mnt/wiki/
      sources/   raw, immutable inputs (the agent reads, never edits)
      pages/     LLM-owned markdown: summaries, entity pages, concept pages
      AGENTS.md  the schema — tells the agent how the wiki is organized
      index.md   catalog of wiki pages
      log.md     append-only chronological record

Three operations, each a separate session to PROVE persistence across the
microVM boundary:

    ingest   read a raw source, integrate it across the wiki (create/update pages)
    query    answer a question from the wiki, filing the answer back as a page
    lint     health-check: find contradictions, stale claims, orphan pages

An S3 Files mount requires the Harness to run in **VPC network mode** (pass the
subnet(s) and security group(s) that can reach the access point's mount target).

Usage:
    # Full demo: bootstrap schema, ingest two sources, query, lint
    python s3_llm_wiki.py \\
        --access-point-arn arn:aws:s3files:us-west-2:111122223333:file-system/fs-abc/access-point/fsap-def \\
        --subnet-ids subnet-0abc1234 --security-group-ids sg-0def5678

    # Run a single operation against an existing wiki harness/mount
    python s3_llm_wiki.py --access-point-arn arn:aws:s3files:... \\
        --subnet-ids subnet-0abc1234 --security-group-ids sg-0def5678 \\
        --op query -m "What do we know about retrieval-augmented generation?"

    # Custom mount path
    python s3_llm_wiki.py --access-point-arn ... --subnet-ids ... --security-group-ids ... --mount-path /mnt/notes

    # Keep the harness after the demo
    python s3_llm_wiki.py --access-point-arn ... --subnet-ids ... --security-group-ids ... --skip-cleanup

    # See all options
    python s3_llm_wiki.py --help
"""

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import boto3
import botocore.exceptions

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.iam import create_harness_role, ROLE_NAME
from utils.client import get_agentcore_client, get_agentcore_control_client

REGION = os.getenv("AWS_DEFAULT_REGION")


# ── Constants ───────────────────────────────────────────────────────────────
DEFAULT_MODEL = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_MOUNT_PATH = "/mnt/wiki"
S3_FILES_POLICY_NAME = "HarnessS3FilesAccess"
MOUNT_PATH_PATTERN = re.compile(r"^/mnt/[a-zA-Z0-9._-]+/?$")

HARNESS_POLL_INTERVAL = 5
HARNESS_POLL_TIMEOUT = 180

# Two tiny "raw sources" the agent ingests. In a real wiki these are papers,
# tickets, docs — here they're short so the demo runs fast.
SOURCES = {
    "rag-overview.md": (
        "# Retrieval-Augmented Generation (RAG)\n\n"
        "RAG retrieves relevant document chunks at query time and feeds them to an "
        "LLM as context. Strengths: fresh data, source attribution. Weaknesses: "
        "re-derives understanding on every query, sensitive to chunking and "
        "retrieval quality."
    ),
    "wiki-pattern.md": (
        "# The LLM Wiki Pattern\n\n"
        "Instead of re-retrieving raw chunks per query, an LLM maintains a persistent "
        "markdown wiki: summaries, entity pages, and concept pages with cross-links. "
        "Knowledge is compiled once and kept current. Contrasts with RAG by making "
        "knowledge a compounding artifact rather than a per-query computation."
    ),
}


# ── CLI ─────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(
    description="Build a persistent, S3-backed LLM wiki with the harness.",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)
parser.add_argument("--access-point-arn", required=True, metavar="ARN",
                    help="S3 Files access point ARN to mount (arn:aws:s3files:...:access-point/fsap-...)")
parser.add_argument("--subnet-ids", required=True, nargs="+", metavar="SUBNET",
                    help="VPC subnet(s) that can reach the access point's mount target (NFS/2049)")
parser.add_argument("--security-group-ids", required=True, nargs="+", metavar="SG",
                    help="Security group(s) allowing NFS (2049) to the mount target")
parser.add_argument("--mount-path", default=DEFAULT_MOUNT_PATH, metavar="PATH",
                    help=f"Where to mount the wiki inside the VM (default: {DEFAULT_MOUNT_PATH})")
parser.add_argument("--op", choices=["all", "ingest", "query", "lint"], default="all",
                    help="Which operation to run (default: all — bootstrap, ingest, query, lint)")
parser.add_argument("--message", "-m", default="How does the LLM wiki pattern differ from RAG?",
                    help="Question for the query operation")
parser.add_argument("--model", default=DEFAULT_MODEL, metavar="MODEL_ID",
                    help=f"Bedrock model ID (default: {DEFAULT_MODEL})")
parser.add_argument("--role-arn", default=None, metavar="ARN",
                    help="Use an existing IAM execution role (must already allow the access point)")
parser.add_argument("--skip-cleanup", action="store_true", help="Keep the harness after the demo")
parser.add_argument("--raw-events", action="store_true", help="Print raw JSON streaming events")


# ── Helpers ─────────────────────────────────────────────────────────────────
def attach_s3_files_policy(role_name, access_point_arn):
    """Allow the execution role to validate and mount the S3 Files access point.

    * `s3files:GetAccessPoint` on `*` — the runtime validates this at harness
      create time. Keep it unscoped; a scoped/conditioned form is rejected at
      create with "Ensure the role has s3files:GetAccessPoint".
    * `s3files:ClientMount`/`ClientWrite` — used when the microVM mounts the
      access point; scoped to the file system with an AccessPointArn condition.
    """
    fs_arn = access_point_arn.split("/access-point/")[0]
    iam = boto3.client("iam")
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "S3FilesValidate",
                "Effect": "Allow",
                "Action": ["s3files:GetAccessPoint"],
                "Resource": "*",
            },
            {
                "Sid": "S3FilesClientMount",
                "Effect": "Allow",
                "Action": ["s3files:ClientMount", "s3files:ClientWrite"],
                "Resource": fs_arn,
                "Condition": {"ArnEquals": {"s3files:AccessPointArn": access_point_arn}},
            },
        ],
    }
    iam.put_role_policy(RoleName=role_name, PolicyName=S3_FILES_POLICY_NAME,
                        PolicyDocument=json.dumps(policy))
    print(f"  Attached S3 Files access policy: {S3_FILES_POLICY_NAME}")


def poll_harness_status(control, harness_id, target_status="READY", timeout=HARNESS_POLL_TIMEOUT):
    """Poll until a Harness reaches the target status or times out."""
    deadline = time.monotonic() + timeout
    while True:
        resp = control.get_harness(harnessId=harness_id)
        status = resp["harness"]["status"]
        print(f"  Harness status: {status}")
        if status == target_status:
            return resp
        if status in ("FAILED", "DELETE_FAILED"):
            reason = resp["harness"].get("failureReason", "")
            raise RuntimeError(f"Harness entered {status}. {reason}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"Harness not {target_status} after {timeout}s (current: {status})")
        time.sleep(HARNESS_POLL_INTERVAL)


def stream_turn(client, harness_arn, message, model_id, mount, raw=False):
    """Run one wiki operation in its OWN session (proves cross-session persistence)."""
    session_id = str(uuid.uuid4()).upper()
    system = (
        f"You maintain a persistent markdown wiki mounted at {mount}. "
        f"Layers: {mount}/sources (raw, read-only), {mount}/pages (your markdown pages), "
        f"{mount}/AGENTS.md (schema), {mount}/index.md (catalog), {mount}/log.md (append-only). "
        "Use your filesystem and shell tools to read and write files directly. "
        "Keep pages concise and cross-linked with [[wiki-links]]."
    )
    response = client.invoke_harness(
        harnessArn=harness_arn,
        runtimeSessionId=session_id,
        messages=[{"role": "user", "content": [{"text": message}]}],
        model={"bedrockModelConfig": {"modelId": model_id}},
        systemPrompt=[{"text": system}],
        timeoutSeconds=300,
    )
    full_text = ""
    try:
        for event in response["stream"]:
            if raw:
                print(json.dumps(event, default=str))
                continue
            if "contentBlockStart" in event:
                start = event["contentBlockStart"].get("start", {})
                if "toolUse" in start:
                    print(f"\n  [Tool: {start['toolUse'].get('name', '?')}]", flush=True)
            elif "contentBlockDelta" in event:
                delta = event["contentBlockDelta"].get("delta", {})
                if "text" in delta:
                    print(delta["text"], end="", flush=True)
                    full_text += delta["text"]
            elif "messageStop" in event:
                print()
            elif "internalServerException" in event:
                print(f"\n  Error: {event['internalServerException']}")
    except botocore.exceptions.EventStreamError:
        if not full_text:
            raise
    return full_text


def seed_sources(client, harness_arn, mount):
    """Write the raw source docs and bootstrap the schema into the mount (one session)."""
    session_id = str(uuid.uuid4()).upper()

    def run(cmd):
        resp = client.invoke_agent_runtime_command(
            agentRuntimeArn=harness_arn, runtimeSessionId=session_id, body={"command": cmd}
        )
        for event in resp["stream"]:
            if "chunk" in event and "contentDelta" in event["chunk"]:
                d = event["chunk"]["contentDelta"]
                if "stderr" in d:
                    print(d["stderr"], end="")

    run(f"mkdir -p {mount}/sources {mount}/pages")
    for name, body in SOURCES.items():
        # base64 to avoid any shell-quoting issues with the markdown body
        import base64
        b64 = base64.b64encode(body.encode()).decode()
        run(f"echo {b64} | base64 -d > {mount}/sources/{name}")
    # Bootstrap schema/index/log only if not present (idempotent for re-runs)
    run(f"test -f {mount}/AGENTS.md || printf '# Wiki Schema\\n\\nsources/ raw inputs. pages/ LLM pages. index.md catalog. log.md history.\\n' > {mount}/AGENTS.md")
    run(f"test -f {mount}/index.md || printf '# Index\\n' > {mount}/index.md")
    run(f"test -f {mount}/log.md || printf '# Log\\n' > {mount}/log.md")
    print(f"  Seeded {len(SOURCES)} source(s) and bootstrapped schema under {mount}")


# ── Main ────────────────────────────────────────────────────────────────────
def main(args=None):
    if args is None:
        args = parser.parse_args()

    if not MOUNT_PATH_PATTERN.match(args.mount_path):
        parser.error(f"--mount-path must look like /mnt/<name> (got: {args.mount_path})")

    control = get_agentcore_control_client()
    client = get_agentcore_client()
    mount = args.mount_path.rstrip("/")
    harness_id = None

    try:
        # ── Step 0: IAM role (with S3 access) ─────────────────────────
        print("=" * 60)
        print("Step 0: IAM execution role")
        print("=" * 60)
        if args.role_arn:
            role_arn = args.role_arn
            print(f"  Using provided role: {role_arn}")
            print("  (ensure it can access the S3 Files access point)")
        else:
            role_arn = create_harness_role()
            attach_s3_files_policy(ROLE_NAME, args.access_point_arn)
            print("  Waiting for IAM propagation...")
            time.sleep(10)

        # ── Step 1: Create harness with the wiki mounted (VPC mode) ───
        print("\n" + "=" * 60)
        print(f"Step 1: Create harness with the wiki mounted at {mount}")
        print("=" * 60)
        # S3 Files mounts require VPC network mode so the microVM can reach the
        # access point's mount target over your VPC.
        network = {
            "networkMode": "VPC",
            "networkModeConfig": {"subnets": args.subnet_ids, "securityGroups": args.security_group_ids},
        }
        filesystem = [{"s3FilesAccessPoint": {"accessPointArn": args.access_point_arn, "mountPath": mount}}]
        harness_name = f"S3LlmWiki_{uuid.uuid4().hex[:8]}"
        resp = control.create_harness(
            harnessName=harness_name,
            executionRoleArn=role_arn,
            environment={
                "agentCoreRuntimeEnvironment": {
                    "networkConfiguration": network,
                    "filesystemConfigurations": filesystem,
                }
            },
        )
        harness_id = resp["harness"]["harnessId"]
        harness_arn = resp["harness"]["arn"]
        print(f"  Harness ID:  {harness_id}")
        print(f"  Harness ARN: {harness_arn}")
        poll_harness_status(control, harness_id)

        # ── Step 2: Seed raw sources (separate session) ───────────────
        if args.op in ("all", "ingest"):
            print("\n" + "=" * 60)
            print("Step 2: Seed raw sources into the mount")
            print("=" * 60)
            seed_sources(client, harness_arn, mount)
            time.sleep(5)

        # ── Step 3: INGEST — compile sources into the wiki ────────────
        if args.op in ("all", "ingest"):
            print("\n" + "=" * 60)
            print("Step 3: INGEST — integrate sources into the wiki")
            print("=" * 60 + "\n")
            stream_turn(
                client, harness_arn,
                f"Ingest every file in {mount}/sources that isn't represented yet. For each, create or "
                f"update concise pages under {mount}/pages (concept/entity pages), cross-link with "
                f"[[links]], update {mount}/index.md, and append a line to {mount}/log.md. "
                "Summarize what you ingested and which pages you touched.",
                args.model, mount, raw=args.raw_events,
            )
            time.sleep(5)

        # ── Step 4: QUERY — answer from the wiki, file the answer ─────
        if args.op in ("all", "query"):
            print("\n" + "=" * 60)
            print("Step 4: QUERY — answer from the wiki (fresh session)")
            print("=" * 60)
            print(f"  Question: {args.message}\n")
            stream_turn(
                client, harness_arn,
                f"Using only the wiki under {mount}/pages, answer: \"{args.message}\". Cite the wiki "
                f"pages you used. Then file your answer as a new page under {mount}/pages and link it "
                f"from {mount}/index.md so the exploration compounds.",
                args.model, mount, raw=args.raw_events,
            )
            time.sleep(5)

        # ── Step 5: LINT — health-check the wiki ──────────────────────
        if args.op in ("all", "lint"):
            print("\n" + "=" * 60)
            print("Step 5: LINT — check the wiki for issues (fresh session)")
            print("=" * 60 + "\n")
            stream_turn(
                client, harness_arn,
                f"Lint the wiki under {mount}: list any contradictions, stale claims, "
                f"orphan pages (not linked from {mount}/index.md), or broken [[links]]. Report findings; "
                "fix trivial issues directly.",
                args.model, mount, raw=args.raw_events,
            )

        print("\n" + "=" * 60)
        print("Done! The wiki persists in S3 — re-run with --op query to see it compound.")
        print("=" * 60)

    finally:
        if not args.skip_cleanup and harness_id:
            print("\nCleaning up...")
            try:
                control.delete_harness(harnessId=harness_id)
                print(f"  Deleted harness: {harness_id}")
            except Exception as e:
                print(f"  Warning: failed to delete harness: {e}")
            print("  Note: the S3 bucket, access point, AND the wiki it holds are left intact.")


if __name__ == "__main__":
    main()
