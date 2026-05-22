# Actor and session isolation

`actorId` + `sessionId` are the only required scoping keys for short-term memory. A single memory resource can serve every user in your application — events are isolated by these two keys at the API level, and IAM conditions on `bedrock-agentcore:actorId` / `sessionId` enforce isolation across roles.

## What you learn

- One memory resource serves many actors
- Events are addressable only via `(memoryId, actorId, sessionId)`
- `ListSessions` returns sessions for the requested actor only

## Run

```bash
python actor-session-isolation.py boto3   # default — direct service calls
python actor-session-isolation.py sdk     # AgentCore MemoryClient helpers
python actor-session-isolation.py cli     # print equivalent AWS CLI commands
```

## Best practices

- **Pick a stable `actorId`** that maps to a real principal (Cognito `sub`, internal user id) — not a transient device id. Long-term memory namespaces typically use `{actorId}`, so a stable id keeps a user's records together.
- **Enforce isolation at IAM, not just at the application layer.** Use the `bedrock-agentcore:actorId` and `bedrock-agentcore:sessionId` condition keys on memory actions so a runtime role can only touch one user's data. See `../../05-security/01-iam-scoped-access/`.
- For multi-tenant workloads, prefix actor ids with the tenant (`acme/user-42`) and condition IAM on the prefix.
