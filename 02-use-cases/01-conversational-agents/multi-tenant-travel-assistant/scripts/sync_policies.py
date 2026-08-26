"""Sync `agent/MultiTenantTravel/policies/*.cedar` into `agentcore.json`'s policy engine.

    uv run python scripts/sync_policies.py

**The `.cedar` files are the source of truth.** `agentcore.json` needs each rule as an
inline `statement`, but a readable Cedar file holds several rules with the comments that
explain *why* each exists. Hand-copying them into JSON would (a) lose the comments, which
are the part a reviewer actually needs, and (b) create two places a policy can be edited.

So this script splits each file on its `// --- Label ---` section headers, carries the
comment block into the statement, and derives the policy **name** from the label — because
that name is what appears in a deny decision log. `common_rule_2` tells an operator
nothing; `common_fail_closed_no_tenant` tells them exactly which rule fired.

It also **substitutes the deployed gateway ARN** for the `{{GATEWAY_ARN}}` placeholder the
`.cedar` sources carry. That indirection exists because AgentCore requires a *specific*
gateway ARN whenever a rule names specific actions (the `resource is AgentCore::Gateway`
type check is only allowed against any action), and the gateway's id is generated per
deploy — so a committed literal ARN names another account's gateway, matches nothing, and
an engine in ENFORCE then denies every tool call while the gateway, its targets and the
runtime all report READY. That is the worst failure shape in the whole sample: silent,
total, and structurally invisible.

Run after editing any `.cedar` file, then `agentcore deploy`.

Exit codes:
    0   the spec names the live gateway and nothing moved — nothing further is required
    10  **the deployed policy does not name the live gateway.** Either the ARN just changed, or
        it is still the fail-closed placeholder. Either way `agentcore deploy` must run again
        before the engine authorises anything. `deploy.sh` acts on this.

        Deliberately *not* conditional on the value having changed this run: a re-run after a
        partial deploy would otherwise report success over a policy that still permits nothing.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICIES_DIR = REPO_ROOT / "agent/MultiTenantTravel/policies"
SPEC_PATH = REPO_ROOT / "agent/MultiTenantTravel/agentcore/agentcore.json"

ENGINE_NAME = "Policy"

# Not `AWS_REGION`, which a shell often carries for unrelated work.
REGION = os.environ.get("TRAVEL_REGION") or "us-east-1"

# Matched by prefix, because CDK appends a hash that shifts when the stack is regenerated.
AGENT_STACK = "AgentCore-MultiTenantTravel-default"
GATEWAY_ARN_OUTPUT = "GatewayToolsArn"

GATEWAY_PLACEHOLDER = "{{GATEWAY_ARN}}"

# **The mode a re-attached engine gets.** Pass one detaches the engine entirely (see `main`), so the
# mode cannot be carried in the spec across that gap. An existing mode is still preserved when there
# is one, which keeps a deliberate flip to `LOG_ONLY` from being undone by the next sync.
DEFAULT_MODE = "ENFORCE"

ARN_IN_STATEMENT = re.compile(r'AgentCore::Gateway::"(?P<arn>[^"]+)"')

# Section header that starts each rule: `// --- Human label ------`
SECTION = re.compile(r"^// --- (?P<label>.+?) -*$", re.MULTILINE)

# Cedar names allow letters, digits and underscores only, and must start with a letter.
NAME_SAFE = re.compile(r"[^A-Za-z0-9]+")


def _policy_name(stem: str, label: str) -> str:
    """`common` + "Fail closed on a token with no tenant context" -> `common_fail_closed…`.

    Kept readable rather than hashed: this string is what an operator sees in a deny log,
    so it has to say which rule fired.
    """
    name = NAME_SAFE.sub("_", f"{stem}_{label.lower()}").strip("_")
    return name[:48].rstrip("_")


def arn_in_spec(spec: dict) -> str | None:
    """The gateway ARN already in the spec, so a credential-less run does not reset a correctly
    narrowed policy back to the sentinel."""
    for engine in spec.get("policyEngines") or []:
        for policy in engine.get("policies") or []:
            match = ARN_IN_STATEMENT.search(policy.get("statement", ""))
            if match:
                return match.group("arn")
    return None


def account_of(arn: str) -> str | None:
    parts = arn.split(":")
    return parts[4] if len(parts) > 4 and parts[4] else None


def gateway_exists(arn: str) -> bool:
    """Whether `arn` names a gateway that is actually there.

    **The check that stops a rolled-back stack.** `AWS::BedrockAgentCore::Policy` confirms the
    gateway in its `resource` clause exists, and a policy that fails takes the gateway, runtime and
    memory down with it. A cached ARN from a previous deploy — or from another account — looks
    perfectly valid in the spec and is only wrong at deploy time, so it is verified here instead.
    """
    try:
        import boto3

        boto3.client("bedrock-agentcore-control", region_name=REGION).get_gateway(
            gatewayIdentifier=arn.rsplit("/", 1)[-1]
        )
        return True
    except Exception:
        return False


def resolve_gateway_arn(spec: dict) -> tuple[str, str]:
    """(arn, how it was resolved), most explicit source first:

      1. `TRAVEL_GATEWAY_ARN` — an explicit override.
      2. The agent stack's CloudFormation output — the live gateway.
      3. The ARN already in the spec, **only if it names the account being deployed to**.
      4. A fail-closed sentinel in the caller's account, for a first deploy.

    Step 3's account check is the point: reusing a cached ARN keeps an offline re-sync
    non-destructive, but reusing one from a *different* account reproduces the bug this exists to
    kill — a policy naming a gateway the account does not own, denying everything while every
    resource reports healthy.
    """
    override = os.environ.get("TRAVEL_GATEWAY_ARN")
    if override:
        return override, "TRAVEL_GATEWAY_ARN"

    account = None
    try:
        import boto3

        account = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
        cfn = boto3.client("cloudformation", region_name=REGION)
        outputs: dict[str, str] = {}
        try:
            stacks = cfn.describe_stacks(StackName=AGENT_STACK)["Stacks"]
            outputs = {o["OutputKey"]: o["OutputValue"] for o in stacks[0].get("Outputs", [])}
        except cfn.exceptions.ClientError:
            print(f"  ({AGENT_STACK} not deployed in {account} yet)")
        matches = [key for key in outputs if key.startswith(GATEWAY_ARN_OUTPUT)]
        # Ambiguity is an error rather than "take the first": naming the wrong gateway here
        # denies live traffic, which is exactly the failure this indirection exists to prevent.
        if len(matches) > 1:
            raise SystemExit(
                f"{GATEWAY_ARN_OUTPUT!r} matched {len(matches)} outputs in {AGENT_STACK}: {matches}"
            )
        if matches and outputs[matches[0]]:
            return outputs[matches[0]], f"{AGENT_STACK} output"
    except SystemExit:
        raise
    except Exception as error:  # no credentials, no boto3, no network
        print(f"  (no AWS access: {type(error).__name__} — falling back to agentcore.json)")

    existing = arn_in_spec(spec)
    if existing and not gateway_exists(existing):
        print(f"  discarding {existing}: no such gateway in {account or 'this account'}")
        existing = None
    if existing:
        existing_account = account_of(existing)
        if account is None:
            return existing, "unchanged from agentcore.json (offline, account unverified)"
        if existing_account == account:
            return existing, "unchanged from agentcore.json"
        print(
            f"  DISCARDING the cached gateway ARN: it names account {existing_account}, "
            f"and this deploy targets {account}."
        )

    return "", "no gateway deployed yet"


def split_rules(path: Path) -> list[tuple[str, str]]:
    """(label, statement) per rule, keeping each rule's explanatory comments.

    Splitting on the section header rather than on `permit(`/`forbid(` is deliberate: the
    comment block above a rule is part of the rule as far as a reader is concerned, and it
    must travel with it into the deployed policy.
    """
    text = path.read_text()
    matches = list(SECTION.finditer(text))
    if not matches:
        # A file may legitimately hold only prose: `arranger.cedar` documents *why* a rule
        # that seemed obvious is not expressible in Cedar, which is worth keeping beside the
        # policies rather than losing to a commit message. Skipped, not an error — but
        # announced, so an empty file is never mistaken for an enforced one.
        if re.search(r"^(?:permit|forbid)\(", text, re.MULTILINE):
            raise SystemExit(
                f"{path.name} contains a rule but no `// --- Label ---` header — add one so "
                "the policy gets a meaningful name in deny logs"
            )
        print(f"  (skipped {path.name}: documentation only, no rules)")
        return []

    rules: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        statement = text[start:end].strip()
        if not re.search(r"^(?:permit|forbid)\(", statement, re.MULTILINE):
            raise SystemExit(
                f"{path.name}: section {match.group('label')!r} contains no permit/forbid"
            )
        rules.append((match.group("label"), statement))
    return rules


def main() -> int:
    if not POLICIES_DIR.is_dir():
        raise SystemExit(f"no policies directory at {POLICIES_DIR}")

    spec = json.loads(SPEC_PATH.read_text())
    previous_arn = arn_in_spec(spec)
    gateway_arn, source = resolve_gateway_arn(spec)
    gateway = spec["agentCoreGateways"][0]

    # **No gateway yet: detach the engine rather than name a gateway that does not exist.**
    #
    # `AWS::BedrockAgentCore::Policy` validates the gateway in its `resource` clause at deploy
    # time — *"Failed to confirm existence on AgentCore Gateway"* — and a failed policy rolls the
    # whole stack back, taking the gateway, runtime and memory with it. So a placeholder ARN cannot
    # be deployed at all; the only order the service permits is gateway first, Cedar second.
    #
    # The window that leaves is a gateway with no authorisation, on a first deploy, before any
    # traffic exists. `deploy.sh` closes it in the same run and fails loudly if it cannot.
    if not gateway_arn:
        spec.pop("policyEngines", None)
        gateway.pop("policyEngineConfiguration", None)
        SPEC_PATH.write_text(json.dumps(spec, indent=2) + "\n")
        print(f"Cedar NOT attached — {source}.")
        print("  The policy resource refuses to reference a gateway that does not exist, so the")
        print("  gateway is created first and Cedar is attached on a second pass. `deploy.sh` does")
        print("  both, in that order, and stops if the second pass does not happen.")
        return 10

    policies = []
    for path in sorted(POLICIES_DIR.glob("*.cedar")):
        for label, statement in split_rules(path):
            statement = statement.replace(GATEWAY_PLACEHOLDER, gateway_arn)
            policies.append(
                {
                    "name": _policy_name(path.stem, label),
                    "description": label[:200],
                    "statement": statement,
                    "sourceFile": f"policies/{path.name}",
                    # A policy that fails to typecheck against the gateway's schema silently never
                    # matches — worse than a deploy error, because it looks like enforcement works.
                    "validationMode": "FAIL_ON_ANY_FINDINGS",
                }
            )

    if not policies:
        raise SystemExit("no Cedar rules found")

    # Caught here, where the message can say why, rather than as a typecheck failure at deploy.
    stale = [p["name"] for p in policies if GATEWAY_PLACEHOLDER in p["statement"]]
    if stale:
        raise SystemExit(f"placeholder left unsubstituted in: {', '.join(stale)}")

    spec["policyEngines"] = [
        {
            "name": ENGINE_NAME,
            "description": "Cedar authorisation for the travel tools — evaluated at the Gateway",
            "policies": policies,
        }
    ]

    # An existing mode wins, so a deliberate flip to LOG_ONLY survives the next sync. Pass one
    # detached the engine, so when it is re-attached there is nothing to preserve and
    # `DEFAULT_MODE` applies.
    existing = gateway.get("policyEngineConfiguration") or {}
    gateway["policyEngineConfiguration"] = {
        "policyEngineName": ENGINE_NAME,
        "mode": existing.get("mode", DEFAULT_MODE),
    }

    SPEC_PATH.write_text(json.dumps(spec, indent=2) + "\n")

    print(
        f"Synced {len(policies)} Cedar rule(s) into {ENGINE_NAME} "
        f"(mode: {gateway['policyEngineConfiguration']['mode']})"
    )
    for policy in policies:
        print(f"  {policy['name']:<46} {policy['sourceFile']}")
    print(f"  gateway: {gateway_arn}")
    print(f"           via {source}")

    if previous_arn != gateway_arn:
        print("")
        print(f"  GATEWAY ARN CHANGED: {previous_arn or '(none)'} -> {gateway_arn}")
        print("  Run `agentcore deploy` again so the policy engine names the live gateway.")
        return 10
    return 0


if __name__ == "__main__":
    sys.exit(main())
