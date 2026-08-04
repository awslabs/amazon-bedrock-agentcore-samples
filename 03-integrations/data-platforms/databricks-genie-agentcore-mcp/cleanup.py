"""Delete every AWS resource this sample created.

Removes the gateway target, the Databricks OAuth2 credential provider and the
gateway itself, then deletes the local state file. Run `agentcore destroy`
separately to remove the deployed Runtime agent.

Usage:
    python cleanup.py
    python cleanup.py --yes    # skip the confirmation prompt
"""

import argparse
import json
import os
import time

import boto3

from config import CREDENTIAL_PROVIDER_NAME, STATE_FILE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes", action="store_true", help="delete without confirmation"
    )
    args = parser.parse_args()

    try:
        with open(STATE_FILE) as f:
            config = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"{STATE_FILE} not found — nothing to clean up.")

    gateway_id = config["gateway_id"]
    target_id = config["target_id"]

    print("This will delete:")
    print(f"  Gateway target        {target_id}")
    print(f"  Credential provider   {CREDENTIAL_PROVIDER_NAME}")
    print(f"  Gateway               {gateway_id}")
    if not args.yes:
        if input("Proceed? [y/N] ").strip().lower() not in ("y", "yes"):
            raise SystemExit("Aborted.")

    agentcore = boto3.client("bedrock-agentcore-control", region_name=config["region"])
    failures = []

    try:
        agentcore.delete_gateway_target(
            gatewayIdentifier=gateway_id, targetId=target_id
        )
        print("Deleted gateway target.")
    except Exception as exc:  # already gone
        print(f"Could not delete gateway target: {exc}")
        failures.append("gateway target")

    try:
        agentcore.delete_oauth2_credential_provider(name=CREDENTIAL_PROVIDER_NAME)
        print("Deleted credential provider.")
    except Exception as exc:
        print(f"Could not delete credential provider: {exc}")
        failures.append("credential provider")

    # Target deletion is asynchronous. DeleteGateway fails while any target is
    # still attached, so wait for the target list to drain first.
    print("Waiting for targets to detach...")
    for _ in range(30):
        try:
            remaining = agentcore.list_gateway_targets(
                gatewayIdentifier=gateway_id
            ).get("items", [])
        except Exception:
            remaining = []
        if not remaining:
            break
        time.sleep(5)

    try:
        agentcore.delete_gateway(gatewayIdentifier=gateway_id)
        print("Deleted gateway.")
    except Exception as exc:
        print(f"Could not delete gateway: {exc}")
        failures.append("gateway")

    if failures:
        # Keep the state file so the command can be re-run to finish the job.
        print(
            f"\nLeft {STATE_FILE} in place — re-run `python cleanup.py` to retry: "
            + ", ".join(failures)
        )
    else:
        os.remove(STATE_FILE)
        print(f"Removed {STATE_FILE}")

    print("\nRun `agentcore destroy` to remove the deployed Runtime agent.")


if __name__ == "__main__":
    main()
