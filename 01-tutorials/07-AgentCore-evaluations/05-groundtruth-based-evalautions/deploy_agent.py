"""Deploy the HR Assistant agent to AgentCore Runtime using boto3 directly.

Run from the notebook via: %run deploy_agent.py

Expects REGION to be set in the caller's namespace (Step 2 config cell).
Sets in the caller's namespace: AGENT_ID, AGENT_ARN, CW_LOG_GROUP, agentcore_client
"""

import base64
import json
import subprocess
import time
from pathlib import Path

import boto3

# REGION must already be set in the notebook before %run
# (it's set in the Step 2 config cell)

# ---- Clients ----
cp = boto3.client("bedrock-agentcore-control", region_name=REGION)  # noqa: F821
ecr = boto3.client("ecr", region_name=REGION)  # noqa: F821
sts = boto3.client("sts", region_name=REGION)  # noqa: F821
iam = boto3.client("iam")

ACCOUNT_ID = sts.get_caller_identity()["Account"]

# ---- Config ----
AGENT_NAME = "hr_assistant_eval_tutorial"
ECR_REPOSITORY_NAME = "hr-assistant-eval-tutorial"
IMAGE_TAG = "latest"
ECR_URI = f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/{ECR_REPOSITORY_NAME}"  # noqa: F821
IMAGE_URI = f"{ECR_URI}:{IMAGE_TAG}"

print(f"ACCOUNT_ID : {ACCOUNT_ID}")
print(f"IMAGE_URI  : {IMAGE_URI}")

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

# ---- 1. Ensure ECR repo ----
try:
    ecr.describe_repositories(repositoryNames=[ECR_REPOSITORY_NAME])
    print(f"ECR repo '{ECR_REPOSITORY_NAME}' exists.")
except ecr.exceptions.RepositoryNotFoundException:
    ecr.create_repository(repositoryName=ECR_REPOSITORY_NAME)
    print(f"Created ECR repo '{ECR_REPOSITORY_NAME}'.")

# ---- 2. ECR login ----
token = ecr.get_authorization_token()["authorizationData"][0]["authorizationToken"]
endpoint = f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com"  # noqa: F821
user, passwd = base64.b64decode(token).decode().split(":")
subprocess.run(
    ["docker", "login", "--username", user, "--password-stdin", endpoint],
    input=passwd.encode(),
    check=True,
)
print("ECR login successful.")

# ---- 3. Docker build ----
# Generate a Dockerfile if one doesn't exist (the repo .gitignore excludes Dockerfile)
if not Path("Dockerfile").exists():
    Path("Dockerfile").write_text(
        "FROM public.ecr.aws/docker/library/python:3.11-slim\n"
        "WORKDIR /app\n"
        "COPY requirements.txt ./\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n"
        "COPY hr_assistant_agent.py ./main.py\n"
        'CMD ["python", "main.py"]\n'
    )
    print("Generated Dockerfile.")

subprocess.run(["docker", "build", "-t", IMAGE_URI, "."], check=True)
print("Docker build complete.")

# ---- 4. Docker push ----
subprocess.run(["docker", "push", IMAGE_URI], check=True)
print("Docker push complete.")

# ---- 5. Create/Update runtime ----
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

args = {
    "agentRuntimeName": AGENT_NAME,
    "agentRuntimeArtifact": {"containerConfiguration": {"containerUri": IMAGE_URI}},
    "roleArn": AGENT_EXECUTION_ROLE_ARN,
    "networkConfiguration": {"networkMode": "PUBLIC"},
}

if existing_id:
    print(f"Updating runtime {existing_id} ...")
    cp.update_agent_runtime(agentRuntimeId=existing_id, **args)
    AGENT_ID = existing_id
    AGENT_ARN = existing_arn
else:
    print(f"Creating runtime '{AGENT_NAME}' ...")
    resp = cp.create_agent_runtime(**args)
    AGENT_ID = resp["agentRuntimeId"]
    AGENT_ARN = resp["agentRuntimeArn"]

# ---- 6. Wait for READY ----
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

CW_LOG_GROUP = f"/aws/bedrock-agentcore/runtimes/{AGENT_ID}-DEFAULT"
agentcore_client = boto3.client("bedrock-agentcore", region_name=REGION)  # noqa: F821

print(f"\nAGENT_ID     : {AGENT_ID}")
print(f"AGENT_ARN    : {AGENT_ARN}")
print(f"CW_LOG_GROUP : {CW_LOG_GROUP}")
print("Deploy complete.")
