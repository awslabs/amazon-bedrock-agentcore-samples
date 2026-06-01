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
```

## Best practices

- **Pick a stable `actorId` per end user**, not per device or installation — actors carry across sessions.
- **One conversation = one `sessionId`.** Open a new session for a new conversation; do not reuse a session weeks later.
- Use `includePayloads=False` on `ListEvents` when you only need to enumerate ids/timestamps — it is significantly faster on long sessions.
- Use `eventExpiryDuration` (3–365 days) on the memory resource to bound storage cost.

## AWS CLI walkthrough

The same flow expressed with the AWS CLI:

```bash
# 1. Create memory + capture id
aws bedrock-agentcore-control create-memory \
  --region "$AWS_REGION" \
  --name "EventsAndSessionsCli-$(date +%s)" \
  --event-expiry-duration 30 \
  --client-token "$(uuidgen)"
export MEMORY_ID=<id-from-response>

# 2. Append events to two distinct sessions for the same actor
for sid in session-a session-b; do
  aws bedrock-agentcore create-event \
    --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
    --actor-id user-42 --session-id "$sid" \
    --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --payload '[{"conversational":{"role":"USER","content":{"text":"hello"}}}]'
done

# 3. ListEvents within one session
aws bedrock-agentcore list-events \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --actor-id user-42 --session-id session-a --include-payloads

# 4. GetEvent for one event by id
aws bedrock-agentcore get-event \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --actor-id user-42 --session-id session-a --event-id <event-id>

# 5. ListSessions discovers prior sessions for the actor
aws bedrock-agentcore list-sessions \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" --actor-id user-42

# 6. Teardown
aws bedrock-agentcore-control delete-memory \
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \
  --client-token "$(uuidgen)"
```
