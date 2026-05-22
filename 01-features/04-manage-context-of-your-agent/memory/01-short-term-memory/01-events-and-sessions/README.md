# Events and sessions

Events are the atomic unit of short-term memory. Each event is **immutable**, **timestamped**, and scoped to an `actorId` + `sessionId`. A session is just a chronologically ordered group of events — there is no separate "session" resource to create.

## What you learn

- `CreateEvent` appends a new event to a session
- `ListEvents` pages through events in a session, optionally with payloads
- `GetEvent` fetches one event in full
- `ListSessions` discovers prior sessions for an actor

## Run

```bash
python events-and-sessions.py boto3   # default — direct service calls
python events-and-sessions.py sdk     # AgentCore MemoryClient helpers
python events-and-sessions.py cli     # print equivalent AWS CLI commands
```

## Best practices

- **Pick a stable `actorId` per end user**, not per device or installation — actors carry across sessions.
- **One conversation = one `sessionId`.** Open a new session for a new conversation; do not reuse a session weeks later.
- Use `includePayloads=False` on `ListEvents` when you only need to enumerate ids/timestamps — it is significantly faster on long sessions.
- Use `eventExpiryDuration` (3–365 days) on the memory resource to bound storage cost.
