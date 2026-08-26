"""Attach the request interceptor and header allowlist to the deployed gateway.

    uv run python scripts/configure_gateway.py

**A post-deploy step because the CLI does not own it.** `agentcore.json` has no
interceptor field and no `metadataConfiguration`, and hand-editing CLI-generated CDK is
forbidden by `AGENTS.md` — so these two settings are applied with
`bedrock-agentcore-control` after `agentcore deploy`.

Three things get configured, and **the demo is broken without any of them**:

0. **`lambda:InvokeFunction` on the interceptor, granted to the gateway's execution
   role.** The CLI generates that role from `agentcore.json`, which knows about *targets*
   — so it grants invoke on the tool Lambda and nothing else. The interceptor is
   therefore un-invokable, and the symptom is brutal: every MCP call returns a generic
   500 ("An internal error occurred"), the interceptor has **zero log streams**, and
   `get_gateway` still reports the interceptor as attached. Nothing points at IAM.

1. **The interceptor**, with `passRequestHeaders: true`. Without that flag the
   interceptor never receives `Authorization` and cannot verify anything.
2. **`allowedRequestHeaders` on every target.** Interceptor-injected headers are
   *silently dropped* unless the target allowlists them (the sole exception is
   `Authorization`). The symptom is a tool that refuses for lack of a tenant, which reads
   like a broken interceptor rather than a missing allowlist entry.

Idempotent: re-running updates in place, so it is safe to chain after every deploy.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import boto3

# Not a literal: a reader deploying to another region would otherwise get a script that
# addresses us-east-1 while their stack is elsewhere. Same default and same reason as
# `deploy.sh` — `TRAVEL_REGION` wins over an ambient `AWS_REGION` set for other work.
REGION = os.environ.get("TRAVEL_REGION") or os.environ.get("AWS_REGION") or "us-east-1"
GATEWAY_NAME = "MultiTenantTravel-Tools"

# Must match `tools/common/context.py` and `infra/lambda/interceptor/index.mjs`.
# The first three are verified identity, injected by the interceptor from JWT claims. The
# fourth is the conversation id, forwarded by the agent for audit correlation only — it becomes
# an STS session tag so a CloudTrail data event traces back to one conversation, and no policy
# keys off it.
#
# **Allowlisting here is not optional.** Except for `Authorization`, an interceptor-injected
# header is dropped unless the target names it, and the failure is silent: the tool simply sees
# no value. For the identity headers that reads as a broken interceptor; for the session id it
# reads as nothing at all, which is worse — tools keep working and the audit trail quietly loses
# attribution.
PROPAGATED_HEADERS = [
    "X-Tenant-Id",
    "X-Traveler-Id",
    "X-Traveler-Role",
    "X-Session-Id",
]


def grant_invoke_to_gateway_role(iam, role_arn: str, interceptor_arn: str) -> None:
    """Let the gateway's own role invoke the interceptor.

    A resource policy on the Lambda (service principal `bedrock-agentcore.amazonaws.com`)
    is *not* sufficient — the gateway assumes its execution role, so that identity needs
    the permission too. Written as an inline policy on the CLI-managed role rather than in
    CDK, because the role belongs to the CLI's stack and editing generated CDK is
    forbidden by `AGENTS.md`.
    """
    role_name = role_arn.rsplit("/", 1)[-1]
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="InvokeRequestInterceptor",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "lambda:InvokeFunction",
                        # Scoped to this one function: the gateway has no business
                        # invoking anything else in the account.
                        "Resource": [interceptor_arn, f"{interceptor_arn}:*"],
                    }
                ],
            }
        ),
    )
    print(f"  granted {role_name} invoke on the interceptor")


def grant_workload_identity(iam, role_arn: str, gateway_id: str) -> None:
    """Let the gateway mint a workload access token for itself.

    **The second permission the generated role is missing, and it fails exactly like the first.**
    The
    gateway fetches a workload token before invoking a target, calling
    `bedrock-agentcore:GetWorkloadAccessToken` on its own workload identity. Without the grant every
    `tools/call` returns `"An internal error occurred. Please retry later."` — reads included — with
    **zero invocations of any tool Lambda**, while the interceptor logs
    `injected verified tenant context` and every target reports `READY`.

    Nothing in the control plane looks wrong, which is what makes this expensive to find: gateway
    READY, targets READY with correct ARNs and allowlists, Cedar `ACTIVE` in `ENFORCE`, IAM
    permitting `lambda:InvokeFunction` on all nine tools, and the tool Lambda answering correctly
    when invoked directly. The cause is visible only with `exceptionLevel: DEBUG` on the gateway,
    which replaces the generic message with the real `403`. Reach for that switch early next time —
    every cheaper check passes.

    **Why the L3 construct does not do this.** `AgentCoreMcp` grants these actions only when a
    target
    declares `OAUTH` or `API_KEY` outbound auth (`Gateway.js`, the `oauthTargets` / `apiKeyTargets`
    branches). Every target here uses `GATEWAY_IAM_ROLE`, so neither branch fires. The construct's
    own
    warning for imported roles lists `GetWorkloadAccessToken` among the permissions a role must
    carry — so the requirement is known, it is simply not granted on this path.

    Scoped to this gateway's own workload identity, and to `GetWorkloadAccessToken` alone: the
    `ForJWT` and `ForUserId` variants exist for on-behalf-of token exchange, which this gateway does
    not do. **This does not widen what any tool can reach** — it lets the gateway obtain a token for
    itself. Tenancy still comes from the interceptor's verified claims, and Cedar still authorises
    every call.
    """
    role_name = role_arn.rsplit("/", 1)[-1]
    account = role_arn.split(":")[4]
    directory = f"arn:aws:bedrock-agentcore:{REGION}:{account}:workload-identity-directory/default"
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="GatewayWorkloadIdentity",
        PolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "bedrock-agentcore:GetWorkloadAccessToken",
                        # The directory itself and this gateway's identity within it. Not a
                        # wildcard:
                        # another gateway's workload identity is none of this role's business.
                        "Resource": [
                            directory,
                            f"{directory}/workload-identity/{gateway_id}",
                        ],
                    }
                ],
            }
        ),
    )
    print(f"  granted {role_name} a workload access token on {gateway_id}")


def wait_until_ready(client, gateway_id: str, *, timeout_seconds: int = 180) -> None:
    """Block until the gateway leaves UPDATING.

    Not optional: `update_gateway` returns before the change settles, and the very next
    `update_gateway_target` call fails with "Cannot perform operation ... when gateway is
    in UPDATING status". Sequencing two control-plane calls in one script needs this
    barrier between them.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status = client.get_gateway(gatewayIdentifier=gateway_id)["status"]
        if status == "READY":
            return
        if status in {"FAILED", "DELETING"}:
            raise SystemExit(f"gateway entered {status}")
        time.sleep(3)
    raise SystemExit("gateway did not become READY in time")


