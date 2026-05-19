"""Deploy the Shopping Concierge agent to AgentCore Runtime using the bedrock-agentcore SDK.

Run from the notebook via: %run -i deploy_shopping_concierge_agent.py

Expects REGION to be set in the caller's namespace (Step 2 config cell).
Sets in the caller's namespace: AGENT_ID, AGENT_ARN, RUNTIME_ARN,
    SERVICE_NAME, LOG_GROUP, SPANS_LOG_GROUP

Deployment steps:
  1. Create an IAM execution role for the runtime
  2. Package the agent source and its dependencies into a zip (ARM64)
  3. Upload the zip to S3
  4. Create an AgentCore Runtime via create_agent_runtime (codeConfiguration)
  5. Poll until READY

See https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/getting-started-custom.html
"""

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path

import boto3

_REGION = REGION  # noqa: F821
_AGENT_NAME = f"shopping_concierge_{uuid.uuid4().hex[:8]}"
_SCRIPT_DIR = Path(__file__).parent

_sts = boto3.client("sts", region_name=_REGION)
_ACCOUNT_ID = _sts.get_caller_identity()["Account"]
_iam = boto3.client("iam", region_name=_REGION)
_s3 = boto3.client("s3", region_name=_REGION)
_ctrl = boto3.client("bedrock-agentcore-control", region_name=_REGION)

_ROLE_NAME = f"{_AGENT_NAME}_role"
_S3_BUCKET = f"bedrock-agentcore-code-{_ACCOUNT_ID}-{_REGION}"
_S3_KEY = f"{_AGENT_NAME}/deployment_package.zip"
_BUILD_DIR = Path(f"/tmp/{_AGENT_NAME}_build")

# ---------------------------------------------------------------------------
# 1. IAM execution role
# ---------------------------------------------------------------------------

_TRUST = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": _ACCOUNT_ID},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:*:{_ACCOUNT_ID}:runtime/*"
                    },
                },
            }
        ],
    }
)

_POLICY = json.dumps(
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                    "cloudwatch:PutMetricData",
                ],
                "Resource": "*",
            }
        ],
    }
)

print(f"Creating IAM role '{_ROLE_NAME}' ...")
try:
    _ROLE_ARN = _iam.create_role(RoleName=_ROLE_NAME, AssumeRolePolicyDocument=_TRUST)[
        "Role"
    ]["Arn"]
    print(f"  Created: {_ROLE_ARN}")
except _iam.exceptions.EntityAlreadyExistsException:
    _ROLE_ARN = _iam.get_role(RoleName=_ROLE_NAME)["Role"]["Arn"]
    print(f"  Already exists: {_ROLE_ARN}")

_iam.put_role_policy(
    RoleName=_ROLE_NAME,
    PolicyName=f"{_AGENT_NAME}_policy",
    PolicyDocument=_POLICY,
)
print("  Policy attached. Waiting 10s for IAM propagation ...")
time.sleep(10)

# ---------------------------------------------------------------------------
# 2. Build deployment package (ARM64)
# ---------------------------------------------------------------------------

print("\nBuilding deployment package ...")
if _BUILD_DIR.exists():
    shutil.rmtree(_BUILD_DIR)
_PKG = _BUILD_DIR / "pkg"
_PKG.mkdir(parents=True)

subprocess.run(
    [
        sys.executable,
        "-m",
        "pip",
        "install",
        "strands-agents[otel]",
        "bedrock-agentcore",
        "aws-opentelemetry-distro",
        "-t",
        str(_PKG),
        "--platform",
        "manylinux2014_aarch64",
        "--only-binary=:all:",
        "--python-version",
        "3.13",
        "--quiet",
    ],
    check=True,
)
shutil.copy(
    _SCRIPT_DIR / "shopping_concierge_agent.py", _PKG / "shopping_concierge_agent.py"
)

_ZIP = _BUILD_DIR / "deployment_package.zip"
with zipfile.ZipFile(_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, _, files in os.walk(_PKG):
        for f in files:
            if f.endswith(".pyc") or "__pycache__" in root:
                continue
            full = Path(root) / f
            zf.write(full, full.relative_to(_PKG))
print(f"  Package: {_ZIP} ({_ZIP.stat().st_size / 1024 / 1024:.1f} MB)")

# ---------------------------------------------------------------------------
# 3. Upload to S3
# ---------------------------------------------------------------------------

print("\nUploading to S3 ...")
try:
    if _REGION == "us-east-1":
        _s3.create_bucket(Bucket=_S3_BUCKET)
    else:
        _s3.create_bucket(
            Bucket=_S3_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": _REGION},
        )
    print(f"  Created bucket: {_S3_BUCKET}")
except Exception:
    print(f"  Bucket exists: {_S3_BUCKET}")
_s3.upload_file(str(_ZIP), _S3_BUCKET, _S3_KEY)
print(f"  Uploaded: s3://{_S3_BUCKET}/{_S3_KEY}")

# ---------------------------------------------------------------------------
# 4. Create AgentCore Runtime
# ---------------------------------------------------------------------------

print(f"\nCreating AgentCore Runtime '{_AGENT_NAME}' ...")
_resp = _ctrl.create_agent_runtime(
    agentRuntimeName=_AGENT_NAME,
    agentRuntimeArtifact={
        "codeConfiguration": {
            "code": {"s3": {"bucket": _S3_BUCKET, "prefix": _S3_KEY}},
            "runtime": "PYTHON_3_13",
            "entryPoint": ["opentelemetry-instrument", "shopping_concierge_agent.py"],
        }
    },
    networkConfiguration={"networkMode": "PUBLIC"},
    roleArn=_ROLE_ARN,
)
AGENT_ID = _resp["agentRuntimeId"]
print(f"  Runtime created: {AGENT_ID}")

# ---------------------------------------------------------------------------
# 5. Poll until READY
# ---------------------------------------------------------------------------

print("Waiting for READY ...")
for _elapsed in range(0, 600, 15):
    _status = _ctrl.get_agent_runtime(agentRuntimeId=AGENT_ID).get("status", "UNKNOWN")
    print(f"  [{_elapsed:>3}s] {_status}")
    if _status in ("READY", "ACTIVE"):
        break
    if "FAILED" in _status:
        raise RuntimeError(f"Deploy failed: {_status}")
    time.sleep(15)
else:
    raise TimeoutError("Agent did not reach READY in 600s")

AGENT_ARN = _ctrl.get_agent_runtime(agentRuntimeId=AGENT_ID)["agentRuntimeArn"]
RUNTIME_ARN = AGENT_ARN
SERVICE_NAME = f"{_AGENT_NAME}.DEFAULT"
LOG_GROUP = f"/aws/bedrock-agentcore/runtimes/{AGENT_ID}-DEFAULT"
SPANS_LOG_GROUP = "aws/spans"

print(f"\nAGENT_ID     : {AGENT_ID}")
print(f"AGENT_ARN    : {AGENT_ARN}")
print(f"RUNTIME_ARN  : {RUNTIME_ARN}")
print(f"SERVICE_NAME : {SERVICE_NAME}")
print(f"LOG_GROUP    : {LOG_GROUP}")
print("Deploy complete.")
