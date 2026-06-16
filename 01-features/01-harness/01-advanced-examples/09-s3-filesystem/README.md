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
| [`s3_knowledge_base.py`](s3_knowledge_base.py) | **The use case: a persistent LLM wiki / knowledge base.** The agent builds and maintains a compounding markdown wiki on the S3 mount across sessions (ingest → query → lint). |

The first script proves the persistence boundary; the second shows *why you'd
want it*.

## Configuration

S3 mounts are set on the harness environment:

```python
environment={
    "agentCoreRuntimeEnvironment": {
        "filesystemConfigurations": [
            {
                "s3FilesAccessPoint": {
                    "accessPointArn": "arn:aws:s3files:us-west-2:111122223333:file-system/fs-abc/access-point/fsap-def",
                    "mountPath": "/mnt/data",
                }
            }
        ]
    }
}
```

`mountPath` must look like `/mnt/<name>`. The execution role must be allowed to
read/write through the access point — when this script creates the role, it
attaches a scoped S3 policy for you.

## Prerequisites

- An **S3 Files access point** backed by a bucket. Its ARN looks like:
  `arn:aws:s3files:<region>:<account>:file-system/fs-xxxx/access-point/fsap-xxxx`
- If you bring your own execution role (`--role-arn`), it must already permit
  that access point.

## Sample Prompts

**Prompt (Session A)**: "Write a short markdown travel note about Amsterdam to /mnt/data/harness-note.md."
**Expected Behavior**: Agent writes the file under the mounted path and confirms the absolute path.

**Prompt (Session B, fresh VM)**: "Read the file /mnt/data/harness-note.md and show me its contents verbatim."
**Expected Behavior**: Agent reads back the note written in Session A — the S3-backed mount persisted it.

## Key Concepts

**Persistence boundary**: A different `session_id` means a different VM disk. Surviving that boundary is what proves the mount is S3-backed.

**Mount path format**: `mountPath` must match `/mnt/<name>` (validated by the script before the call).

**IAM scope**: The execution role only needs access to the single access point — the script attaches a narrowly scoped policy.

## Use case: a persistent LLM wiki / knowledge base

[`s3_knowledge_base.py`](s3_knowledge_base.py) turns the S3 mount into a
**persistent, compounding LLM wiki**, following the pattern Andrej Karpathy
describes in [this gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):
rather than re-deriving answers from raw documents on every query (classic RAG),
the agent **builds and maintains a markdown wiki once and keeps it current**, so
knowledge becomes a compounding artifact.

The S3 mount is what makes this possible — the wiki must outlive any single
session and be shared across invocations. Three layers live under the mount:

```
/mnt/kb/
  sources/   raw, immutable inputs (the agent reads, never edits)
  wiki/      LLM-owned markdown: summaries, entity pages, concept pages ([[cross-linked]])
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
    --access-point-arn arn:aws:s3files:us-west-2:111122223333:file-system/fs-abc/access-point/fsap-def

# Custom mount path + filename
python s3_filesystem.py \
    --access-point-arn arn:aws:s3files:... \
    --mount-path /mnt/shared \
    --filename trip-notes.md
```

```bash
# 2) The LLM wiki — full demo (bootstrap, ingest, query, lint)
python s3_knowledge_base.py \
    --access-point-arn arn:aws:s3files:us-west-2:111122223333:file-system/fs-abc/access-point/fsap-def

# Query the existing wiki (it compounds — answers get filed back)
python s3_knowledge_base.py --access-point-arn arn:aws:s3files:... \
    --op query -m "How does the LLM wiki pattern differ from RAG?"
```