def find_gateway(client, name: str) -> dict:
    """Locate the gateway by name, following pagination.

    `list_gateways` paginates, and ignoring `nextToken` means an existence check quietly
    misses resources once an account accumulates a few.
    """
    token = None
    while True:
        kwargs = {"nextToken": token} if token else {}
        page = client.list_gateways(**kwargs)
        for item in page.get("items", []):
            if item.get("name") == name:
                return item
        token = page.get("nextToken")
        if not token:
            raise SystemExit(f"gateway {name!r} not found — run `agentcore deploy` first")


def main(debug: bool | None = None) -> int:
    """Configure the gateway. `debug` is tri-state: `None` leaves `exceptionLevel` as it is."""
    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    ssm = boto3.client("ssm", region_name=REGION)

    interceptor_param = "/multi-tenant-travel/gateway/interceptor-arn"
    interceptor_arn = ssm.get_parameter(Name=interceptor_param)["Parameter"]["Value"]

    gateway = find_gateway(control, GATEWAY_NAME)
    gateway_id = gateway["gatewayId"]
    print(f"Gateway {GATEWAY_NAME} ({gateway_id})")

    current = control.get_gateway(gatewayIdentifier=gateway_id)

    # **`update_gateway` is a full replace, not a patch: omitting a field CLEARS it.**
    #
    # This bit us for real. An earlier version passed through the authorizer but not the
    # policy engine, so running this script after `agentcore deploy` silently detached
    # Cedar — leaving `policyEngineConfiguration: null` and a gateway that *looked*
    # governed while enforcing nothing. A policy engine that appears attached but never
    # denies is worse than none, because it reads as working.
    #
    # Everything not being deliberately changed is therefore read back and passed through.
    # `_passthrough` below covers the optional fields; add to it rather than to this dict
    # when the service grows a new one.
    update = {
        "gatewayIdentifier": gateway_id,
        "name": current["name"],
        "roleArn": current["roleArn"],
        "protocolType": current["protocolType"],
        "authorizerType": current["authorizerType"],
        "authorizerConfiguration": current["authorizerConfiguration"],
        "interceptorConfigurations": [
            {
                "interceptor": {"lambda": {"arn": interceptor_arn}},
                # REQUEST only. A RESPONSE interceptor is where response-side redaction
                # would live; adding one with nothing to do would be an empty hop per call.
                "interceptionPoints": ["REQUEST"],
                # Without this the interceptor cannot see the bearer token, so it cannot
                # verify the caller — the single most important line in this file.
                "inputConfiguration": {"passRequestHeaders": True},
            }
        ],
    }
    # Optional fields that must survive the replace. `policyEngineConfiguration` is the one
    # that caused a silent loss of Cedar enforcement; the rest are here so the next
    # addition does not repeat it.
    _passthrough = (
        "description",
        "policyEngineConfiguration",
        "protocolConfiguration",
        "exceptionLevel",
        "kmsKeyArn",
        "wafConfiguration",
        "customTransformConfiguration",
    )
    for field in _passthrough:
        if (value := current.get(field)) is not None:
            update[field] = value

    # **`exceptionLevel` is the switch that turns the gateway's generic 500 into the real cause**,
    # and
    # it is worth knowing about before spending an afternoon on the alternative. `DEBUG` makes a
    # failed
    # `tools/call` return the underlying error — the missing-IAM `403` in `grant_workload_identity`
    # was
    # invisible without it, because every other signal (gateway READY, targets READY, Cedar ACTIVE,
    # interceptor logging normally) looked correct.
    #
    # Explicit flags rather than a hand-written boto3 call, and **off by default**: a debug error
    # can
    # carry internal detail into a tool response, so it is a deliberate, temporary switch. It is
    # also
    # in the passthrough list above, which means it *survives* a plain re-run — clearing it has to
    # be
    # asked for.
    if debug is True:
        update["exceptionLevel"] = "DEBUG"
    elif debug is False:
        update.pop("exceptionLevel", None)

    # `UpdateGateway` takes `{arn, mode}` here — **not** `policyEngineName`, which is what
    # `agentcore.json` uses. The two layers name the same thing differently, so the read-back
    # value passes through as-is; the mode is preserved because LOG_ONLY -> ENFORCE is a
    # deliberate act this script must not undo.
    if engine := update.get("policyEngineConfiguration"):
        update["policyEngineConfiguration"] = {
            "arn": engine["arn"],
            "mode": engine.get("mode", "LOG_ONLY"),
        }

    # IAM first, both grants: attaching an interceptor the role cannot invoke breaks every MCP call,
    # and so does a role that cannot mint its own workload token. Same symptom for both — a generic
    # 500 on every tool — so they are applied together, before the attachment that needs them.
    iam = boto3.client("iam", region_name=REGION)
    grant_invoke_to_gateway_role(iam, current["roleArn"], interceptor_arn)
    grant_workload_identity(iam, current["roleArn"], gateway_id)

    control.update_gateway(**update)
    print(f"  attached interceptor {interceptor_arn.rsplit(':', 1)[-1]} (passRequestHeaders=true)")
    if engine := update.get("policyEngineConfiguration"):
        print(f"  preserved policy engine ({engine['mode']}) {engine['arn'].rsplit('/', 1)[-1]}")
    else:
        # Loud, because a silently detached policy engine is a gateway that looks governed
        # and enforces nothing.
        print("  WARNING: no policy engine attached to this gateway")

    wait_until_ready(control, gateway_id)

    # Allowlist the injected headers on every target, or they never arrive.
    targets = control.list_gateway_targets(gatewayIdentifier=gateway_id).get("items", [])
    for target in targets:
        target_id = target["targetId"]
        # `targetId`, not `targetIdentifier` — the gateway-level parameter is
        # `gatewayIdentifier` but the target-level one is not symmetrical.
        detail = control.get_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)
        control.update_gateway_target(
            gatewayIdentifier=gateway_id,
            targetId=target_id,
            name=detail["name"],
            targetConfiguration=detail["targetConfiguration"],
            credentialProviderConfigurations=detail.get("credentialProviderConfigurations", []),
            metadataConfiguration={"allowedRequestHeaders": PROPAGATED_HEADERS},
        )
        print(f"  target {detail['name']}: allowlisted {', '.join(PROPAGATED_HEADERS)}")

    print(f"\nGateway URL: {current['gatewayUrl']}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--debug-errors",
        dest="debug",
        action="store_true",
        default=None,
        help="return the gateway's real error instead of a generic 500 (see the docstring)",
    )
    group.add_argument(
        "--no-debug-errors",
        dest="debug",
        action="store_false",
        help="clear exceptionLevel, which a plain re-run deliberately preserves",
    )
    sys.exit(main(debug=parser.parse_args().debug))
