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

from config import CREDENTIAL_PROVIDER_NAME, IAM_POLICY_NAME, STATE_FILE


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
    if config.get("role_arn"):
        print(f"  IAM role              {config['role_arn'].split('/')[-1]}")
    if (config.get("client_info") or {}).get("user_pool_id"):
        print(f"  Cognito user pool     {config['client_info']['user_pool_id']}")
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

    # The gateway execution role and the Cognito user pool are created by
    # deploy.py, so remove them here too.
    role_arn = config.get("role_arn", "")
    if role_arn:
        role_name = role_arn.split("/")[-1]
        iam = boto3.client("iam")
        try:
            iam.delete_role_policy(RoleName=role_name, PolicyName=IAM_POLICY_NAME)
            iam.delete_role(RoleName=role_name)
            print(f"Deleted IAM role {role_name}.")
        except Exception as exc:
            print(f"Could not delete IAM role {role_name}: {exc}")
            failures.append("IAM role")

    client_info = config.get("client_info") or {}
    pool_id = client_info.get("user_pool_id", "")
    if pool_id:
        cognito = boto3.client("cognito-idp", region_name=config["region"])
        # The hosted-UI domain must go before the pool, otherwise DeleteUserPool
        # fails with "It has a domain configured that should be deleted first".
        domain = client_info.get("domain", "")
        if domain:
            try:
                cognito.delete_user_pool_domain(Domain=domain, UserPoolId=pool_id)
                print(f"Deleted Cognito domain {domain}.")
                time.sleep(10)
            except Exception as exc:
                print(f"Could not delete Cognito domain {domain}: {exc}")
        try:
            cognito.delete_user_pool(UserPoolId=pool_id)
            print(f"Deleted Cognito user pool {pool_id}.")
        except Exception as exc:
            print(f"Could not delete Cognito user pool {pool_id}: {exc}")
            failures.append("Cognito user pool")

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
