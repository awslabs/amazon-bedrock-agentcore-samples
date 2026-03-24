import os
import base64
import hashlib
import hmac
import json
import boto3
from boto3.session import Session
from typing import Optional


SAMPLE_ROLE_NAME = "SessionDemoBedrockAgentCoreRole"
POLICY_NAME = "AWSMCPtBedrockAgentCorePolicy"
#S3_PREFIX = "SessionDemoBucket"

def get_aws_account_id() -> str:
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Account"]


# def create_s3_bucket() -> Optional[str]:
#     """Create S3 bucket for session storage."""
#     s3 = boto3.client("s3")
#     boto_session = Session()
#     region = boto_session.region_name
#     account_id = get_aws_account_id()
    
#     bucket_name = f"{S3_PREFIX.lower()}-{account_id}-{region}"
    
#     try:
#         if region == "us-east-1":
#             s3.create_bucket(Bucket=bucket_name)
#         else:
#             s3.create_bucket(
#                 Bucket=bucket_name,
#                 CreateBucketConfiguration={"LocationConstraint": region}
#             )
#         print(f"✅ Created S3 bucket: {bucket_name}")
#         return bucket_name
#     except s3.exceptions.BucketAlreadyOwnedByYou:
#         print(f"ℹ️ Bucket {bucket_name} already exists")
#         return bucket_name
#     except Exception as e:
#         print(f"❌ Error creating S3 bucket: {str(e)}")
#         return None


# def upload_file_to_s3(file_path: str, s3_prefix: str) -> Optional[str]:
#     """Upload file to S3 bucket."""
#     s3 = boto3.client("s3")
#     boto_session = Session()
#     region = boto_session.region_name
#     account_id = get_aws_account_id()
    
#     bucket_name = f"{S3_PREFIX.lower()}-{account_id}-{region}"
#     file_name = os.path.basename(file_path)
#     s3_key = f"{s3_prefix}/{file_name}"
    
#     try:
#         s3.upload_file(file_path, bucket_name, s3_key)
#         print(f"✅ Uploaded {file_path} to s3://{bucket_name}/{s3_key}")
#         return f"s3://{bucket_name}/{s3_key}"
#     except Exception as e:
#         print(f"❌ Error uploading file: {str(e)}")
#         return None


