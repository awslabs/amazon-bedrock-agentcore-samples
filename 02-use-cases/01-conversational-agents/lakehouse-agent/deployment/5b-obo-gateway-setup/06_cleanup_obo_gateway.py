#!/usr/bin/env python3
"""
Cleanup OBO_Gateway substrate.

Mirrors deployment/5a-gateway-setup/cleanup_gateway.py shape. Tears down what
9.1-9.4 created (and only that — by-name scoping prevents collateral damage
to the interceptor side or to other workloads in the account).

Cleanup coverage (per R10.4 + tasks.md 9.6):
  1. OBO_Gateway target (lakehouse-obo-target)
  2. OBO_Gateway (lakehouse-notes-gateway)
  3. OBO_Gateway IAM role (agentcore-lakehouse-notes-gateway-role)
  4. OAuth2 credential providers: Okta OBO (lakehouse-obo-okta-provider) +
     Cognito M2M (lakehouse-notes-cognito-oauth-provider) — each safe-if-absent
  5. AOSS data-access policy   (lakehouse-claim-notes-data)        [9.1 created]
  6. AOSS network policy       (lakehouse-claim-notes-network)     [9.1 created]
  7. AOSS encryption policy    (lakehouse-claim-notes-encryption)  [9.1 created]
  8. AOSS collection           (lakehouse-claim-notes)             [9.1 created]
  9. Net-new SSM keys: notes-gateway-* (4 keys), opensearch-collection-{arn,endpoint},
     obo-credential-provider-arn

Note: there is no agent-IAM revert step — the agent deliberately holds NO OBO
grant (the GW2 gateway role performs the RFC 8693 exchange, Finding 15), so
there is nothing to undo on the agent role.

Resources NOT cleaned here (owned by sibling cleanup scripts):
  - OpenSearch_MCP_Server runtime + its IAM/ECR/CodeBuild + opensearch-mcp-runtime-{arn,id}
    -> deployment/4b-mcp-opensearch-server/cleanup_runtime.py
  - Agent runtime + IAM/ECR/CodeBuild
    -> deployment/6-lakehouse-agent/cleanup_agent.py
  - Interceptor gateway and its substrate
    -> deployment/5a-gateway-setup/cleanup_gateway.py
  - Okta OBO exchange app (lakehouse-obo-exchange-client) + okta-obo-client-* SSM keys
    -> deployment/1-okta-setup/cleanup_okta.py  (Okta-side resource; owned there)

Cleanup ordering (load-bearing): targets BEFORE gateway, gateway BEFORE role,
data-access policy BEFORE collection (AOSS rejects collection delete while a
data-access policy references it). Encryption + network policies can be
removed anytime after the collection is gone.

Idempotent (per R10.1 + R10.2): re-running after a successful first run logs
all ⏭️ and exits 0.

Usage:
    python 06_cleanup_obo_gateway.py [--keep-ssm]
"""

import argparse
import os
import sys
import time

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from utils.aws_session_utils import get_aws_session

# Names match the create-side scripts (9.1, 9.3, 9.4, 9.5)
COLLECTION_NAME = "lakehouse-claim-notes"
GATEWAY_NAME = "lakehouse-notes-gateway"
GATEWAY_ROLE_NAME = f"agentcore-{GATEWAY_NAME}-role"
PROVIDER_NAME = "lakehouse-obo-okta-provider"
# Cognito M2M gateway->runtime credential provider created by 04's Cognito
# branch (COGNITO_M2M_PROVIDER_NAME). Deleted explicitly here (symmetric with
# the Okta OBO provider above) rather than relying on cleanup_gateway.py's
# incidental "lakehouse" substring match. Safe-if-absent -> no-op on Okta.
COGNITO_M2M_PROVIDER_NAME = "lakehouse-notes-cognito-oauth-provider"
ENCRYPTION_POLICY_NAME = f"{COLLECTION_NAME}-encryption"
NETWORK_POLICY_NAME = f"{COLLECTION_NAME}-network"
DATA_ACCESS_POLICY_NAME = f"{COLLECTION_NAME}-data"

SSM_PREFIX = "/app/lakehouse-agent/"


