"""
Zero to Registry in 10 Minutes — Admin Setup & IAM Governance Guide

Walks an IT/DevOps Admin through standing up an AWS Agent Registry from scratch:
  - Configure IAM policies for Admin, Publisher, and Consumer personas
  - Create a registry with governance-first manual approval (autoApproval: false)
  - Register all three record types: MCP server, A2A agent, CUSTOM skill
  - Prove governance guardrails (Publisher cannot self-approve, Consumer is read-only)
  - Approve records and verify semantic search

Usage:
    python getting_started_registry_end_to_end.py

Prerequisites:
    - boto3 >= 1.42.87  (pip install boto3)
    - AWS credentials with IAM management + STS + bedrock-agentcore permissions
    - AWS_DEFAULT_REGION set (default: us-west-2)

Resources created:
    - 1 Agent Registry (enterprise_agent_registry)
    - 3 Records: MCP server, A2A agent, CUSTOM skill
    - 3 IAM users: registry-admin-demo, registry-publisher-demo, registry-consumer-demo
"""

import os
import boto3
import json
import time
from botocore.exceptions import ClientError

AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")

# ── Setup clients ─────────────────────────────────────────────────────────────
session = boto3.Session(region_name=AWS_REGION)
ACCOUNT_ID = session.client("sts").get_caller_identity()["Account"]

cp_client = session.client("bedrock-agentcore-control")
dp_client = session.client("bedrock-agentcore")
iam_client = session.client("iam")


def pp(response):
    data = {k: v for k, v in response.items() if k != "ResponseMetadata"}
    print(json.dumps(data, indent=2, default=str))


def wait_for_registry_ready(client, registry_id, timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        r = client.get_registry(registryId=registry_id)
        if r["status"] == "READY":
            print(f"  ✅ Registry READY ({int(time.time() - start)}s)")
            return r
        print(f"  ⏳ Status: {r['status']}...")
        time.sleep(3)
    raise TimeoutError(f"Registry not READY after {timeout}s")


def test_action(desc, fn):
    try:
        result = fn()
        print(f"  ✅ ALLOWED: {desc}")
        return result
    except ClientError as e:
        code = e.response["Error"]["Code"]
        print(f"  🚫 DENIED:  {desc} ({code})")
        return None


RECORD_IDS = {}
RECORD_NAMES = {}

print(
    f"Session ready | Region: {AWS_REGION} | Account: {ACCOUNT_ID[:4]}****{ACCOUNT_ID[-4:]}"
)

# ── Step 1: Create registry ───────────────────────────────────────────────────
print("\n── Step 1: Create Registry (autoApproval: false) ──")
create_resp = cp_client.create_registry(
    name="enterprise_agent_registry",
    description="Enterprise registry for MCP servers, A2A agents, and custom resources. Manual approval required.",
    approvalConfiguration={"autoApproval": False},
)
REGISTRY_ARN = create_resp["registryArn"]
REGISTRY_ID = REGISTRY_ARN.split("/")[-1]
print(f"  Registry: {REGISTRY_ID}")
print("  Waiting for READY...")
wait_for_registry_ready(cp_client, REGISTRY_ID)

# ── Step 2: Define IAM policies ───────────────────────────────────────────────
print("\n── Step 2: Define IAM Policies ──")

ADMIN_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowCreatingAndListingRegistries",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:CreateRegistry",
                "bedrock-agentcore:ListRegistries",
            ],
            "Resource": [f"arn:aws:bedrock-agentcore:{AWS_REGION}:{ACCOUNT_ID}:*"],
        },
        {
            "Sid": "AllowGetUpdateDeleteRegistry",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:GetRegistry",
                "bedrock-agentcore:UpdateRegistry",
                "bedrock-agentcore:DeleteRegistry",
            ],
            "Resource": [
                f"arn:aws:bedrock-agentcore:{AWS_REGION}:{ACCOUNT_ID}:registry/*"
            ],
        },
        {
            "Sid": "AllowCreatingAndListingRegistryRecords",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:CreateRegistryRecord",
                "bedrock-agentcore:ListRegistryRecords",
            ],
            "Resource": [
                f"arn:aws:bedrock-agentcore:{AWS_REGION}:{ACCOUNT_ID}:registry/*"
            ],
        },
        {
            "Sid": "AllowRecordLevelOperations",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:GetRegistryRecord",
                "bedrock-agentcore:UpdateRegistryRecord",
                "bedrock-agentcore:DeleteRegistryRecord",
                "bedrock-agentcore:SubmitRegistryRecordForApproval",
            ],
            "Resource": [
                f"arn:aws:bedrock-agentcore:{AWS_REGION}:{ACCOUNT_ID}:registry/*/record/*"
            ],
        },
        {
            "Sid": "AllowApproveRejectDeprecateRecords",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:UpdateRegistryRecordStatus"],
            "Resource": [
                f"arn:aws:bedrock-agentcore:{AWS_REGION}:{ACCOUNT_ID}:registry/*/record/*"
            ],
        },
    ],
}

