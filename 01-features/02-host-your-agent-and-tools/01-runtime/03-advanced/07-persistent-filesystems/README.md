# Persistent Filesystems

## Overview

AgentCore runtime supports persisting filesystem state across session stop/resume cycles. Files, installed packages, and build artifacts survive session stops without needing external storage like S3 or DynamoDB.

## How It Works

Add `filesystemConfigurations` when creating the runtime:

```python
control.create_agent_runtime(
    # ... other params ...
    filesystemConfigurations=[
        {
            'sessionStorage': {
                'mountPath': '/mnt/data',  # must be under /mnt with one subdirectory
            }
        }
    ],
)
```

Files written to `/mnt/data` persist across session stop/resume cycles within the same session.

### Session Storage Lifecycle

```
Session Start  →  Write files to /mnt/data  →  Session Stop (microVM shuts down)
                                                     ↓
Session Resume (same session ID)  →  Files still at /mnt/data  →  Continue working
                                                     ↓
Session Terminate  →  Storage released permanently
```

### Constraints

| Constraint | Detail |
|:-----------|:-------|
| Mount path | Must be under `/mnt` with exactly one subdirectory (e.g., `/mnt/data`, `/mnt/workspace`) |
| Scope | Storage is per-session — different session IDs have different storage |
| Lifecycle | Storage persists across stop/resume but is released on session termination |

## What This Demo Shows

The `invoke.py` script demonstrates the full lifecycle:

1. **Add notes** — the agent writes notes to `/mnt/data/notes.json`
2. **Stop the session** — the microVM shuts down
3. **Resume the same session** — the microVM restarts with the same session ID
4. **Verify persistence** — the notes are still there

### The Agent Code

The agent uses tools that read/write to the persistent mount:

```python
STORAGE_PATH = "/mnt/data"
NOTES_FILE = f"{STORAGE_PATH}/notes.json"

@tool
def add_note(content: str) -> str:
    """Add a note to persistent storage."""
    notes = json.load(open(NOTES_FILE)) if os.path.exists(NOTES_FILE) else []
    notes.append({"id": len(notes) + 1, "content": content})
    json.dump(notes, open(NOTES_FILE, "w"))
    return f"Note saved"

@tool
def list_notes() -> str:
    """List all notes from persistent storage."""
    notes = json.load(open(NOTES_FILE)) if os.path.exists(NOTES_FILE) else []
    return json.dumps(notes)
```

### The Deploy Script

The key difference from other deploy scripts is the `filesystemConfigurations` parameter:

```python
control.create_agent_runtime(
    agentRuntimeName="persistent-fs-agent",
    agentRuntimeArtifact={...},
    roleArn=role_arn,
    networkConfiguration={"networkMode": "PUBLIC"},
    protocolConfiguration={"serverProtocol": "HTTP"},
    # ── This is the key addition ──
    filesystemConfigurations=[
        {"sessionStorage": {"mountPath": "/mnt/data"}}
    ],
)
```

## Files

| File | Description |
|:-----|:------------|
| `agent.py` | Note-taking agent that reads/writes to `/mnt/data/notes.json` |
| `requirements.txt` | Dependencies |
| `deploy.py` | Deploys with `filesystemConfigurations` for persistent storage |
| `invoke.py` | Adds notes → stops session → resumes → verifies notes persist |
| `cleanup.py` | Deletes runtime, endpoint, S3 artifact, IAM role |

## Quick Start

```bash
python deploy.py     # Deploy with persistent filesystem at /mnt/data
python invoke.py     # Run the persistence demo
python cleanup.py    # Clean up
```
