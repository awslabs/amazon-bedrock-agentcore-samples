"""Publish the agent runtime ARN and memory id to Parameter Store, from the agent stack's outputs.

    cd backend && AWS_REGION=us-east-1 uv run python ../scripts/publish_agent_refs.py

**Run this after `agentcore deploy`, and never by hand.** Two values in this system are produced by
the AgentCore CLI's own CloudFormation stack and consumed by ours: the runtime ARN the BFF invokes,
and the memory id it reads conversation history from. Two stacks means no CloudFormation
reference is possible, so something has to carry them across.

**They used to be carried by environment variables on the `cdk deploy` command, and that was a real
defect rather than a stylistic one.** A redeploy from a shell that had not exported
`TRAVEL_RUNTIME_ARN` wrote an **empty string** over a working value. Nothing failed: CloudFormation
reported success, the deploy log was clean, and the next traveller to send a message received a
`404 <UnknownOperationException/>` from `InvokeAgentRuntime` — an error that names no cause,
mentions neither the ARN nor the deployment, and points at AgentCore rather than at the
operator's shell.

Reading the values from the source of truth removes the step a human can forget. The script is
idempotent, prints what it changed, and refuses to write a value it could not find rather than
publishing an empty one — the failure it exists to prevent.
"""

from __future__ import annotations

import argparse
import os
import sys

import boto3

# Not a literal: a reader deploying to another region would otherwise get a script that
# addresses us-east-1 while their stack is elsewhere. Same default and same reason as
# `deploy.sh` — `TRAVEL_REGION` wins over an ambient `AWS_REGION` set for other work.
REGION = os.environ.get("TRAVEL_REGION") or os.environ.get("AWS_REGION") or "us-east-1"
AGENT_STACK = "AgentCore-MultiTenantTravel-default"

# Output key → parameter name. The keys are CDK-generated and carry a hash suffix, so they are
# matched by *prefix*: the CLI regenerates its stack, and a hash that shifts would otherwise
# silently stop resolving — the same class of silent failure this script exists to remove.
PUBLISH: dict[str, tuple[str, str]] = {
    "ApplicationAgentAssistantRuntimeArnOutput": (
        "/multi-tenant-travel/agent/runtime-arn",
        "Agent runtime the conversation API invokes",
    ),
    "ApplicationMemoryConversationsIdOutput": (
        "/multi-tenant-travel/agent/memory-id",
        "AgentCore Memory holding conversation history",
    ),
}


def outputs(cfn) -> dict[str, str]:
    try:
        stacks = cfn.describe_stacks(StackName=AGENT_STACK)["Stacks"]
    except cfn.exceptions.ClientError as error:
        raise SystemExit(
            f"cannot read {AGENT_STACK}: {error}\nrun `agentcore deploy` first"
        ) from None
    return {o["OutputKey"]: o["OutputValue"] for o in stacks[0].get("Outputs", [])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="print what would be written and exit"
    )
    args = parser.parse_args()

    cfn = boto3.client("cloudformation", region_name=REGION)
    ssm = boto3.client("ssm", region_name=REGION)

    found = outputs(cfn)
    failures = []

    for prefix, (parameter, description) in PUBLISH.items():
        matches = [key for key in found if key.startswith(prefix)]
        if not matches:
            failures.append(f"no output starting with {prefix!r} in {AGENT_STACK}")
            continue
        # More than one match would mean the prefix is ambiguous — a silent wrong value is exactly
        # what this script exists to avoid, so it is a failure rather than a "pick the first".
        if len(matches) > 1:
            failures.append(f"{prefix!r} matched {len(matches)} outputs: {sorted(matches)}")
            continue

        value = found[matches[0]]
        if not value:
            failures.append(f"{matches[0]} is present but empty")
            continue

        try:
            current = ssm.get_parameter(Name=parameter)["Parameter"]["Value"]
        except ssm.exceptions.ParameterNotFound:
            current = None

        if current == value:
            print(f"  unchanged  {parameter}")
            continue

        if args.dry_run:
            print(f"  would set  {parameter} = {value}")
            continue

        ssm.put_parameter(
            Name=parameter,
            Value=value,
            Type="String",
            Description=description,
            Overwrite=True,
        )
        print(f"  {'updated' if current else 'created'}    {parameter} = {value}")

    if failures:
        print("\nFAILED:")
        for failure in failures:
            print(f"  {failure}")
        # Loud and non-zero. A partial publish that exits 0 would let a deploy pipeline continue
        # with a stale runtime ARN — the original bug wearing a different hat.
        return 1

    print("\nagent references published — the conversation API resolves these at cold start")
    return 0


if __name__ == "__main__":
    sys.exit(main())
