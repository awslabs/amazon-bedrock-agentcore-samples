# Quickstart — AWS CLI

> **Status:** placeholder — content to be written.
>
> This quickstart will walk through the same end-to-end flow as the boto3 and AgentCore SDK quickstarts, using only `aws bedrock-agentcore-control` and `aws bedrock-agentcore` shell commands.

## Planned flow

1. **Prereqs** — AWS CLI v2, credentials, region, a memory execution role ARN.
2. **Create a memory resource** — `aws bedrock-agentcore-control create-memory` with `--event-expiry-days`, wait until `status == ACTIVE`.
3. **Write an event** — `aws bedrock-agentcore create-event` with an `actorId`, `sessionId`, and a pair of user/assistant messages.
4. **List & read events** — `list-events` and `get-event` to confirm short-term storage.
5. **Add a built-in semantic strategy** — `update-memory --add-memory-strategies ...` with a `{actorId}`-scoped namespace.
6. **Retrieve a memory record** — `retrieve-memory-records` with a natural-language query once extraction completes (~1 minute).
7. **Teardown** — `delete-memory`.

## See also

- [Concepts](./01-memory-concepts.md)
- Same flow in [boto3](./04-quickstart-boto3.ipynb) and [AgentCore SDK](./05-quickstart-agentcore-sdk.ipynb).
