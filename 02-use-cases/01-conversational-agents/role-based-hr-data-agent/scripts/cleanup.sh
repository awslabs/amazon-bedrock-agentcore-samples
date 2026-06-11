#!/bin/bash
# =============================================================================
# role-based-hr-data-agent — Cleanup Script
#
# Removes all deployed AWS resources in reverse deployment order:
#   1. AgentCore Runtime
#   2. AgentCore Gateway (+ Cedar Policy Engine)
#   3. CloudFormation stacks (Lambda, IAM, Cognito)
#   4. S3 deployment bucket
#   5. SSM parameters
#
# Usage:
#   bash scripts/cleanup.sh [--region us-east-1] [--env dev]
# =============================================================================

set -euo pipefail

REGION="us-east-1"
ENV="dev"

while [[ $# -gt 0 ]]; do
  case $1 in
    --region) REGION="$2"; shift 2 ;;
    --env) ENV="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="hr-dlp-deploy-${ACCOUNT_ID}-${REGION}"
STACK_INFRA="hr-dlp-infrastructure-${ENV}"
STACK_COGNITO="hr-dlp-cognito-${ENV}"

echo "============================================================"
echo "  Role-Based HR Data Agent — Cleanup"
echo "  Region: ${REGION}  |  Environment: ${ENV}"
echo "  Account: ${ACCOUNT_ID}"
echo "============================================================"

# ---------------------------------------------------------------------------
# Step 1: Delete AgentCore Runtimes (hr_data_agent_runtime* or hr_dlp*)
#         Waits for DELETING status before proceeding.
# ---------------------------------------------------------------------------
echo ""
echo "Step 1: Deleting AgentCore Runtime(s)"
python3 - <<PYEOF
import boto3, time, os

region = os.environ.get("AWS_REGION", "${REGION}")
client = boto3.client("bedrock-agentcore-control", region_name=region)
runtimes = client.list_agent_runtimes().get("agentRuntimes", [])
hr_runtimes = [r for r in runtimes if
               r["agentRuntimeName"].startswith("hr_data_agent_runtime") or
               r["agentRuntimeName"].startswith("hr_dlp")]

if not hr_runtimes:
    print("  No HR runtimes found — skipping")
else:
    for r in hr_runtimes:
        rid = r["agentRuntimeId"]
        print(f"  Deleting runtime: {r['agentRuntimeName']} ({rid})")
        try:
            client.delete_agent_runtime(agentRuntimeId=rid)
        except Exception as e:
            print(f"  WARNING: {e}")
    # Wait for all to leave READY state
    print("  Waiting for runtimes to finish deleting...")
    for _ in range(30):
        time.sleep(5)
        remaining = client.list_agent_runtimes().get("agentRuntimes", [])
        still_active = [r for r in remaining if
                        (r["agentRuntimeName"].startswith("hr_data_agent_runtime") or
                         r["agentRuntimeName"].startswith("hr_dlp")) and
                        r.get("status") != "DELETING"]
        if not still_active:
            print("  Runtimes deleted.")
            break
PYEOF

# ---------------------------------------------------------------------------
# Step 2: Delete AgentCore Gateway (hr-data-agent-gateway*)
#         Lists by name prefix — does not rely on SSM.
#         Deletes all targets first, then the gateway.
# ---------------------------------------------------------------------------
echo ""
echo "Step 2: Deleting AgentCore Gateway(s)"
python3 - <<PYEOF
import boto3, time, os

region = os.environ.get("AWS_REGION", "${REGION}")
client = boto3.client("bedrock-agentcore-control", region_name=region)
gateways = client.list_gateways().get("items", [])
hr_gateways = [g for g in gateways if g["name"].startswith("hr-data-agent-gateway")]

if not hr_gateways:
    print("  No hr-data-agent-gateway* gateways found — skipping")
else:
    for gw in hr_gateways:
        gid = gw["gatewayId"]
        print(f"  Gateway: {gw['name']} ({gid})")
        # Delete all targets first
        targets = client.list_gateway_targets(gatewayIdentifier=gid).get("items", [])
        for t in targets:
            tid = t["targetId"]
            print(f"    Deleting target: {tid}")
            try:
                client.delete_gateway_target(gatewayIdentifier=gid, targetId=tid)
            except Exception as e:
                print(f"    WARNING: {e}")
        # Poll until all targets are fully removed before deleting the gateway
        if targets:
            for _ in range(12):
                time.sleep(10)
                remaining = client.list_gateway_targets(gatewayIdentifier=gid).get("items", [])
                if not remaining:
                    break
        # Delete the gateway
        print(f"    Deleting gateway: {gid}")
        try:
            client.delete_gateway(gatewayIdentifier=gid)
            print(f"    Status: DELETING")
        except Exception as e:
            print(f"    WARNING: {e}")
