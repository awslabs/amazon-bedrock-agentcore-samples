"""Deploy the Shopping Concierge agent to AgentCore Runtime using CodeZip (no Docker).

Run from the notebook via: %run -i deploy_shopping_concierge_agent.py

Expects REGION to be set in the caller's namespace (Step 2 config cell).
Sets in the caller's namespace: AGENT_ID, AGENT_ARN, RUNTIME_ARN,
    SERVICE_NAME, LOG_GROUP, SPANS_LOG_GROUP
"""

import io
import json
import time
import zipfile

import boto3

# REGION must already be set in the notebook before %run -i

cp = boto3.client("bedrock-agentcore-control", region_name=REGION)  # noqa: F821
s3 = boto3.client("s3", region_name=REGION)  # noqa: F821
sts = boto3.client("sts", region_name=REGION)  # noqa: F821
iam = boto3.client("iam")

ACCOUNT_ID = sts.get_caller_identity()["Account"]

# ---- Config ----
AGENT_NAME = "shopping_concierge_eval"
S3_BUCKET = f"agentcore-deploy-{ACCOUNT_ID}-{REGION}"  # noqa: F821
S3_KEY = f"{AGENT_NAME}/code.zip"
RUNTIME_VERSION = "PYTHON_3_12"

print(f"ACCOUNT_ID : {ACCOUNT_ID}")
print(f"S3_BUCKET  : {S3_BUCKET}")

# ---- 0. Ensure execution role ----
ROLE_NAME = "AgentCoreExecutionRole"
TRUST_POLICY = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
)
try:
    role_resp = iam.get_role(RoleName=ROLE_NAME)
    AGENT_EXECUTION_ROLE_ARN = role_resp["Role"]["Arn"]
    print(f"Execution role exists: {AGENT_EXECUTION_ROLE_ARN}")
except iam.exceptions.NoSuchEntityException:
    print(f"Creating execution role {ROLE_NAME} ...")
    role_resp = iam.create_role(
        RoleName=ROLE_NAME,
        AssumeRolePolicyDocument=TRUST_POLICY,
        Description="Execution role for AgentCore runtimes (auto-created)",
    )
    AGENT_EXECUTION_ROLE_ARN = role_resp["Role"]["Arn"]
    for p in [
        "arn:aws:iam::aws:policy/AmazonBedrockFullAccess",
        "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
    ]:
        iam.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=p)
    print(f"Created: {AGENT_EXECUTION_ROLE_ARN}")
    print("Waiting 10s for IAM propagation ...")
    time.sleep(10)

# ---- 1. Ensure S3 bucket ----
try:
    s3.head_bucket(Bucket=S3_BUCKET)
    print(f"S3 bucket '{S3_BUCKET}' exists.")
except s3.exceptions.ClientError:
    create_args = {"Bucket": S3_BUCKET}
    if REGION != "us-east-1":  # noqa: F821
        create_args["CreateBucketConfiguration"] = {"LocationConstraint": REGION}  # noqa: F821
    s3.create_bucket(**create_args)
    print(f"Created S3 bucket '{S3_BUCKET}'.")

# ---- 2. Zip and upload agent code ----
print("Zipping agent code ...")
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write("shopping_concierge_agent.py", "shopping_concierge_agent.py")
    zf.write("requirements.txt", "requirements.txt")
buf.seek(0)

s3.put_object(Bucket=S3_BUCKET, Key=S3_KEY, Body=buf.getvalue())
print(f"Uploaded s3://{S3_BUCKET}/{S3_KEY} ({len(buf.getvalue())} bytes)")

# ---- 3. Create/Update runtime ----
existing_id = None
existing_arn = None
paginator = cp.get_paginator("list_agent_runtimes")
for page in paginator.paginate():
    for rt in page.get("agentRuntimes", []):
        if rt.get("agentRuntimeName") == AGENT_NAME:
            existing_id = rt["agentRuntimeId"]
            existing_arn = rt["agentRuntimeArn"]
            break
    if existing_id:
        break

runtime_args = {
    "agentRuntimeName": AGENT_NAME,
    "agentRuntimeArtifact": {
        "codeConfiguration": {
            "code": {"s3": {"bucket": S3_BUCKET, "prefix": S3_KEY}},
            "runtime": RUNTIME_VERSION,
            "entryPoint": ["shopping_concierge_agent.py"],
        },
    },
    "roleArn": AGENT_EXECUTION_ROLE_ARN,
    "networkConfiguration": {"networkMode": "PUBLIC"},
}

if existing_id:
    print(f"Updating runtime {existing_id} ...")
    cp.update_agent_runtime(agentRuntimeId=existing_id, **runtime_args)
    AGENT_ID = existing_id
    AGENT_ARN = existing_arn
else:
    print(f"Creating runtime '{AGENT_NAME}' ...")
    resp = cp.create_agent_runtime(**runtime_args)
    AGENT_ID = resp["agentRuntimeId"]
    AGENT_ARN = resp["agentRuntimeArn"]

# ---- 4. Wait for READY ----
print("Waiting for READY ...")
for elapsed in range(0, 600, 15):
    status = cp.get_agent_runtime(agentRuntimeId=AGENT_ID).get("status", "UNKNOWN")
    print(f"  [{elapsed:>3}s] {status}")
    if status in ("READY", "ACTIVE"):
        break
    if status in ("FAILED", "CREATE_FAILED", "UPDATE_FAILED"):
        raise RuntimeError(f"Deploy failed: {status}")
    time.sleep(15)
else:
    raise TimeoutError("Agent did not reach READY in 600s")

# ---- Set variables for the notebook ----
RUNTIME_ARN = AGENT_ARN
SERVICE_NAME = AGENT_NAME
LOG_GROUP = f"/aws/bedrock-agentcore/runtimes/{AGENT_ID}-DEFAULT"
SPANS_LOG_GROUP = "aws/spans"

print(f"\nAGENT_ID     : {AGENT_ID}")
print(f"AGENT_ARN    : {AGENT_ARN}")
print(f"RUNTIME_ARN  : {RUNTIME_ARN}")
print(f"SERVICE_NAME : {SERVICE_NAME}")
print(f"LOG_GROUP    : {LOG_GROUP}")
print("Deploy complete.")
