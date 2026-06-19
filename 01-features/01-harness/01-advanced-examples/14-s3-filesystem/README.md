# S3 Filesystem Mount

| Information         | Details                                                                  |
|:--------------------|:-------------------------------------------------------------------------|
| Tutorial type       | Advanced Example                                                         |
| Agent type          | Assistant with persistent storage                                        |
| Agentic Framework   | None (direct boto3)                                                      |
| LLM model           | Anthropic Claude Haiku 4.5                                               |
| Tutorial components | AgentCore harness — `filesystemConfigurations`, S3 Files access point    |
| Example complexity  | Intermediate                                                             |

## Overview

A harness session runs in an isolated microVM with an **ephemeral** disk — when
the session ends, anything written to the VM is gone. Mount an **S3 Files access
point** into the VM and the agent gets a normal POSIX path (e.g. `/mnt/data`)
backed by S3, so artifacts persist past the session and are shared across
sessions.

## What's in this folder

| File | What it shows |
|---|---|
| [`s3_filesystem.py`](s3_filesystem.py) | **The mechanism.** Session A writes a file under the mount; Session B (a brand-new microVM) reads it back — only possible because the file lives in S3, not on the VM disk. |
| [`s3_llm_wiki.py`](s3_llm_wiki.py) | **The use case: a persistent LLM wiki.** The agent builds and maintains a compounding markdown wiki on the S3 mount across sessions (ingest → query → lint). |

The first script proves the persistence boundary; the second shows *why you'd
want it*.

## Configuration

An S3 Files mount requires the harness to run in **VPC network mode** — the
microVM reaches the access point's mount target over your VPC. So the
environment carries both a `networkConfiguration` and the `filesystemConfigurations`:

```python
environment={
    "agentCoreRuntimeEnvironment": {
        "networkConfiguration": {
            "networkMode": "VPC",
            "networkModeConfig": {
                "subnets": ["subnet-0abc1234"],
                "securityGroups": ["sg-0def5678"],
            },
        },
        "filesystemConfigurations": [
            {
                "s3FilesAccessPoint": {
                    "accessPointArn": "arn:aws:s3files:us-west-2:111122223333:file-system/fs-abc/access-point/fsap-def",
                    "mountPath": "/mnt/data",
                }
            }
        ],
    }
}
```

`mountPath` must look like `/mnt/<name>`. The execution role must be allowed to
mount the access point — when this script creates the role, it attaches the
required `s3files` permissions for you: `s3files:GetAccessPoint` (the runtime
validates this at create time, so it stays unscoped) plus `s3files:ClientMount`
and `s3files:ClientWrite` (scoped to the file system with an `AccessPointArn`
condition, used when the microVM mounts the access point).

## Prerequisites

- An **S3 Files access point** backed by a bucket, with a **mount target** in the
  subnet you pass. Its ARN looks like:
  `arn:aws:s3files:<region>:<account>:file-system/fs-xxxx/access-point/fsap-xxxx`
- The **subnet(s) and security group(s)** that reach the mount target. The Harness
  must be in the **same VPC** as the mount target, the subnet(s) you pass must be
  in an **Availability Zone that has a mount target**, and the security group(s)
  must allow **NFS (port 2049)** between the Harness and the mount target (a
  self-referencing security group is the simplest setup).
- **Use private subnets with egress** (a route to a NAT gateway). VPC-mode
  Harnesses run in private networking; public subnets do not give the microVM the
  connectivity it needs and the invoke will fail. See
  [Configure AgentCore for VPC](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-vpc.html).
- If you bring your own execution role (`--role-arn`), it must already have the
  `s3files` mount permissions above.

## Sample Prompts

**Prompt (Session A)**: "Write a short markdown travel note about Amsterdam to /mnt/data/harness-note.md."
**Expected Behavior**: Agent writes the file under the mounted path and confirms the absolute path.

**Prompt (Session B, fresh VM)**: "Read the file /mnt/data/harness-note.md and show me its contents verbatim."
**Expected Behavior**: Agent reads back the note written in Session A — the S3-backed mount persisted it.

## Key Concepts

**Persistence boundary**: A different `session_id` means a different VM disk. Surviving that boundary is what proves the mount is S3-backed.

**Mount path format**: `mountPath` must match `/mnt/<name>` (validated by the script before the call).

**IAM scope**: The execution role only needs access to the single access point — the script attaches a narrowly scoped policy.

## Use case: a persistent LLM wiki

[`s3_llm_wiki.py`](s3_llm_wiki.py) turns the S3 mount into a
**persistent, compounding LLM wiki**, following the pattern Andrej Karpathy
describes in [this gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
rather than re-deriving answers from raw documents on every query (classic RAG),
the agent **builds and maintains a markdown wiki once and keeps it current**, so
knowledge becomes a compounding artifact.

> This is a self-maintained markdown wiki on the agent's filesystem — it is
> unrelated to the **Amazon Bedrock Knowledge Bases** feature.

The S3 mount is what makes this possible — the wiki must outlive any single
session and be shared across invocations. Three layers live under the mount:

```
/mnt/wiki/
  sources/   raw, immutable inputs (the agent reads, never edits)
  pages/     LLM-owned markdown: summaries, entity pages, concept pages ([[cross-linked]])
  AGENTS.md  the schema (how the wiki is organized)
  index.md   catalog of pages
  log.md     append-only history
```

Three operations, **each run in its own session** to prove the wiki persists
across the microVM boundary:

- **ingest** — read a raw source and integrate it across the wiki (create/update pages)
- **query** — answer from the wiki, then file the answer back as a new page so explorations compound
- **lint** — health-check: contradictions, stale claims, orphan pages, broken links

Re-run with `--op query` later and the wiki is still there in S3 — the agent
picks up exactly where it left off.

## Clean Up

```python
control.delete_harness(harnessId=harness_id)
from utils.iam import delete_harness_role
delete_harness_role()
```

The script deletes the harness on exit (pass `--skip-cleanup` to keep it). It
**leaves your S3 bucket and access point intact**.

## Running the Python Scripts

```bash
pip install -r ../../requirements.txt
```

```bash
# 1) The mechanism — prove persistence across sessions
python s3_filesystem.py \
    --access-point-arn arn:aws:s3files:us-west-2:111122223333:file-system/fs-abc/access-point/fsap-def \
    --subnet-ids subnet-0abc1234 \
    --security-group-ids sg-0def5678

# Custom mount path + filename
python s3_filesystem.py \
    --access-point-arn arn:aws:s3files:... \
    --subnet-ids subnet-0abc1234 --security-group-ids sg-0def5678 \
    --mount-path /mnt/shared \
    --filename trip-notes.md
```

```bash
# 2) The LLM wiki — full demo (bootstrap, ingest, query, lint)
python s3_llm_wiki.py \
    --access-point-arn arn:aws:s3files:us-west-2:111122223333:file-system/fs-abc/access-point/fsap-def \
    --subnet-ids subnet-0abc1234 --security-group-ids sg-0def5678

# Query the existing wiki (it compounds — answers get filed back)
python s3_llm_wiki.py --access-point-arn arn:aws:s3files:... \
    --subnet-ids subnet-0abc1234 --security-group-ids sg-0def5678 \
    --op query -m "How does the LLM wiki pattern differ from RAG?"
```