PUBLISHER_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowListingAllRegistries",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:ListRegistries"],
            "Resource": [f"arn:aws:bedrock-agentcore:{AWS_REGION}:{ACCOUNT_ID}:*"],
        },
        {
            "Sid": "AllowGetRegistry",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:GetRegistry"],
            "Resource": [
                f"arn:aws:bedrock-agentcore:{AWS_REGION}:{ACCOUNT_ID}:registry/*"
            ],
        },
        {
            "Sid": "AllowCreatingAndListingRegistryRecords",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:CreateRegistryRecord",
                "bedrock-agentcore:ListRegistryRecords",
            ],
            "Resource": [
                f"arn:aws:bedrock-agentcore:{AWS_REGION}:{ACCOUNT_ID}:registry/*"
            ],
        },
        {
            "Sid": "AllowRecordLevelOperations",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:GetRegistryRecord",
                "bedrock-agentcore:UpdateRegistryRecord",
                "bedrock-agentcore:DeleteRegistryRecord",
                "bedrock-agentcore:SubmitRegistryRecordForApproval",
            ],
            "Resource": [
                f"arn:aws:bedrock-agentcore:{AWS_REGION}:{ACCOUNT_ID}:registry/*/record/*"
            ],
        },
    ],
}

CONSUMER_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowListingAllRegistries",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:ListRegistries"],
            "Resource": [f"arn:aws:bedrock-agentcore:{AWS_REGION}:{ACCOUNT_ID}:*"],
        },
        {
            "Sid": "AllowGetRegistry",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:GetRegistry"],
            "Resource": [
                f"arn:aws:bedrock-agentcore:{AWS_REGION}:{ACCOUNT_ID}:registry/*"
            ],
        },
        {
            "Sid": "AllowSearchingForApprovedRecords",
            "Effect": "Allow",
            "Action": ["bedrock-agentcore:SearchRegistryRecords"],
            "Resource": [
                f"arn:aws:bedrock-agentcore:{AWS_REGION}:{ACCOUNT_ID}:registry/*"
            ],
        },
        {
            "Sid": "AllowListingAndGettingRecords",
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:ListRegistryRecords",
                "bedrock-agentcore:GetRegistryRecord",
            ],
            "Resource": [
                f"arn:aws:bedrock-agentcore:{AWS_REGION}:{ACCOUNT_ID}:registry/*"
            ],
        },
    ],
}
print("  ✅ Admin, Publisher, Consumer policies defined")

# ── Step 3: Create IAM users ──────────────────────────────────────────────────
print("\n── Step 3: Create IAM Users ──")
USERS = {
    "registry-admin-demo": ADMIN_POLICY,
    "registry-publisher-demo": PUBLISHER_POLICY,
    "registry-consumer-demo": CONSUMER_POLICY,
}
PERSONA_LABELS = {
    "registry-admin-demo": "Admin",
    "registry-publisher-demo": "Publisher",
    "registry-consumer-demo": "Consumer",
}

