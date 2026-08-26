"""Narrow the three AgentCore VPC endpoints to this deployment's own resources.

    cd backend && AWS_REGION=us-east-1 uv run python ../scripts/restrict_agentcore_endpoints.py
    ...add --dry-run to print the policies without applying them

**A post-deploy step because of ordering, not because it is optional.** Eight of the eleven
interface
endpoints are narrowed in `MultiTenantTravelStack.restrictEndpoints()`. These three cannot be: they
name the
runtime, the memory and the gateway, all of which belong to the AgentCore CLI's stack — which
deploys *after* `infra/`. So there is no ARN at synth time.

That is the same sequencing problem `publish_agent_refs.py` already solves, and the same shape of
solution: read the values from the deployed agent stack, then apply them.

**Why bother, given the endpoints are already private?** Because "private" and "restricted" are
different properties, and only the second one is worth the endpoint's monthly cost. Left at the
default an endpoint policy is `*` on `*` — a private route to *every* AgentCore operation on
*every* resource the caller's IAM permits. With a policy, two independent controls must fail before
something in this VPC reaches an unrelated agent, memory or gateway: its execution role, and the
network path.

The `sts` endpoint is the argument for doing this: scoping it to one role is what surfaced a genuine
misconfiguration during the VPC migration.

**Idempotent**, and it prints what it changed. Run it after every `agentcore deploy` — the ARNs are
stable across deploys today, but a stack recreation would change them, and a policy naming a
resource that no longer exists fails closed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import boto3

# Not a literal: a reader deploying to another region would otherwise get a script that
# addresses us-east-1 while their stack is elsewhere. Same default and same reason as
# `deploy.sh` — `TRAVEL_REGION` wins over an ambient `AWS_REGION` set for other work.
REGION = os.environ.get("TRAVEL_REGION") or os.environ.get("AWS_REGION") or "us-east-1"
VPC_NAME = "multi-tenant-travel-vpc"
AGENT_STACK = "AgentCore-MultiTenantTravel-default"

# Outputs to read from the agent stack, matched by prefix because CDK appends a hash that shifts
# when the stack is regenerated. Same reasoning as `publish_agent_refs.py`.
RUNTIME_ARN_OUTPUT = "ApplicationAgentAssistantRuntimeArnOutput"
GATEWAY_ARN_OUTPUT = "GatewayToolsArn"
MEMORY_ID_OUTPUT = "ApplicationMemoryConversationsIdOutput"


def stack_outputs(cfn) -> dict[str, str]:
    try:
        stacks = cfn.describe_stacks(StackName=AGENT_STACK)["Stacks"]
    except cfn.exceptions.ClientError as error:
        raise SystemExit(
            f"cannot read {AGENT_STACK}: {error}\nrun `agentcore deploy` first"
        ) from None
    return {o["OutputKey"]: o["OutputValue"] for o in stacks[0].get("Outputs", [])}


def by_prefix(outputs: dict[str, str], prefix: str) -> str:
    """One output whose key starts with `prefix`, or a loud failure.

    Ambiguity is an error rather than a "take the first": publishing a policy that names the wrong
    resource would deny live traffic, and the whole point of this script is to avoid a silent
    misconfiguration.
    """
    matches = [key for key in outputs if key.startswith(prefix)]
    if len(matches) != 1:
        raise SystemExit(f"{prefix!r} matched {len(matches)} outputs in {AGENT_STACK}: {matches}")
    value = outputs[matches[0]]
    if not value:
        raise SystemExit(f"{matches[0]} is present but empty")
    return value


def policies(account: str, runtime_arn: str, gateway_arn: str, memory_arn: str) -> dict[str, dict]:
    """The policy document for each of the three endpoints, keyed by service name.

    Each is written from what the code demonstrably calls, read out of the source rather than from a
    list of plausible actions — the same method that caught `sts:TagSession` and
    `bedrock:ApplyGuardrail` being missing during the migration.
    """
    return {
        # The Gateway the agent calls its tools through, and only ours.
        #
        # Tool authorisation is *not* what this defends: Cedar and the interceptor do that per call
        # with a verified JWT. What this adds is that nothing in this VPC can reach a *different*
        # gateway — one in this account with laxer policies, or a future one added for another
        # purpose. A network-level boundary on top of the identity-level one.
        "bedrock-agentcore.gateway": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    # MCP traffic to a gateway authorizes as `InvokeGateway`.
                    # `ListGatewayTargets` is how the client discovers the catalogue at startup —
                    # the agent logs "agent ready: 14 tools" from exactly this call, so omitting it
                    # would produce an agent with no tools and no obvious reason why.
                    "Action": [
                        "bedrock-agentcore:InvokeGateway",
                        "bedrock-agentcore:ListGatewayTargets",
                    ],
                    "Resource": [gateway_arn, f"{gateway_arn}/*"],
                }
            ],
        },
        # The data plane: conversation memory every turn, plus the runtime invoke.
        #
        # `Resource` names both because this endpoint carries both. The runtime entry matters less
        # than it looks — the BFF invokes the runtime from *outside* the VPC — but the agent's own
        # `InvokeAgentRuntime` would cross here if it ever self-invoked, and naming it costs
        # nothing.
        "bedrock-agentcore": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    # Read from `session_manager.py`: `create_event` per turn, `list_events` to
                    # restore history, `retrieve_memory_records` for the `USER_PREFERENCE`
                    # namespace, and `get_event`/`delete_event`, held for corrections.
                    "Action": [
                        "bedrock-agentcore:CreateEvent",
                        "bedrock-agentcore:GetEvent",
                        "bedrock-agentcore:ListEvents",
                        "bedrock-agentcore:DeleteEvent",
                        "bedrock-agentcore:RetrieveMemoryRecords",
                        "bedrock-agentcore:InvokeAgentRuntime",
                    ],
                    "Resource": [memory_arn, f"{memory_arn}/*", runtime_arn, f"{runtime_arn}/*"],
                }
            ],
        },
        # The control plane, and the narrowest of the three on purpose.
        #
        # **`AgentCoreMemorySessionManager` constructs a `bedrock-agentcore-control` client but
        # never calls it on the request path** — verified by reading it: the only reference is the
        # client construction itself, and every per-turn call goes through the data-plane client.
        # Constructing a boto3 client makes no network request, so this endpoint may be unnecessary.
        #
        # It is kept, scoped read-only on our own memory, rather than deleted: the library could
        # resolve strategies through it on a path not exercised yet, and $14.60/month is a poor
        # trade against an agent that fails at cold start for a reason nobody would look for. Writes
        # are excluded — CDK owns the memory's lifecycle, and a runtime that could `DeleteMemory` is
        # a blast radius with no upside.
        "bedrock-agentcore-control": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["bedrock-agentcore:GetMemory", "bedrock-agentcore:ListMemories"],
                    "Resource": [memory_arn, f"{memory_arn}/*"],
                }
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print the policies and exit")
    args = parser.parse_args()

    ec2 = boto3.client("ec2", region_name=REGION)
    cfn = boto3.client("cloudformation", region_name=REGION)
    account = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]

    found = ec2.describe_vpcs(Filters=[{"Name": "tag:Name", "Values": [VPC_NAME]}])["Vpcs"]
    if not found:
        raise SystemExit(
            f"no VPC named {VPC_NAME!r} — the stack is deployed public, so there are no endpoints "
            "to restrict. Deploy with TRAVEL_PRIVATE=true first."
        )
    vpc_id = found[0]["VpcId"]

    outputs = stack_outputs(cfn)
    runtime_arn = by_prefix(outputs, RUNTIME_ARN_OUTPUT)
    gateway_arn = by_prefix(outputs, GATEWAY_ARN_OUTPUT)
    memory_id = by_prefix(outputs, MEMORY_ID_OUTPUT)
    # The stack publishes the memory *id*; the ARN is not an output, so it is composed here. Same
    # form `conversation-api.ts` uses for the BFF's `ListEvents` grant.
    memory_arn = f"arn:aws:bedrock-agentcore:{REGION}:{account}:memory/{memory_id}"

    print(f"\nVPC {vpc_id}")
    print(f"  runtime {runtime_arn}")
    print(f"  gateway {gateway_arn}")
    print(f"  memory  {memory_arn}\n")

    wanted = policies(account, runtime_arn, gateway_arn, memory_arn)
    endpoints = {
        e["ServiceName"].replace(f"com.amazonaws.{REGION}.", ""): e
        for e in ec2.describe_vpc_endpoints(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])[
            "VpcEndpoints"
        ]
    }

    failures = []
    for service, document in wanted.items():
        endpoint = endpoints.get(service)
        if not endpoint:
            failures.append(f"no {service} endpoint in {vpc_id}")
            continue

        current = json.loads(endpoint.get("PolicyDocument") or "{}")
        if current == document:
            print(f"  unchanged  {service}")
            continue

        if args.dry_run:
            print(f"  would set  {service}")
            print("     " + json.dumps(document["Statement"][0]["Action"]))
            continue

        ec2.modify_vpc_endpoint(
            VpcEndpointId=endpoint["VpcEndpointId"],
            PolicyDocument=json.dumps(document),
        )
        actions = document["Statement"][0]["Action"]
        print(f"  restricted {service}  ({len(actions)} actions)")

    if failures:
        print("\nFAILED:")
        for failure in failures:
            print(f"  {failure}")
        return 1

    print("\nall eleven interface endpoints are now narrowed — verify with verify_network.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
