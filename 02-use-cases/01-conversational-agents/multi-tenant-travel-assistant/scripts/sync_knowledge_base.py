"""Ingest the policy documents into the knowledge base, and wait for it to finish.

    cd backend && uv run python ../scripts/sync_knowledge_base.py [--no-wait]

**The gap this closes, and why nothing caught it.** The knowledge base was created, the documents
and
their metadata sidecars were uploaded to S3 by `seed.load`, and the data source reported
`AVAILABLE`.
`ListIngestionJobs` reported that no ingestion job had *ever* run. Nothing in the repository called
`StartIngestionJob`. So the vector index was empty from the first deploy, and every
`search_policy_knowledge` call returned zero results.

**The failure was invisible because the agent handles it well.** Asked "can I claim in-flight wifi
back?", the agent searched, got nothing, and answered:

    "The policy documents don't say anything about in-flight wifi reimbursement. Your travel team
     would be able to tell you whether it's covered. Would you like me to connect you with them?"

That is a careful, correctly-hedged, escalation-offering answer — and completely wrong. Globex's
policy
document says plainly, in section 2.3, "In-flight wifi is reimbursable on flights exceeding three
hours." An empty retriever and a well-behaved agent combine into a confident "your policy is
silent on
this", which is the worst possible answer: it reads as diligence. A retrieval layer that returns
nothing does not look broken from the outside, which is exactly why it needs a check that asserts a
known sentence comes back.

**Idempotent, so `deploy.sh` runs it every time.** Bedrock ingestion is incremental: unchanged
objects
are detected and skipped, so a re-run on an unchanged corpus is cheap and the statistics show zero
new documents. That also makes this the right place to pick up an edited policy document, which
would
otherwise sit in S3 and never reach the index.
"""

from __future__ import annotations

import argparse
import sys
import time

import boto3
from deployed_refs import refs

TERMINAL = {"COMPLETE", "FAILED", "STOPPED"}


def wait_for(agent, kb_id: str, ds_id: str, job_id: str, *, timeout: int = 1800) -> str:
    """Poll one ingestion job to a terminal state.

    Waited on rather than fired and forgotten, because the next thing a deploy does is tell the
    operator the stack is ready. Returning while the index is still building means the first
    `search_policy_knowledge` after a deploy can legitimately find nothing, which is the same
    symptom as never having ingested at all.
    """
    deadline = time.time() + timeout
    last = None
    while True:
        job = agent.get_ingestion_job(
            knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job_id
        )["ingestionJob"]
        status = job["status"]
        if status != last:
            print(f"    {status}")
            last = status
        if status in TERMINAL:
            stats = job.get("statistics") or {}
            if stats:
                print(
                    "    scanned={} new={} modified={} deleted={} failed={}".format(
                        stats.get("numberOfDocumentsScanned"),
                        stats.get("numberOfNewDocumentsIndexed"),
                        stats.get("numberOfModifiedDocumentsIndexed"),
                        stats.get("numberOfDocumentsDeleted"),
                        stats.get("numberOfDocumentsFailed"),
                    )
                )
            for reason in job.get("failureReasons") or []:
                print(f"    failure: {reason}", file=sys.stderr)
            return status
        if time.time() > deadline:
            print(f"    still {status} after {timeout}s — not waiting further", file=sys.stderr)
            return status
        time.sleep(10)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-wait", action="store_true", help="start ingestion and return without polling"
    )
    args = parser.parse_args()

    agent = boto3.client("bedrock-agent", region_name=refs.region)
    kb_id = refs.knowledge_base_id

    sources = agent.list_data_sources(knowledgeBaseId=kb_id)["dataSourceSummaries"]
    if not sources:
        print(f"  {kb_id} has no data sources", file=sys.stderr)
        return 1

    failed = False
    for source in sources:
        ds_id = source["dataSourceId"]
        print(f"  ingesting {source['name']} ({ds_id})")
        job = agent.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
            description="deploy.sh sync_knowledge_base",
        )["ingestionJob"]
        if args.no_wait:
            print(f"    started {job['ingestionJobId']}, not waiting")
            continue
        if wait_for(agent, kb_id, ds_id, job["ingestionJobId"]) != "COMPLETE":
            failed = True

    if failed:
        print("  at least one ingestion job did not complete", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
