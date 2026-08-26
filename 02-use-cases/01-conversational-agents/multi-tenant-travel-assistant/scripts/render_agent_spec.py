"""Fill `agentcore.json` and the runtime's IAM policies from the deployed stacks.

    cd backend && uv run python ../scripts/render_agent_spec.py

The CLI's schema takes concrete values — a Lambda ARN per gateway target, a Cognito discovery URL,
client ids, VPC ids, the gateway's MCP URL — and has no reference syntax. A committed spec is
therefore a snapshot of one deployment, and a clone into another account points at the first one.

That fails in the worst way: a spec naming another account's Lambda ARNs deploys cleanly, the
gateway and its targets report READY, and every tool call then fails at invoke. So every value is
read back from the deployment that owns it.

Run after `cdk deploy` and before `agentcore deploy`; `deploy.sh` sequences it.

Exit codes:
    0   the spec matches the deployed stacks
    10  something changed, or the gateway MCP URL is not resolvable yet (a first deploy) — either
        way `agentcore deploy` must run again. `deploy.sh` acts on this.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import boto3

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = REPO_ROOT / "agent/MultiTenantTravel/agentcore/agentcore.json"
TARGETS_PATH = REPO_ROOT / "agent/MultiTenantTravel/agentcore/aws-targets.json"
IAM_POLICY_DIR = REPO_ROOT / "agent/MultiTenantTravel/app/MultiTenantTravel/policies"

# Not `AWS_REGION`, which a shell often carries for unrelated work.
REGION = os.environ.get("TRAVEL_REGION") or "us-east-1"

INFRA_STACK = "multi-tenant-travel"
AGENT_STACK = "AgentCore-MultiTenantTravel-default"
GATEWAY_ARN_OUTPUT = "GatewayToolsArn"

# The same flag `infra/` reads, so the runtime's network mode cannot disagree with whether a VPC
# was built.
PRIVATE = (os.environ.get("TRAVEL_PRIVATE") or "").lower() == "true"

# Matches the placeholder *and* a rendered value, which is what makes re-rendering idempotent.
ACCOUNT_SEGMENT = re.compile(r"(?<=:)(?:\{\{ACCOUNT\}\}|\d{12})(?=:)")
# Concrete regions only: `arn:aws:bedrock:*::foundation-model/…` wildcards the region and leaves
# the account empty, because the global inference profile's models live in other regions.
REGION_SEGMENT = re.compile(r"(arn:aws:[a-z0-9-]+:)(?:\{\{REGION\}\}|[a-z]{2}(?:-[a-z]+)+-\d)(:)")


def stack_outputs(cfn, stack: str) -> dict[str, str]:
    """Outputs of `stack`, or `{}` if it is not deployed yet — which is normal on a first pass."""
    try:
        stacks = cfn.describe_stacks(StackName=stack)["Stacks"]
    except cfn.exceptions.ClientError:
        return {}
    return {o["OutputKey"]: o["OutputValue"] for o in stacks[0].get("Outputs", [])}


def find_output(outputs: dict[str, str], needle: str, stack: str) -> str:
    """One output whose key *contains* `needle`, or a loud failure.

    Substring rather than prefix: CDK builds a logical id from the construct path plus a hash, so a
    `CfnOutput` named `policyToolArn` inside a `Tools` construct surfaces as
    `ToolspolicyToolArn7A1640C7`. Prefix-matching it finds nothing. Ambiguity is an error rather
    than "take the first": naming the wrong resource is the failure this script exists to prevent.
    """
    matches = [key for key in outputs if needle in key]
    if len(matches) != 1:
        raise SystemExit(
            f"{needle!r} matched {len(matches)} outputs in {stack}: {matches}\n"
            f"run `cd infra && TRAVEL_REGION={REGION} npm run deploy` first"
        )
    value = outputs[matches[0]]
    if not value:
        raise SystemExit(f"{matches[0]} is present but empty")
    return value


def identity_params(ssm) -> dict[str, str]:
    """The `/multi-tenant-travel/identity/*` values the infra stack publishes.

    Parameter Store rather than a CloudFormation export: an export locks the two CDK apps together,
    since CloudFormation refuses to delete one that is in use.
    """
    wanted = ["discovery-url", "cli-client-id", "web-client-id"]
    resolved: dict[str, str] = {}
    for name in wanted:
        parameter = f"/multi-tenant-travel/identity/{name}"
        try:
            resolved[name] = ssm.get_parameter(Name=parameter)["Parameter"]["Value"]
        except ssm.exceptions.ParameterNotFound:
            raise SystemExit(
                f"{parameter} not found — deploy `infra/` before rendering the agent spec"
            ) from None
    return resolved


def render_iam_policies(account: str) -> list[str]:
    """Point the runtime's `additionalPolicies` at this account's resources.

    The quietest failure in the repo if it is wrong: these grant `bedrock:ApplyGuardrail` and the
    SSM reads for the guardrail and inference-profile ids, all of which the agent treats as
    non-fatal — so a wrong account yields a working agent that is silently unguarded.
    """
    changed: list[str] = []
    for path in sorted(IAM_POLICY_DIR.glob("*.json")):
        original = path.read_text()
        rendered = REGION_SEGMENT.sub(rf"\1{REGION}\2", ACCOUNT_SEGMENT.sub(account, original))
        if rendered != original:
            path.write_text(rendered)
            changed.append(path.name)
    return changed


def main() -> int:
    cfn = boto3.client("cloudformation", region_name=REGION)
    ssm = boto3.client("ssm", region_name=REGION)
    account = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]

    infra = stack_outputs(cfn, INFRA_STACK)
    if not infra:
        raise SystemExit(
            f"stack {INFRA_STACK} is not deployed in {account}/{REGION}.\n"
            f"run `cd infra && TRAVEL_REGION={REGION} npm run deploy` first"
        )
    agent = stack_outputs(cfn, AGENT_STACK)
    identity = identity_params(ssm)

    spec = json.loads(SPEC_PATH.read_text())
    before = json.dumps(spec, sort_keys=True)
    runtime = spec["runtimes"][0]
    gateway = spec["agentCoreGateways"][0]
    notes: list[str] = []

    # Keyed off the target's name, which matches the family key in `infra/lib/tools.ts`.
    for target in gateway.get("targets", []):
        config = target.get("lambdaFunctionArn")
        if not config:
            continue
        arn = find_output(infra, f"{target['name']}ToolArn", INFRA_STACK)
        if config.get("lambdaArn") != arn:
            config["lambdaArn"] = arn
            notes.append(f"target {target['name']}: {arn}")

    # **Both**: the runtime and the gateway validate inbound tokens independently, so each carries
    # its own authorizer. Rendering only the runtime's leaves the gateway trusting another
    # account's pool, which then rejects every token the runtime just accepted.
    clients = [identity["cli-client-id"], identity["web-client-id"]]
    for label, holder in (("runtime", runtime), ("gateway", gateway)):
        authorizer = (holder.get("authorizerConfiguration") or {}).get("customJwtAuthorizer")
        if not authorizer:
            continue
        if authorizer.get("discoveryUrl") != identity["discovery-url"]:
            authorizer["discoveryUrl"] = identity["discovery-url"]
            notes.append(f"{label} discoveryUrl: {identity['discovery-url']}")
        if authorizer.get("allowedClients") != clients:
            authorizer["allowedClients"] = clients
            notes.append(f"{label} allowedClients: {', '.join(clients)}")

    # Not committed: the VPC is opt-in, so a default deploy builds none — and a spec still saying
    # `VPC` would send the runtime looking for subnets that were never created.
    if PRIVATE:
        vpc = find_output(infra, "VpcId", INFRA_STACK)
        subnets = find_output(infra, "PrivateSubnetIds", INFRA_STACK).split(",")
        security_group = find_output(infra, "ComputeSecurityGroupId", INFRA_STACK)
        wanted = {"vpcId": vpc, "subnets": subnets, "securityGroups": [security_group]}
        if runtime.get("networkMode") != "VPC" or runtime.get("networkConfig") != wanted:
            runtime["networkMode"] = "VPC"
            runtime["networkConfig"] = wanted
            notes.append(f"networkConfig: {vpc} / {len(subnets)} subnets / {security_group}")
    elif runtime.get("networkMode") != "PUBLIC" or "networkConfig" in runtime:
        runtime["networkMode"] = "PUBLIC"
        runtime.pop("networkConfig", None)
        notes.append("networkMode: PUBLIC (no VPC — set TRAVEL_PRIVATE=true for the private one)")

    # Derived from the gateway ARN, because the id in the hostname is the id in the ARN. Not
    # resolvable on a first deploy, which is half of why a fresh account needs two passes —
    # `sync_policies.py` is the other half.
    pending_url = False
    if agent:
        gateway_arn = find_output(agent, GATEWAY_ARN_OUTPUT, AGENT_STACK)
        gateway_id = gateway_arn.rsplit("/", 1)[-1]
        url = f"https://{gateway_id}.gateway.bedrock-agentcore.{REGION}.amazonaws.com/mcp"
        env = runtime.setdefault("envVars", [])
        entry = next((e for e in env if e.get("name") == "GATEWAY_MCP_URL"), None)
        if entry is None:
            env.append({"name": "GATEWAY_MCP_URL", "value": url})
            notes.append(f"GATEWAY_MCP_URL: {url}")
        elif entry.get("value") != url:
            entry["value"] = url
            notes.append(f"GATEWAY_MCP_URL: {url}")
    else:
        pending_url = True

    changed = json.dumps(spec, sort_keys=True) != before
    if changed:
        SPEC_PATH.write_text(json.dumps(spec, indent=2) + "\n")

    # A wrong account here fails with `Target "default" not found`, which is at least loud.
    targets = json.loads(TARGETS_PATH.read_text())
    target_changed = False
    for entry in targets:
        if entry.get("account") != account or entry.get("region") != REGION:
            entry["account"], entry["region"] = account, REGION
            target_changed = True
    if target_changed:
        TARGETS_PATH.write_text(json.dumps(targets, indent=2) + "\n")
        notes.append(f"aws-targets.json: {account}/{REGION}")

    iam_changed = render_iam_policies(account)
    for name in iam_changed:
        notes.append(f"policies/{name}: account {account}, region {REGION}")

    print(f"Rendered agentcore.json for {account}/{REGION}")
    if notes:
        for note in notes:
            print(f"  {note}")
    else:
        print("  (already matched the deployed stacks)")

    if pending_url:
        print("")
        print(f"  {AGENT_STACK} is not deployed yet, so GATEWAY_MCP_URL could not be resolved.")
        print("  Deploy the agent, then run this again — `deploy.sh` does both, in that order.")

    return 10 if (notes or pending_url) else 0


if __name__ == "__main__":
    sys.exit(main())
