#!/usr/bin/env python3
"""
Deploy Strands and LangGraph agents to AgentCore Runtime using the bedrock-agentcore SDK.

Saves agent IDs and ARNs to agents_config.json for use in the tutorial notebook.
Run this script from the 00-prereqs directory:

    python deploy_agents.py

On subsequent runs, already-deployed agents are detected automatically and
the script simply waits for READY status before writing the config.

Deployment steps per agent:
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
import zipfile
from pathlib import Path

import boto3
from boto3.session import Session

CONFIG_FILE = "agents_config.json"
_SCRIPT_DIR = Path(__file__).parent

STRANDS_NAME = "acevalstrands2"
LANGGRAPH_NAME = "acevallanggraph2"

STRANDS_REQUIREMENTS = [
    "strands-agents[otel]",
    "strands-agents-tools",
    "bedrock-agentcore",
    "aws-opentelemetry-distro",
]

LANGGRAPH_REQUIREMENTS = [
    "langchain[aws]",
    "langgraph",
    "langsmith[otel]",
    "langchain-community",
    "opentelemetry-instrumentation-langchain",
    "bedrock-agentcore",
    "aws-opentelemetry-distro",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_region():
    return Session().region_name


def get_account_id(region):
    return boto3.client("sts", region_name=region).get_caller_identity()["Account"]


def find_runtime(cp, name):
    """Return the first runtime whose name matches exactly, or None."""
    paginator = cp.get_paginator("list_agent_runtimes")
    for page in paginator.paginate():
        for rt in page.get("agentRuntimeSummaries", page.get("agentRuntimes", [])):
            if rt.get("agentRuntimeName") == name:
                return rt
    return None


def wait_for_ready(region, agent_id, label, max_wait=600, poll_interval=15):
    """Poll until the agent reaches READY (or raises on failure/timeout)."""
    cp = boto3.client("bedrock-agentcore-control", region_name=region)
    terminal = {"READY", "FAILED", "CREATE_FAILED", "UPDATE_FAILED", "DELETE_FAILED"}
    elapsed = 0
    while elapsed < max_wait:
        resp = cp.get_agent_runtime(agentRuntimeId=agent_id)
        status = resp.get("agentRuntimeStatus") or resp.get("status", "UNKNOWN")
        print(f"  [{label}] status: {status}")
        if status in terminal:
            if status != "READY":
                raise RuntimeError(f"{label} deployment ended with status: {status}")
            return
        time.sleep(poll_interval)
        elapsed += poll_interval
    raise TimeoutError(f"{label} did not reach READY within {max_wait}s")


def _create_role(iam, name, account_id):
    """Create (or return existing) IAM execution role for an AgentCore Runtime."""
    trust = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {"aws:SourceAccount": account_id},
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:bedrock-agentcore:*:{account_id}:runtime/*"
                        },
                    },
                }
            ],
        }
    )
    policy = json.dumps(
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
    role_name = f"{name}_role"
    try:
        role_arn = iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=trust)[
            "Role"
        ]["Arn"]
        print(f"  Created IAM role: {role_arn}")
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
        print(f"  IAM role exists: {role_arn}")
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName=f"{name}_policy",
        PolicyDocument=policy,
    )
    print("  Policy attached. Waiting 10s for IAM propagation ...")
    time.sleep(10)
    return role_arn


def _build_and_upload(name, agent_file, requirements, region, account_id, s3):
    """Package dependencies + agent code, upload to S3, return (bucket, key)."""
    build_dir = Path(f"/tmp/{name}_build")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    pkg = build_dir / "pkg"
    pkg.mkdir(parents=True)

    print(f"  Installing dependencies for {name} (ARM64) ...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            *requirements,
            "-t",
            str(pkg),
            "--platform",
            "manylinux2014_aarch64",
            "--only-binary=:all:",
            "--python-version",
            "3.13",
            "--quiet",
        ],
        check=True,
    )
    shutil.copy(_SCRIPT_DIR / agent_file, pkg / agent_file)

    zip_path = build_dir / "deployment_package.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(pkg):
            for f in files:
                if f.endswith(".pyc") or "__pycache__" in root:
                    continue
                full = Path(root) / f
                zf.write(full, full.relative_to(pkg))
    print(f"  Package: {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")

    bucket = f"bedrock-agentcore-code-{account_id}-{region}"
    key = f"{name}/deployment_package.zip"
    try:
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket)
        else:
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        print(f"  Created S3 bucket: {bucket}")
    except Exception:
        print(f"  S3 bucket exists: {bucket}")
    s3.upload_file(str(zip_path), bucket, key)
    print(f"  Uploaded: s3://{bucket}/{key}")
    return bucket, key


def _deploy_agent(name, agent_file, entrypoint, requirements, region, account_id, cp):
    """Deploy one agent: IAM role → package → S3 → create_agent_runtime → wait."""
    iam = boto3.client("iam", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    ctrl = boto3.client("bedrock-agentcore-control", region_name=region)

    existing = find_runtime(cp, name)
    if existing:
        agent_id = existing["agentRuntimeId"]
        agent_arn = existing["agentRuntimeArn"]
        print(f"  Already deployed: {agent_id}")
        wait_for_ready(region, agent_id, name)
        return agent_id, agent_arn

    role_arn = _create_role(iam, name, account_id)
    bucket, key = _build_and_upload(
        name, agent_file, requirements, region, account_id, s3
    )

    print(f"  Creating AgentCore Runtime '{name}' ...")
    resp = ctrl.create_agent_runtime(
        agentRuntimeName=name,
        agentRuntimeArtifact={
            "codeConfiguration": {
                "code": {"s3": {"bucket": bucket, "prefix": key}},
                "runtime": "PYTHON_3_13",
                "entryPoint": ["opentelemetry-instrument", entrypoint],
            }
        },
        networkConfiguration={"networkMode": "PUBLIC"},
        roleArn=role_arn,
    )
    agent_id = resp["agentRuntimeId"]
    print(f"  Runtime created: {agent_id}")

    wait_for_ready(region, agent_id, name)
    agent_arn = ctrl.get_agent_runtime(agentRuntimeId=agent_id)["agentRuntimeArn"]
    print(f"  Ready: {agent_id}")
    return agent_id, agent_arn


# ---------------------------------------------------------------------------
# Agent deployment
# ---------------------------------------------------------------------------


def deploy_strands(region, account_id, cp):
    print(f"\n=== Strands Agent ({STRANDS_NAME}) ===")
    return _deploy_agent(
        name=STRANDS_NAME,
        agent_file="eval_agent_strands.py",
        entrypoint="eval_agent_strands.py",
        requirements=STRANDS_REQUIREMENTS,
        region=region,
        account_id=account_id,
        cp=cp,
    )


def deploy_langgraph(region, account_id, cp):
    print(f"\n=== LangGraph Agent ({LANGGRAPH_NAME}) ===")
    return _deploy_agent(
        name=LANGGRAPH_NAME,
        agent_file="eval_agent_langgraph.py",
        entrypoint="eval_agent_langgraph.py",
        requirements=LANGGRAPH_REQUIREMENTS,
        region=region,
        account_id=account_id,
        cp=cp,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    region = get_region()
    account_id = get_account_id(region)
    cp = boto3.client("bedrock-agentcore-control", region_name=region)

    print(f"Region : {region}")
    print(f"Account: {account_id}")

    strands_id, strands_arn = deploy_strands(region, account_id, cp)
    langgraph_id, langgraph_arn = deploy_langgraph(region, account_id, cp)

    config = {
        "strands": {"agent_id": strands_id, "agent_arn": strands_arn},
        "langgraph": {"agent_id": langgraph_id, "agent_arn": langgraph_arn},
        "region": region,
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\nConfig saved to {CONFIG_FILE}")
    print(f"  Strands   agent_id : {strands_id}")
    print(f"  LangGraph agent_id : {langgraph_id}")


if __name__ == "__main__":
    main()
