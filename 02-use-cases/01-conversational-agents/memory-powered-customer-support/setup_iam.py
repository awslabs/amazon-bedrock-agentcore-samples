"""
IAM Role Setup for AgentCore Memory Execution

Creates the IAM role required by AgentCore Memory to invoke
Amazon Bedrock models for semantic extraction strategies.
"""

import json
import os
import sys

import boto3
from botocore.exceptions import ClientError

REGION = os.getenv("AWS_REGION", "us-east-1")
ROLE_NAME = "AgentCoreMemoryExecutionRole"


def create_memory_execution_role():
    """Create the IAM execution role for AgentCore Memory."""
    iam = boto3.client("iam", region_name=REGION)
    sts = boto3.client("sts", region_name=REGION)
    account_id = sts.get_caller_identity()["Account"]

    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    bedrock_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                "Resource": "*",
            }
        ],
    }

    try:
        iam.get_role(RoleName=ROLE_NAME)
        print(f"Role '{ROLE_NAME}' already exists.")
    except iam.exceptions.NoSuchEntityException:
        iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Execution role for AgentCore Memory semantic extraction",
        )
        iam.put_role_policy(
            RoleName=ROLE_NAME,
            PolicyName="BedrockModelAccess",
            PolicyDocument=json.dumps(bedrock_policy),
        )
        print(f"Created role '{ROLE_NAME}' successfully.")
        print("Note: Allow 10-15 seconds for IAM propagation before using.")

    role_arn = f"arn:aws:iam::{account_id}:role/{ROLE_NAME}"
    print("\nSet this environment variable:")
    print(f"  export MEMORY_EXECUTION_ROLE_ARN={role_arn}")
    return role_arn


if __name__ == "__main__":
    create_memory_execution_role()
