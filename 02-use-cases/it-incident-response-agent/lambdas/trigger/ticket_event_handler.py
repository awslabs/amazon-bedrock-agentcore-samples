"""SNS-triggered handler: dispatch a Jira issue key into the AgentCore Runtime.

Wire-up:
  Jira automation -> SNS topic -> this Lambda -> InvokeAgentRuntime.

Each SNS message body is a small JSON object:
  {"issue_key": "INC-1042", "requester_id": "U-1001"}

`requester_id` is optional — if missing, the runtime falls back to the
issue key as the actor id for memory.

Note on auth: the runtime fetches its own outbound tokens (Auth0 M2M for
the Gateway, Atlassian 3LO for the Jira MCP server) via AgentCore Identity
(`@requires_access_token`). The trigger Lambda does NOT mint or pass
tokens — that responsibility lives entirely with AgentCore Identity inside
the runtime.
"""

import base64
import json
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AGENT_RUNTIME_ARN = os.environ["AGENT_RUNTIME_ARN"]

_runtime = boto3.client("bedrock-agentcore")


def lambda_handler(event, context):
    logger.info("ticket_event_handler invoked, records=%d", len(event.get("Records", [])))

    for record in event.get("Records", []):
        message = json.loads(record["Sns"]["Message"])
        issue_key = message["issue_key"]
        logger.info("dispatching Jira issue %s", issue_key)

        payload = json.dumps(
            {
                "issue_key": issue_key,
                "requester_id": message.get("requester_id", issue_key),
            }
        ).encode()

        resp = _runtime.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            qualifier="DEFAULT",
            payload=base64.b64encode(payload),
        )
        logger.info(
            "AgentCore invoked for issue %s, status=%s",
            issue_key,
            resp.get("ResponseMetadata", {}).get("HTTPStatusCode"),
        )

    return {"status": "dispatched", "count": len(event.get("Records", []))}