user_credentials = {}
for user_name, policy in USERS.items():
    try:
        iam_client.create_user(UserName=user_name)
    except iam_client.exceptions.EntityAlreadyExistsException:
        pass
    iam_client.put_user_policy(
        UserName=user_name,
        PolicyName=f"{user_name}-policy",
        PolicyDocument=json.dumps(policy),
    )
    try:
        keys = iam_client.create_access_key(UserName=user_name)
    except ClientError as e:
        if "LimitExceeded" in str(e):
            for k in iam_client.list_access_keys(UserName=user_name)[
                "AccessKeyMetadata"
            ]:
                iam_client.delete_access_key(
                    UserName=user_name, AccessKeyId=k["AccessKeyId"]
                )
            keys = iam_client.create_access_key(UserName=user_name)
        else:
            raise
    user_credentials[user_name] = {
        "access_key": keys["AccessKey"]["AccessKeyId"],
        "secret_key": keys["AccessKey"]["SecretAccessKey"],
    }
    print(f"  ✅ {PERSONA_LABELS[user_name]}: {user_name}")

print("\n  Waiting 10s for IAM policy propagation...")
time.sleep(10)


def get_client_for_user(user_name, service="bedrock-agentcore-control"):
    creds = user_credentials[user_name]
    s = boto3.Session(
        aws_access_key_id=creds["access_key"],
        aws_secret_access_key=creds["secret_key"],
        region_name=AWS_REGION,
    )
    return s.client(service)


publisher_cp = get_client_for_user("registry-publisher-demo")
admin_cp = get_client_for_user("registry-admin-demo")
consumer_cp = get_client_for_user("registry-consumer-demo")
consumer_dp = get_client_for_user("registry-consumer-demo", service="bedrock-agentcore")

# ── Step 4: Create records (MCP, A2A, CUSTOM) ─────────────────────────────────
print("\n── Step 4: Create Records ──")

mcp_rec = publisher_cp.create_registry_record(
    registryId=REGISTRY_ID,
    name="enterprise_code_review_mcp",
    descriptorType="MCP",
    descriptors={
        "mcp": {
            "server": {
                "inlineContent": json.dumps(
                    {
                        "name": "io.enterprise/code-review",
                        "description": "MCP server for automated code review with security scanning",
                        "version": "2.1.0",
                        "packages": [
                            {
                                "registryType": "npm",
                                "identifier": "@enterprise/code-review-mcp",
                                "version": "2.1.0",
                                "transport": {"type": "stdio"},
                            }
                        ],
                    }
                )
            },
            "tools": {
                "inlineContent": json.dumps(
                    {
                        "tools": [
                            {
                                "name": "review_code",
                                "description": "Analyze code for security issues",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"code": {"type": "string"}},
                                },
                            }
                        ]
                    }
                )
            },
        }
    },
    recordVersion="2.1",
)
RECORD_IDS["mcp"] = mcp_rec["recordArn"].split("/")[-1]
RECORD_NAMES["mcp"] = "enterprise_code_review_mcp"
print(f"  ✅ MCP: {RECORD_IDS['mcp']} — DRAFT")

