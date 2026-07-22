#!/usr/bin/env python3
"""
Add OBO permissions to the Lakehouse_Agent runtime role.

Per R2.7: the agent's IAM role needs
`bedrock-agentcore:GetWorkloadAccessTokenForJWT` so it can invoke the
OBO_Gateway path. (The interceptor path does not need this permission;
it's owned solely by the OBO substrate.)

Designed to be invoked from notebook 05b AFTER notebook 06 has created
the agent runtime role. The agent role is created by
deployment/6-lakehouse-agent/deploy_lakehouse_agent.py with name
`AgentCoreRuntimeRole-lakehouse-agent` and inline policy
`AgentCoreRuntimePermissions`.

Invocation order (per design §10 reconciliation):
  notebook 05b cells run 5b/01 -> 4b/deploy_runtime -> 5b/02..04 -> 5b/05
  but 5b/05's preconditions (the agent role) are produced by notebook 06.
  This script is idempotent — if the
  agent role doesn't exist yet, log and skip; notebook 06's cell sequence
  re-runs this script after `deploy_lakehouse_agent.py`.

Idempotency:
  - Agent role absent: log informational + skip cleanly (exit 0).
  - Agent role present, permission already attached to the inline policy:
    no-op, log "already present".
  - Agent role present, permission absent: amend the inline policy in place
    (read existing JSON, append the OBO statement, put_role_policy).

This script does NOT replace the entire policy — `deploy_lakehouse_agent.py`
re-runs put_role_policy with its full permission set on every redeploy, so
this script's amendment will be wiped on the next agent redeploy. The agent
runtime re-deploy is the moment the agent's "full"
permissions get rewritten — at that point, this script must run again.
That's intentional and matches design §12 #5 (writer-consumer atomicity:
the agent-IAM writer is `deploy_lakehouse_agent.py`; this OBO patch is a
consumer-side amend that re-runs after every writer-side run).

Usage:
    python 05_update_agent_iam.py
"""

import boto3
import json
import sys


AGENT_ROLE_NAME = "AgentCoreRuntimeRole-lakehouse-agent"
INLINE_POLICY_NAME = "AgentCoreRuntimePermissions"
OBO_ACTION = "bedrock-agentcore:GetWorkloadAccessTokenForJWT"
OBO_SID = "OBOWorkloadAccessTokenForJWT"


def main():
    print("=" * 70)
    print("Agent IAM Patch: Grant OBO permissions (OPTIONAL)")
    print("=" * 70)

    session = boto3.Session()
    region = session.region_name
    sts = boto3.client("sts", region_name=region)
    account_id = sts.get_caller_identity()["Account"]
    iam = boto3.client("iam")

    print(f"\n📋 Region: {region}")
    print(f"   Account: {account_id}")
    print(f"   Agent role: {AGENT_ROLE_NAME}")
    print(f"   Inline policy: {INLINE_POLICY_NAME}")
    print(f"   Action to grant: {OBO_ACTION}")

    # 1) Check whether the agent role exists.
    try:
        iam.get_role(RoleName=AGENT_ROLE_NAME)
    except iam.exceptions.NoSuchEntityException:
        print(f"\nℹ️  Agent role '{AGENT_ROLE_NAME}' not found.")
        print("   This is expected if notebook 06 hasn't run yet (the agent")
        print("   role is created by deploy_lakehouse_agent.py).")
        print("   Skipping OBO IAM patch; re-run this script after notebook 06.")
        sys.exit(0)

    print("\n✅ Agent role exists")

    # 2) Read the inline policy.
    try:
        resp = iam.get_role_policy(
            RoleName=AGENT_ROLE_NAME,
            PolicyName=INLINE_POLICY_NAME,
        )
        policy_doc = resp["PolicyDocument"]
    except iam.exceptions.NoSuchEntityException:
        print(f"\nℹ️  Agent role exists but inline policy '{INLINE_POLICY_NAME}' not found.")
        print("   This is unexpected — deploy_lakehouse_agent.py should attach it.")
        print("   Re-run notebook 06 to restore the agent's base permissions, then re-run this script.")
        sys.exit(0)

    # IAM returns the policy document as a Python dict (decoded from URL-encoded JSON).
    print(f"\n📋 Current inline policy has {len(policy_doc.get('Statement', []))} statement(s)")

    # 3) Check whether the OBO action is already present.
    statements = policy_doc.setdefault("Statement", [])
    for s in statements:
        actions = s.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        if OBO_ACTION in actions:
            print(f"\n✅ Action '{OBO_ACTION}' is already present in the inline policy.")
            print("   No-op; agent already has OBO permissions.")
            print("=" * 70)
            return

    # 4) Append the OBO statement and put_role_policy.
    obo_statement = {
        "Sid": OBO_SID,
        "Effect": "Allow",
        "Action": [OBO_ACTION],
        # AgentCore Identity workload-identity-directory + OAuth2 token vault
        # ARNs. Matches the gateway-side permissions shape from
        # 5a-gateway-setup/create_gateway.py (the OBO target's data-plane
        # access exercises this same workload-identity surface).
        "Resource": [
            f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default",
            f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/*",
        ],
    }
    statements.append(obo_statement)
    print("\n🔧 Appending OBO statement to inline policy...")
    print(f"   Sid: {OBO_SID}")
    print(f"   Action: {OBO_ACTION}")
    print("   Resource: workload-identity-directory/default[/workload-identity/*]")

    try:
        iam.put_role_policy(
            RoleName=AGENT_ROLE_NAME,
            PolicyName=INLINE_POLICY_NAME,
            PolicyDocument=json.dumps(policy_doc),
        )
        print(f"\n✅ Updated inline policy on {AGENT_ROLE_NAME}")
        print(f"   Statement count: {len(statements)}")
        print("\n📋 Note:")
        print("   This step is OPTIONAL — only for the direct (non-gateway)")
        print("   self-mint path. The gateway-mediated OBO path does NOT need it:")
        print("   the OBO_Gateway's own role performs the RFC 8693 exchange, so the")
        print("   agent role carries no OBO grant by design and nothing needs re-running.")
        print("=" * 70)
    except Exception as e:
        print(f"\n❌ Error updating inline policy: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
