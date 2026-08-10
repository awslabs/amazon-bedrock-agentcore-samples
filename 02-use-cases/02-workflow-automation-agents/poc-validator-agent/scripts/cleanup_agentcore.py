#!/usr/bin/env python3
"""Delete orphaned AgentCore control-plane resources for this sample.

`agentcore deploy` against an emptied schema removes the CloudFormation stack,
but control-plane resources occasionally survive a partial or interrupted
deploy. This sweeps them.

Follows the API sequence used by
02-use-cases/02-workflow-automation-agents/event-driven-claims-agent/scripts/cleanup_agentcore.py:
targets before gateways, policies before policy engines, endpoints before
runtimes — the delete order matters because parents refuse to go while children
exist.

    python scripts/cleanup_agentcore.py --region us-west-2          # dry run
    python scripts/cleanup_agentcore.py --region us-west-2 --apply
"""

import argparse
import sys

PREFIXES = ("PocValidator", "pocvalidator")


def matches_project(name: str) -> bool:
    return bool(name) and name.startswith(PREFIXES)


def _delete_safe(client, method: str, dry_run: bool, **kwargs) -> None:
    label = ", ".join(f"{k}={v}" for k, v in kwargs.items())
    if dry_run:
        print(f"  [dry-run] {method}({label})")
        return
    try:
        getattr(client, method)(**kwargs)
        print(f"  deleted  {method}({label})")
    except Exception as exc:  # noqa: BLE001 — best-effort sweep
        print(f"  skipped  {method}({label}): {exc}")


def _paginate(client, method: str, key: str):
    try:
        response = getattr(client, method)()
    except Exception as exc:  # noqa: BLE001
        print(f"  could not list via {method}: {exc}")
        return []
    return response.get(key, [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True)
    parser.add_argument("--apply", action="store_true",
                        help="actually delete; omit for a dry run")
    args = parser.parse_args()
    dry_run = not args.apply

    try:
        import boto3
    except ImportError:
        print("boto3 is required: pip install boto3", file=sys.stderr)
        return 1

    client = boto3.client("bedrock-agentcore-control", region_name=args.region)
    mode = "DRY RUN — nothing will be deleted" if dry_run else "APPLYING DELETIONS"
    print(f"{mode}  (region {args.region})\n")

    # Gateways: targets first, then the gateway.
    print("Gateways")
    for gateway in _paginate(client, "list_gateways", "items"):
        name = gateway.get("name", "")
        if not matches_project(name):
            continue
        gateway_id = gateway.get("gatewayId")
        for target in _paginate_targets(client, gateway_id):
            _delete_safe(client, "delete_gateway_target", dry_run,
                         gatewayIdentifier=gateway_id,
                         targetId=target.get("targetId"))
        _delete_safe(client, "delete_gateway", dry_run, gatewayIdentifier=gateway_id)

    # Policy engines: policies first.
    print("\nPolicy engines")
    for engine in _paginate(client, "list_policy_engines", "items"):
        if not matches_project(engine.get("name", "")):
            continue
        engine_id = engine.get("policyEngineId")
        try:
            policies = client.list_policies(policyEngineId=engine_id).get("items", [])
        except Exception:  # noqa: BLE001
            policies = []
        for policy in policies:
            _delete_safe(client, "delete_policy", dry_run,
                         policyEngineId=engine_id, policyId=policy.get("policyId"))
        _delete_safe(client, "delete_policy_engine", dry_run, policyEngineId=engine_id)

    # Runtimes: endpoints first.
    print("\nRuntimes")
    for runtime in _paginate(client, "list_agent_runtimes", "agentRuntimes"):
        if not matches_project(runtime.get("agentRuntimeName", "")):
            continue
        runtime_id = runtime.get("agentRuntimeId")
        try:
            endpoints = client.list_agent_runtime_endpoints(
                agentRuntimeId=runtime_id
            ).get("runtimeEndpoints", [])
        except Exception:  # noqa: BLE001
            endpoints = []
        for endpoint in endpoints:
            _delete_safe(client, "delete_agent_runtime_endpoint", dry_run,
                         agentRuntimeId=runtime_id,
                         endpointName=endpoint.get("name"))
        _delete_safe(client, "delete_agent_runtime", dry_run, agentRuntimeId=runtime_id)

    # Memories.
    print("\nMemories")
    for memory in _paginate(client, "list_memories", "memories"):
        if not matches_project(memory.get("id", "") or memory.get("name", "")):
            continue
        _delete_safe(client, "delete_memory", dry_run, memoryId=memory.get("id"))

    print(
        "\nDone."
        + ("\nRe-run with --apply to delete." if dry_run else "")
        + "\nCheck ECR repositories and CloudWatch log groups separately — this "
        "script only sweeps AgentCore control-plane resources."
    )
    return 0


def _paginate_targets(client, gateway_id):
    if not gateway_id:
        return []
    try:
        return client.list_gateway_targets(gatewayIdentifier=gateway_id).get("items", [])
    except Exception as exc:  # noqa: BLE001
        print(f"  could not list targets for {gateway_id}: {exc}")
        return []


if __name__ == "__main__":
    raise SystemExit(main())