a2a_rec = publisher_cp.create_registry_record(
    registryId=REGISTRY_ID,
    name="enterprise_compliance_agent",
    descriptorType="A2A",
    descriptors={
        "a2a": {
            "agentCard": {
                "schemaVersion": "0.3",
                "inlineContent": json.dumps(
                    {
                        "protocolVersion": "0.3",
                        "name": "enterprise-compliance-agent",
                        "description": "A2A agent for compliance policy validation and audit checks",
                        "version": "1.0.0",
                        "url": "https://compliance-agent.internal.example.com/a2a",
                        "capabilities": {"streaming": True},
                        "skills": [
                            {
                                "id": "validate_compliance",
                                "name": "Compliance Validation",
                                "description": "Validates resources against compliance policies.",
                                "tags": ["compliance"],
                            },
                            {
                                "id": "audit_check",
                                "name": "Audit Check",
                                "description": "Runs audit checks on infrastructure.",
                                "tags": ["audit"],
                            },
                        ],
                        "defaultInputModes": ["text/plain"],
                        "defaultOutputModes": ["text/plain"],
                    }
                ),
            }
        }
    },
    recordVersion="1.0",
)
RECORD_IDS["a2a"] = a2a_rec["recordArn"].split("/")[-1]
RECORD_NAMES["a2a"] = "enterprise_compliance_agent"
print(f"  ✅ A2A: {RECORD_IDS['a2a']} — DRAFT")

custom_rec = publisher_cp.create_registry_record(
    registryId=REGISTRY_ID,
    name="enterprise_data_pipeline_skill",
    descriptorType="CUSTOM",
    descriptors={
        "custom": {
            "inlineContent": json.dumps(
                {
                    "name": "data-pipeline-orchestrator",
                    "description": "Custom skill for orchestrating cross-account data pipelines",
                    "version": "3.0.0",
                    "endpoint": "https://pipelines.internal.example.com/api/v3",
                    "auth": {
                        "type": "IAM",
                        "roleArn": f"arn:aws:iam::{ACCOUNT_ID}:role/pipeline-invoker",
                    },
                }
            )
        }
    },
    recordVersion="3.0",
)
RECORD_IDS["custom"] = custom_rec["recordArn"].split("/")[-1]
RECORD_NAMES["custom"] = "enterprise_data_pipeline_skill"
print(f"  ✅ CUSTOM: {RECORD_IDS['custom']} — DRAFT")

time.sleep(5)

# ── Step 5: Governance tests ──────────────────────────────────────────────────
print("\n── Step 5: Governance Guardrail Tests ──")
mcp_record_id = RECORD_IDS["mcp"]

print("\n  5a. Publisher submits MCP record for approval (SHOULD SUCCEED)")
test_action(
    "SubmitRegistryRecordForApproval",
    lambda: publisher_cp.submit_registry_record_for_approval(
        registryId=REGISTRY_ID, recordId=mcp_record_id
    ),
)

print("\n  5b. Publisher tries to self-approve (SHOULD FAIL)")
test_action(
    "UpdateRegistryRecordStatus → APPROVED (self-approval)",
    lambda: publisher_cp.update_registry_record_status(
        registryId=REGISTRY_ID,
        recordId=mcp_record_id,
        status="APPROVED",
        statusReason="Self-approval attempt",
    ),
)
rec = admin_cp.get_registry_record(registryId=REGISTRY_ID, recordId=mcp_record_id)
assert rec["status"] == "PENDING_APPROVAL", (
    "GOVERNANCE FAILURE: Publisher was able to self-approve!"
)
print("  ✅ Guardrail PASSED — Publisher cannot self-approve")

print("\n  5c. Consumer tries to create a record (SHOULD FAIL)")
test_action(
    "CreateRegistryRecord",
    lambda: consumer_cp.create_registry_record(
        registryId=REGISTRY_ID,
        name="shouldFail",
        descriptorType="MCP",
        descriptors={"mcp": {"server": {"inlineContent": "{}"}}},
        recordVersion="1.0",
    ),
)

print("\n  5d. Consumer tries to approve a record (SHOULD FAIL)")
test_action(
    "UpdateRegistryRecordStatus → APPROVED",
    lambda: consumer_cp.update_registry_record_status(
        registryId=REGISTRY_ID,
        recordId=mcp_record_id,
        status="APPROVED",
        statusReason="Consumer approval attempt",
    ),
)