class OBOCleanup:
    def __init__(self, keep_ssm=False):
        _session, self.region, self.account_id = get_aws_session()
        self.bedrock = boto3.client("bedrock-agentcore-control", region_name=self.region)
        self.iam = boto3.client("iam")
        self.aoss = boto3.client("opensearchserverless", region_name=self.region)
        self.ssm = boto3.client("ssm", region_name=self.region)
        self.keep_ssm = keep_ssm

    def _get_ssm_param(self, name, default=None):
        try:
            return self.ssm.get_parameter(Name=f"{SSM_PREFIX}{name}")["Parameter"]["Value"]
        except Exception:
            return default

    # ─── 1+2: OBO gateway target + gateway ────────────────────────────
    def delete_gateway(self):
        print(f"\n🗑️  Deleting OBO_Gateway: {GATEWAY_NAME}")

        # Find by name (SSM key may be missing if 9.4 partially failed)
        gateway_id = self._get_ssm_param("notes-gateway-id")
        if not gateway_id:
            try:
                response = self.bedrock.list_gateways()
                for gw in response.get("items", []):
                    if gw.get("name") == GATEWAY_NAME:
                        gateway_id = gw["gatewayId"]
                        break
            except Exception as e:
                print(f"   ⚠️  list_gateways failed: {e}")

        if not gateway_id:
            print("   ⏭️  No OBO gateway found")
            return

        # Targets first
        try:
            targets = self.bedrock.list_gateway_targets(gatewayIdentifier=gateway_id).get("items", [])
            for target in targets:
                tid = target["targetId"]
                try:
                    self.bedrock.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=tid)
                    print(f"   ✅ Deleted target: {target.get('name', tid)}")
                except Exception as e:
                    print(f"   ⚠️  Error deleting target {tid}: {e}")

            if targets:
                print("   ⏳ Waiting for targets to delete...")
                for _ in range(12):
                    remaining = self.bedrock.list_gateway_targets(gatewayIdentifier=gateway_id).get("items", [])
                    if not remaining:
                        break
                    time.sleep(5)
        except Exception as e:
            print(f"   ⚠️  Error listing/deleting targets: {e}")

        # Gateway
        try:
            self.bedrock.delete_gateway(gatewayIdentifier=gateway_id)
            print(f"   ✅ Deleted gateway: {gateway_id}")
            time.sleep(5)
        except self.bedrock.exceptions.ResourceNotFoundException:
            print(f"   ⏭️  Gateway not found: {gateway_id}")
        except Exception as e:
            print(f"   ❌ Error deleting gateway: {e}")

    # ─── 3: OBO gateway IAM role ──────────────────────────────────────
    def delete_gateway_role(self):
        print(f"\n🗑️  Deleting OBO_Gateway IAM role: {GATEWAY_ROLE_NAME}")
        try:
            self.iam.get_role(RoleName=GATEWAY_ROLE_NAME)
        except self.iam.exceptions.NoSuchEntityException:
            print(f"   ⏭️  Role not found: {GATEWAY_ROLE_NAME}")
            return
        try:
            for p in self.iam.list_role_policies(RoleName=GATEWAY_ROLE_NAME)["PolicyNames"]:
                self.iam.delete_role_policy(RoleName=GATEWAY_ROLE_NAME, PolicyName=p)
            for p in self.iam.list_attached_role_policies(RoleName=GATEWAY_ROLE_NAME)["AttachedPolicies"]:
                self.iam.detach_role_policy(RoleName=GATEWAY_ROLE_NAME, PolicyArn=p["PolicyArn"])
            self.iam.delete_role(RoleName=GATEWAY_ROLE_NAME)
            print(f"   ✅ Deleted role: {GATEWAY_ROLE_NAME}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    # ─── 4: OAuth2 credential providers (Okta OBO + Cognito M2M) ───────
    def delete_oauth_provider(self, provider_name=PROVIDER_NAME):
        print(f"\n🗑️  Deleting OAuth2 credential provider: {provider_name}")
        try:
            self.bedrock.delete_oauth2_credential_provider(name=provider_name)
            print(f"   ✅ Deleted: {provider_name}")
        except self.bedrock.exceptions.ResourceNotFoundException:
            print(f"   ⏭️  Provider not found: {provider_name}")
        except Exception as e:
            msg = str(e).lower()
            if "not found" in msg or "resourcenotfound" in msg:
                print(f"   ⏭️  Provider not found: {provider_name}")
            else:
                print(f"   ❌ Error: {e}")

    # ─── 5+6+7+8: AOSS data-access policy / network / encryption / collection ─
    def delete_aoss_collection(self):
        print(f"\n🗑️  Deleting AOSS data-access policy: {DATA_ACCESS_POLICY_NAME}")
        # Data-access policy MUST go first — AOSS rejects collection delete
        # while a data-access policy still references the collection.
        try:
            self.aoss.delete_access_policy(name=DATA_ACCESS_POLICY_NAME, type="data")
            print(f"   ✅ Deleted: {DATA_ACCESS_POLICY_NAME}")
        except self.aoss.exceptions.ResourceNotFoundException:
            print(f"   ⏭️  Policy not found: {DATA_ACCESS_POLICY_NAME}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        print(f"\n🗑️  Deleting AOSS collection: {COLLECTION_NAME}")
        try:
            response = self.aoss.list_collections(collectionFilters={"name": COLLECTION_NAME})
            summaries = response.get("collectionSummaries", [])
            if not summaries:
                print(f"   ⏭️  Collection not found: {COLLECTION_NAME}")
            else:
                collection_id = summaries[0]["id"]
                try:
                    self.aoss.delete_collection(id=collection_id)
                    print(f"   ✅ Delete initiated: {COLLECTION_NAME} (id={collection_id})")
                    print("   ⏳ Waiting for collection to delete...")
                    for _ in range(40):  # up to ~10 min
                        details = self.aoss.batch_get_collection(ids=[collection_id])
                        items = details.get("collectionDetails", [])
                        if not items:
                            print("   ✅ Collection deleted")
                            break
                        status = items[0].get("status")
                        if status not in ("DELETING", "ACTIVE", "CREATING"):
                            print(f"   ⚠️  Unexpected status during delete: {status}")
                            break
                        time.sleep(15)
                except self.aoss.exceptions.ResourceNotFoundException:
                    print("   ⏭️  Collection already gone")
                except Exception as e:
                    print(f"   ❌ Error deleting collection: {e}")
        except Exception as e:
            print(f"   ❌ Error listing collections: {e}")

        print(f"\n🗑️  Deleting AOSS network policy: {NETWORK_POLICY_NAME}")
        try:
            self.aoss.delete_security_policy(name=NETWORK_POLICY_NAME, type="network")
            print(f"   ✅ Deleted: {NETWORK_POLICY_NAME}")
        except self.aoss.exceptions.ResourceNotFoundException:
            print(f"   ⏭️  Policy not found: {NETWORK_POLICY_NAME}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        print(f"\n🗑️  Deleting AOSS encryption policy: {ENCRYPTION_POLICY_NAME}")
        try:
            self.aoss.delete_security_policy(name=ENCRYPTION_POLICY_NAME, type="encryption")
            print(f"   ✅ Deleted: {ENCRYPTION_POLICY_NAME}")
        except self.aoss.exceptions.ResourceNotFoundException:
            print(f"   ⏭️  Policy not found: {ENCRYPTION_POLICY_NAME}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    # ─── 9: SSM keys ──────────────────────────────────────────────────
    def delete_ssm_parameters(self):
        if self.keep_ssm:
            print("\n⏭️  Keeping SSM parameters (--keep-ssm)")
            return
        print("\n🗑️  Deleting SSM parameters...")
        # All net-new keys this 5b/ directory owns
        params = [
            # GW2 notes gateway (9.4)
            "notes-gateway-id",
            "notes-gateway-arn",
            "notes-gateway-url",
            "notes-gateway-name",
            # OBO credential provider (9.3)
            "obo-credential-provider-arn",
            # AOSS collection (9.1)
            "opensearch-collection-arn",
            "opensearch-collection-endpoint",
        ]
        # opensearch-mcp-runtime-{arn,id} are intentionally NOT deleted here —
        # they're owned by deployment/4b-mcp-opensearch-server/cleanup_runtime.py
        # and removing them here would create a coverage overlap that would
        # produce ⚠️ on second-run cleanup (defeats R10.2 ⏭️-only second-run).
        for p in params:
            try:
                self.ssm.delete_parameter(Name=f"{SSM_PREFIX}{p}")
                print(f"   ✅ Deleted: {SSM_PREFIX}{p}")
            except self.ssm.exceptions.ParameterNotFound:
                pass
            except Exception as e:
                print(f"   ❌ Error: {e}")

    def run(self):
        print("\n🧹 OBO_Gateway Cleanup")
        print(f"   Region: {self.region}")
        print(f"   Account: {self.account_id}")
        # Order matters: gateway-side AWS resources first (target -> gateway ->
        # role -> provider), then AOSS, then SSM.
        self.delete_gateway()
        self.delete_gateway_role()
        self.delete_oauth_provider()  # Okta OBO provider (no-op on Cognito)
        self.delete_oauth_provider(COGNITO_M2M_PROVIDER_NAME)  # Cognito M2M provider (no-op on Okta)
        self.delete_aoss_collection()
        self.delete_ssm_parameters()
        print("\n✨ OBO_Gateway cleanup complete!")


def main():
    parser = argparse.ArgumentParser(description="Cleanup OBO_Gateway substrate")
    parser.add_argument("--keep-ssm", action="store_true", help="Keep SSM parameters")
    args = parser.parse_args()
    OBOCleanup(keep_ssm=args.keep_ssm).run()


if __name__ == "__main__":
    main()