def create_agentcore_runtime_execution_role(role_name: str) -> Optional[str]:
    """Create IAM role for AgentCore runtime execution."""
    iam = boto3.client("iam")
    boto_session = Session()
    region = boto_session.region_name
    account_id = get_aws_account_id()

    # Trust relationship policy
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {"Service": [
                                "bedrock-agentcore.amazonaws.com",
                                "developer.genesis-service.aws.internal",
                                "preprod.genesis-service.aws.internal"]
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {
                        "aws:SourceArn": (
                            f"arn:aws:bedrock-agentcore:{region}:"
                            f"{account_id}:*"
                        )
                    },
                },
            }
        ],
    }

    # IAM policy document
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ECRImageAccess",
                "Effect": "Allow",
                "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                "Resource": [
                    f"arn:aws:ecr:{region}:{account_id}:repository/*"
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:DescribeLogStreams", "logs:CreateLogGroup"],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:"
                    "/aws/bedrock-agentcore/runtimes/*"
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:DescribeLogGroups"],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:*"
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:"
                    "/aws/bedrock-agentcore/runtimes/*:log-stream:*"
                ],
            },
            {
                "Sid": "ECRTokenAccess",
                "Effect": "Allow",
                "Action": ["ecr:GetAuthorizationToken"],
                "Resource": "*",
            },
            {
                "Effect": "Allow",
                "Action": [
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                "Resource": ["*"],
            },
            {
                "Effect": "Allow",
                "Resource": "*",
                "Action": "cloudwatch:PutMetricData",
                "Condition": {
                    "StringEquals": {
                        "cloudwatch:namespace": "bedrock-agentcore"
                    }
                },
            },
            {
                "Sid": "GetAgentAccessToken",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:"
                    f"workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:"
                    "workload-identity-directory/default/workload-identity/*",
                ],
            },
            {
                "Sid": "BedrockModelInvocation",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:ApplyGuardrail",
                    "bedrock:Retrieve",
                ],
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:{region}:{account_id}:*",
                ],
            }#,
            # {
            #     "Sid": "S3BucketAccess",
            #     "Effect": "Allow",
            #     "Action": [
            #         "s3:GetObject",
            #         "s3:PutObject",
            #         "s3:DeleteObject",
            #         "s3:ListBucket"
            #     ],
            #     "Resource": [
            #         f"arn:aws:s3:::{S3_PREFIX.lower()}-{account_id}-{region}",
            #         f"arn:aws:s3:::{S3_PREFIX.lower()}-{account_id}-{region}/*"
            #     ],
            # },
            # {
            #     "Sid": "AllowAgentToUseMemory",
            #     "Effect": "Allow",
            #     "Action": [
            #         "bedrock-agentcore:CreateEvent",
            #         "bedrock-agentcore:GetMemoryRecord",
            #         "bedrock-agentcore:GetMemory",
            #         "bedrock-agentcore:RetrieveMemoryRecords",
            #         "bedrock-agentcore:ListMemoryRecords",
            #     ],
            #     "Resource": [
            #         f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
            #     ],
            # }
        ],
    }

    try:
        # Check if role already exists
        try:
            existing_role = iam.get_role(RoleName=role_name)
            print(f"ℹ️ Role {role_name} already exists")
            print(f"Role ARN: {existing_role['Role']['Arn']}")
            return existing_role["Role"]["Arn"]
        except iam.exceptions.NoSuchEntityException:
            pass

        # Create IAM role
        role_response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=(
                "IAM role for Amazon Bedrock AgentCore "
                "with required permissions"
            ),
        )

        print(f"✅ Created IAM role: {role_name}")
        print(f"Role ARN: {role_response['Role']['Arn']}")

        # Check if policy already exists
        policy_arn = f"arn:aws:iam::{account_id}:policy/{POLICY_NAME}"

        try:
            iam.get_policy(PolicyArn=policy_arn)
            print(f"ℹ️ Policy {POLICY_NAME} already exists")
        except iam.exceptions.NoSuchEntityException:
            # Create policy
            policy_response = iam.create_policy(
                PolicyName=POLICY_NAME,
                PolicyDocument=json.dumps(policy_document),
                Description="Policy for Amazon Bedrock AgentCore permissions",
            )
            print(f"✅ Created policy: {POLICY_NAME}")
            policy_arn = policy_response["Policy"]["Arn"]

        # Attach policy to role
        try:
            iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            print("✅ Attached policy to role")
        except iam.exceptions.ClientError as e:
            if "already attached" in str(e).lower():
                print("ℹ️ Policy already attached to role")
            else:
                raise

        print(f"Policy ARN: {policy_arn}")
        return role_response["Role"]["Arn"]

    except iam.exceptions.ClientError as e:
        print(f"❌ Error creating IAM role: {str(e)}")
        return None


def delete_agentcore_runtime_execution_role(role_name: str) -> None:
    """Delete AgentCore runtime execution role and associated policy."""
    iam = boto3.client("iam")

    try:
        account_id = get_aws_account_id()
        policy_arn = f"arn:aws:iam::{account_id}:policy/{POLICY_NAME}"

        # Detach policy from role
        try:
            iam.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            print("✅ Detached policy from role")
        except iam.exceptions.ClientError:
            pass

        # Delete role
        try:
            iam.delete_role(RoleName=role_name)
            print(f"✅ Deleted role: {role_name}")
        except iam.exceptions.ClientError:
            pass

        # Delete policy
        try:
            iam.delete_policy(PolicyArn=policy_arn)
            print(f"✅ Deleted policy: {POLICY_NAME}")
        except iam.exceptions.ClientError:
            pass

    except iam.exceptions.ClientError as e:
        print(f"❌ Error during cleanup: {str(e)}")


def local_file_cleanup() -> None:
    """Clean up local files created during the tutorial."""
    # List of files to clean up
    files_to_delete = [
        "Dockerfile",
        ".dockerignore",
        ".bedrock_agentcore.yaml"
    ]

    deleted_files = []
    missing_files = []

    for file in files_to_delete:
        if os.path.exists(file):
            try:
                os.unlink(file)
                deleted_files.append(file)
                print(f"  ✅ Deleted {file}")
            except OSError as e:
                print(f"  ⚠️  Error deleting {file}: {e}")
        else:
            missing_files.append(file)

    if deleted_files:
        print(f"\n📁 Successfully deleted {len(deleted_files)} files")
    if missing_files:
        print(
            f"ℹ️  {len(missing_files)} files were already missing: "
            f"{', '.join(missing_files)}"
        )