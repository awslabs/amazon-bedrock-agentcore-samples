"""Redriving failed memory extraction jobs.

What you learn:
    - ListMemoryExtractionJobs to find jobs that failed
    - StartMemoryExtractionJob to redrive a job by id
    - When a redrive is appropriate vs. when to investigate first

Long-term extraction runs asynchronously after CreateEvent. If a job fails
(model throttle, transient error, validation issue), AgentCore records it
as an extraction job with status=FAILED and a failureReason. You can list
those, decide whether the underlying issue is fixed, and redrive.

Three surfaces:
    python redrive-failed-extractions.py boto3
    python redrive-failed-extractions.py sdk    # documents the SDK gap
    python redrive-failed-extractions.py cli

SDK note: MemoryClient does not wrap ListMemoryExtractionJobs or
StartMemoryExtractionJob. Use the wrapped boto3 client (`client.gmcp_client`)
or boto3 directly.

Prerequisites:
    pip install boto3 bedrock-agentcore
    export AWS_REGION=us-east-1
    export MEMORY_ID=<memory-id-with-failed-jobs>
"""

import os
import sys
import time

REGION = os.getenv("AWS_REGION", "us-east-1")


# === boto3 ============================================================
def run_with_boto3() -> None:
    import boto3

    memory_id = os.environ.get("MEMORY_ID")
    if not memory_id:
        print("[boto3] Set MEMORY_ID to a memory resource with failed extraction jobs.")
        return

    data = boto3.client("bedrock-agentcore", region_name=REGION)

    failed = []
    next_token = None
    while True:
        kwargs = {"memoryId": memory_id, "filter": {"status": "FAILED"}}
        if next_token:
            kwargs["nextToken"] = next_token
        resp = data.list_memory_extraction_jobs(**kwargs)
        failed.extend(resp.get("jobs", []))
        next_token = resp.get("nextToken")
        if not next_token:
            break

    print(f"[boto3] Found {len(failed)} failed job(s) for {memory_id}")
    for j in failed:
        print(
            f"  jobId={j['jobID']} actor={j.get('actorId')} "
            f"session={j.get('sessionId')} strategy={j.get('strategyId')}"
        )
        print(f"    failureReason={j.get('failureReason')}")

    # Gate redrive on a deliberate fix — blind retries waste tokens.
    for j in failed:
        echoed = data.start_memory_extraction_job(
            memoryId=memory_id, extractionJob={"jobId": j["jobID"]},
        )["jobId"]
        print(f"[boto3] Redrove jobId={echoed}")
        time.sleep(1)


# === AgentCore SDK ====================================================
def run_with_sdk() -> None:
    print(
        "[sdk] Extraction-job redrive is not exposed by MemoryClient.\n"
        "      Use the boto3 path (see run_with_boto3) or call:\n"
        "        client.gmcp_client.list_memory_extraction_jobs(\n"
        "            memoryId=..., filter={\"status\": \"FAILED\"})\n"
        "        client.gmcp_client.start_memory_extraction_job(\n"
        "            memoryId=..., extractionJob={\"jobId\": ...})"
    )


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# 1. List failed extraction jobs for a memory.
aws bedrock-agentcore list-memory-extraction-jobs \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --filter '{"status":"FAILED"}'

# 2. Inspect the failureReason for each job before deciding to redrive.
#    Common reasons: ThrottlingException (model), AccessDenied (role), validation.

# 3. Redrive a single job. Only do this after fixing the underlying issue.
aws bedrock-agentcore start-memory-extraction-job \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --extraction-job '{"jobId":"<jobId-from-list>"}'

# 4. Confirm the job left the FAILED set.
aws bedrock-agentcore list-memory-extraction-jobs \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --filter '{"status":"FAILED"}'
"""


def main() -> None:
    surface = sys.argv[1] if len(sys.argv) > 1 else "boto3"
    if surface == "boto3":
        run_with_boto3()
    elif surface == "sdk":
        run_with_sdk()
    elif surface == "cli":
        print(CLI_WALKTHROUGH)
    else:
        print(f"Unknown surface {surface!r}. Use boto3 | sdk | cli.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