PYEOF

# ---------------------------------------------------------------------------
# Step 3: Delete Cedar Policy Engines matching hr_dlp_policies_*
# Must delete all policies inside each engine before deleting the engine.
# ---------------------------------------------------------------------------
echo ""
echo "Step 3: Deleting Cedar Policy Engines (hr_dlp_policies_*)"
python3 - <<'PYEOF'
import boto3, time, sys

client = boto3.client("bedrock-agentcore-control")
engines = client.list_policy_engines().get("policyEngines", [])
hr_engines = [e for e in engines if e["name"].startswith("hr_dlp_policies_")]

if not hr_engines:
    print("  No hr_dlp_policies_* engines found — skipping")
    sys.exit(0)

for engine in hr_engines:
    engine_id = engine["policyEngineId"]
    print(f"  Engine: {engine['name']} ({engine_id})")
    policies = client.list_policies(policyEngineId=engine_id).get("policies", [])
    for p in policies:
        print(f"    Deleting policy: {p['policyId']}")
        client.delete_policy(policyEngineId=engine_id, policyId=p["policyId"])
    # Wait for all policies to finish deleting
    for _ in range(20):
        time.sleep(3)
        if not client.list_policies(policyEngineId=engine_id).get("policies", []):
            break
    resp = client.delete_policy_engine(policyEngineId=engine_id)
    print(f"    Engine status: {resp.get('status')}")
PYEOF

# ---------------------------------------------------------------------------
# Step 4: Delete CloudFormation stacks
# ---------------------------------------------------------------------------
echo ""
echo "Step 4: Deleting CloudFormation stack: ${STACK_INFRA}"
aws cloudformation delete-stack --stack-name "${STACK_INFRA}" --region "${REGION}" 2>/dev/null || true
aws cloudformation wait stack-delete-complete --stack-name "${STACK_INFRA}" --region "${REGION}" 2>/dev/null || true
echo "  Done: ${STACK_INFRA}"

echo "Deleting CloudFormation stack: ${STACK_COGNITO}"
aws cloudformation delete-stack --stack-name "${STACK_COGNITO}" --region "${REGION}" 2>/dev/null || true
aws cloudformation wait stack-delete-complete --stack-name "${STACK_COGNITO}" --region "${REGION}" 2>/dev/null || true
echo "  Done: ${STACK_COGNITO}"

# ---------------------------------------------------------------------------
# Step 5: Empty and delete S3 bucket
# ---------------------------------------------------------------------------
echo ""
echo "Step 5: Cleaning up S3 bucket: ${BUCKET}"
if aws s3api head-bucket --bucket "${BUCKET}" --region "${REGION}" 2>/dev/null; then
  aws s3 rm "s3://${BUCKET}" --recursive
  aws s3api delete-bucket --bucket "${BUCKET}" --region "${REGION}"
  echo "  Bucket deleted: ${BUCKET}"
else
  echo "  Bucket not found — skipping"
fi

# ---------------------------------------------------------------------------
# Step 6: Delete all SSM parameters under /app/hrdlp/
# ---------------------------------------------------------------------------
echo ""
echo "Step 6: Deleting SSM parameters under /app/hrdlp/"

# Collect all parameter names (paginated)
ALL_PARAMS=$(aws ssm get-parameters-by-path \
  --path /app/hrdlp \
  --recursive \
  --query "Parameters[].Name" \
  --output text \
  --region "${REGION}" 2>/dev/null || true)

if [[ -n "${ALL_PARAMS}" ]]; then
  # delete-parameters accepts up to 10 names at a time
  echo "${ALL_PARAMS}" | tr '\t' '\n' | xargs -n 10 \
    aws ssm delete-parameters --region "${REGION}" --names 2>/dev/null || true
  echo "  SSM parameters deleted"
else
  echo "  No SSM parameters found — skipping"
fi

echo ""
echo "============================================================"
echo "  Cleanup complete."
echo "  You can now re-deploy with:"
echo "    bash scripts/prereq.sh --region ${REGION} --env ${ENV}"
echo "============================================================"