print("\n  5e. Consumer read operations (SHOULD SUCCEED)")
test_action("ListRegistries", lambda: consumer_cp.list_registries())
test_action("GetRegistry", lambda: consumer_cp.get_registry(registryId=REGISTRY_ID))
test_action(
    "ListRegistryRecords",
    lambda: consumer_cp.list_registry_records(registryId=REGISTRY_ID),
)

print("\n  5f. Admin approves MCP record (SHOULD SUCCEED)")
test_action(
    "Admin: UpdateRegistryRecordStatus → APPROVED",
    lambda: admin_cp.update_registry_record_status(
        registryId=REGISTRY_ID,
        recordId=mcp_record_id,
        status="APPROVED",
        statusReason="Approved by admin after review",
    ),
)
rec = admin_cp.get_registry_record(registryId=REGISTRY_ID, recordId=mcp_record_id)
print(f"  MCP record status: {rec['status']}")

# ── Step 6: Approve remaining records + search ────────────────────────────────
print("\n── Step 6: Approve Remaining Records ──")
time.sleep(5)
for rtype in ["a2a", "custom"]:
    rid = RECORD_IDS[rtype]
    name = RECORD_NAMES[rtype]
    test_action(
        f"Submit {name}",
        lambda rid=rid: publisher_cp.submit_registry_record_for_approval(
            registryId=REGISTRY_ID, recordId=rid
        ),
    )
time.sleep(5)
for rtype in ["a2a", "custom"]:
    rid = RECORD_IDS[rtype]
    name = RECORD_NAMES[rtype]
    test_action(
        f"Approve {name}",
        lambda rid=rid: admin_cp.update_registry_record_status(
            registryId=REGISTRY_ID,
            recordId=rid,
            status="APPROVED",
            statusReason="Approved by admin",
        ),
    )

# Final status
print("\n=== Final Record Status ===")
for rtype, rid in RECORD_IDS.items():
    r = admin_cp.get_registry_record(registryId=REGISTRY_ID, recordId=rid)
    print(f"  {rtype.upper():<10} {RECORD_NAMES[rtype]:<40} {r['status']}")

# Semantic search
print("\n── Semantic Search Verification (wait 30s for indexing) ──")
time.sleep(30)
queries = [
    "code review security scanning",
    "compliance policy validation",
    "data pipeline orchestration",
]
for q in queries:
    try:
        results = consumer_dp.search_registry_records(
            registryIds=[REGISTRY_ARN], searchQuery=q, maxResults=5
        )
        for r in results.get("registryRecords", []):
            print(f"  🔍 '{q}' → [{r.get('descriptorType')}] {r['name']}")
        if not results.get("registryRecords"):
            print(f"  🔍 '{q}' → no results yet (index may still propagate)")
    except Exception as e:
        print(f"  Error: {e}")

print("\n✅ End-to-end registry demo complete.")

# ── Cleanup (commented out) ───────────────────────────────────────────────────
# print("\n── Cleanup ──")
# for rtype, rid in RECORD_IDS.items():
#     try:
#         cp_client.delete_registry_record(registryId=REGISTRY_ID, recordId=rid)
#         print(f"  Deleted record: {RECORD_NAMES[rtype]}")
#     except Exception as e:
#         print(f"  Record cleanup: {e}")
# try:
#     cp_client.delete_registry(registryId=REGISTRY_ID)
#     print(f"  Deleted registry: enterprise_agent_registry")
# except Exception as e:
#     print(f"  Registry cleanup: {e}")
# for user_name in USERS.keys():
#     try:
#         for k in iam_client.list_access_keys(UserName=user_name)["AccessKeyMetadata"]:
#             iam_client.delete_access_key(UserName=user_name, AccessKeyId=k["AccessKeyId"])
#         iam_client.delete_user_policy(UserName=user_name, PolicyName=f"{user_name}-policy")
#         iam_client.delete_user(UserName=user_name)
#         print(f"  Deleted user: {PERSONA_LABELS[user_name]}")
#     except Exception as e:
#         print(f"  User cleanup: {e}")
