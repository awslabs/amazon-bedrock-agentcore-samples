# Event branching

Branches let you fork a session at a chosen event and continue down divergent paths. Each branch is identified by a `name` and a `rootEventId` (the parent event it forks from). Branches share the parent's history but record their own subsequent events.

## What you learn

- Forking a session by setting `branch={"name": ..., "rootEventId": ...}` on `CreateEvent`
- Reading one branch only with `filter={"branch": {"name": "...", "includeParentBranches": False}}`
- Reading the full ancestry with `includeParentBranches=True`

## When to use

- **What-if conversations** — explore alternative replies without polluting the canonical thread.
- **Parallel sub-agents** — each subagent writes on its own branch off a shared parent state, then a coordinator stitches the branches.
- **A/B exploration during development** — compare retrieval/strategy variants on the same upstream context.

## Run

```bash
python event-branching.py boto3   # default — direct service calls
python event-branching.py sdk     # uses MemoryClient.fork_conversation
python event-branching.py cli     # print equivalent AWS CLI commands
```

## Best practices

- **Pick the fork point deliberately.** The `rootEventId` becomes the shared base — everything before it is parent context for every descendant branch.
- **Use short, descriptive branch names** (`autumn`, `agent-a`, `experiment-1`). The name is opaque to AgentCore but is your filter key on `ListEvents`.
- For multi-agent parallel work, share the parent context but isolate per-agent contributions on distinct branches; merge by reading each branch separately.
- See `../examples/multi-agent/with-strands-agent/multi-agent-parallel-branches/` for an end-to-end Strands example.
