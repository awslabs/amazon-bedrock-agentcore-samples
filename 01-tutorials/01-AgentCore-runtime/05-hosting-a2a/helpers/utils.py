import base64
import hashlib
import hmac
import json
import os

import boto3
from boto3.session import Session

sts_client = boto3.client("sts")

# Get AWS account details
REGION = boto3.session.Session().region_name

username = "testuser"
secret_name = "aws_docs_assistant"
ssm_docs_agent_role_arn = "/app/aws_docs_assistant/agentcore/runtime_execution_role_arn"
policy_name = f"AWSDocsAssistantBedrockAgentCorePolicy-{REGION}"
log_group_base_name = "/aws/bedrock-agentcore/runtimes/"


SSM_DOCS_AGENT_ARN = "/app/aws_docs_assistant/agentcore/agent_arn"
SSM_BLOGS_AGENT_ARN = "/app/aws_blogs_assistant/agentcore/agent_arn"

AWS_DOCS_ROLE_NAME = f"AWSDocsAssistantBedrockAgentCoreRole-{REGION}"
AWS_BLOG_ROLE_NAME = f"AWSBlogsAssistantBedrockAgentCoreRole-{REGION}"
ORCHESTRATOR_ROLE_NAME = f"AWSOrchestratorAssistantAgentCoreRole-{REGION}"



################################################
## General
################################################
def get_aws_account_id() -> str:
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Account"]


def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    ssm = boto3.client("ssm")

    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)

    return response["Parameter"]["Value"]


def put_ssm_parameter(
    name: str, value: str, parameter_type: str = "String", with_encryption: bool = False
) -> None:
    ssm = boto3.client("ssm")
    put_params = {
        "Name": name,
        "Value": value,
        "Type": parameter_type,
        "Overwrite": True,
    }
    if with_encryption:
        put_params["Type"] = "SecureString"

    ssm.put_parameter(**put_params)


def delete_ssm_parameter(name: str) -> None:
    ssm = boto3.client("ssm")
    try:
        ssm.delete_parameter(Name=name)
    except ssm.exceptions.ParameterNotFound:
        pass


def save_secret(secret_value):
    """Save a secret in AWS Secrets Manager."""
    boto_session = Session()
    region = boto_session.region_name
    secrets_client = boto3.client("secretsmanager", region_name=region)

    try:
        secrets_client.create_secret(
            Name=secret_name,
            SecretString=secret_value,
            Description="Secret containing the Cognito Configuration for the AWS Docs Agent",
        )
        print("✅ Created secret")
    except secrets_client.exceptions.ResourceExistsException:
        secrets_client.update_secret(SecretId=secret_name, SecretString=secret_value)
        print("✅ Updated existing secret")
    except Exception as e:
        print(f"❌ Error saving secret: {str(e)}")
        return False
    return True


def get_cognito_secret():
    """Get a secret value from AWS Secrets Manager."""
    boto_session = Session()
    region = boto_session.region_name
    secrets_client = boto3.client("secretsmanager", region_name=region)
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        return response["SecretString"]
    except Exception as e:
        print(f"❌ Error getting secret: {str(e)}")
        return None


def delete_cognito_secret():
    """Delete a secret from AWS Secrets Manager."""
    boto_session = Session()
    region = boto_session.region_name
    secrets_client = boto3.client("secretsmanager", region_name=region)
    try:
        secrets_client.delete_secret(
            SecretId=secret_name, ForceDeleteWithoutRecovery=True
        )
        print("✅ Secret Deleted")
        return True
    except Exception as e:
        print(f"❌ Error deleting secret: {str(e)}")
        return False

################################################
## Cognito Resources
################################################
def reauthenticate_user(client_id, client_secret):
    boto_session = Session()
    region = boto_session.region_name
    # Initialize Cognito client
    cognito_client = boto3.client("cognito-idp", region_name=region)
    # Authenticate User and get Access Token

    message = bytes(username + client_id, "utf-8")
    key = bytes(client_secret, "utf-8")
    secret_hash = base64.b64encode(
        hmac.new(key, message, digestmod=hashlib.sha256).digest()
    ).decode()

    auth_response = cognito_client.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": username,
            "PASSWORD": "MyPassword123!",
            "SECRET_HASH": secret_hash,
        },
    )
    bearer_token = auth_response["AuthenticationResult"]["AccessToken"]
    return bearer_token


def setup_cognito_user_pool():
    boto_session = Session()
    region = boto_session.region_name
    # Initialize Cognito client
    cognito_client = boto3.client("cognito-idp", region_name=region)
    try:
        # Create User Pool
        user_pool_response = cognito_client.create_user_pool(
            PoolName="MCPServerPool", Policies={"PasswordPolicy": {"MinimumLength": 8}}
        )
        pool_id = user_pool_response["UserPool"]["Id"]
        # Create App Client
        app_client_response = cognito_client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName="MCPServerPoolClient",
            GenerateSecret=True,
            ExplicitAuthFlows=[
                "ALLOW_USER_PASSWORD_AUTH",
                "ALLOW_REFRESH_TOKEN_AUTH",
                "ALLOW_USER_SRP_AUTH",
            ],
        )
        print(app_client_response["UserPoolClient"])
        client_id = app_client_response["UserPoolClient"]["ClientId"]
        client_secret = app_client_response["UserPoolClient"]["ClientSecret"]

        # Create User
        cognito_client.admin_create_user(
            UserPoolId=pool_id,
            Username=username,
            TemporaryPassword="Temp123!",
            MessageAction="SUPPRESS",
        )

        # Set Permanent Password
        cognito_client.admin_set_user_password(
            UserPoolId=pool_id,
            Username=username,
            Password="MyPassword123!",
            Permanent=True,
        )

        app_client_id = client_id
        key = client_secret
        message = bytes(username + app_client_id, "utf-8")
        key = bytes(key, "utf-8")
        secret_hash = base64.b64encode(
            hmac.new(key, message, digestmod=hashlib.sha256).digest()
        ).decode()

        # Authenticate User and get Access Token
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": "testuser",
                "PASSWORD": "MyPassword123!",
                "SECRET_HASH": secret_hash,
            },
        )
        bearer_token = auth_response["AuthenticationResult"]["AccessToken"]
        # Output the required values
        print(f"Pool id: {pool_id}")
        print(
            f"Discovery URL: https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
        )
        print(f"Client ID: {client_id}")
        print(f"Bearer Token: {bearer_token}")

        # Return values if needed for further processing
        cognito_config = {
            "pool_id": pool_id,
            "client_id": client_id,
            "client_secret": client_secret,
            "secret_hash": secret_hash,
            "bearer_token": bearer_token,
            "discovery_url": f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration",
        }

        save_secret(json.dumps(cognito_config))

        return cognito_config
    except Exception as e:
        print(f"Error: {e}")
        return None


def cleanup_cognito_resources(pool_id):
    """
    Delete Cognito resources including users, app clients, and user pool
    """
    try:
        # Initialize Cognito client using the same session configuration
        boto_session = Session()
        region = boto_session.region_name
        cognito_client = boto3.client("cognito-idp", region_name=region)

        if pool_id:
            try:
                # List and delete all app clients
                clients_response = cognito_client.list_user_pool_clients(
                    UserPoolId=pool_id, MaxResults=60
                )

                for client in clients_response["UserPoolClients"]:
                    print(f"Deleting app client: {client['ClientName']}")
                    cognito_client.delete_user_pool_client(
                        UserPoolId=pool_id, ClientId=client["ClientId"]
                    )

                # List and delete all users
                users_response = cognito_client.list_users(
                    UserPoolId=pool_id, AttributesToGet=["email"]
                )

                for user in users_response.get("Users", []):
                    print(f"Deleting user: {user['Username']}")
                    cognito_client.admin_delete_user(
                        UserPoolId=pool_id, Username=user["Username"]
                    )

                # Delete the user pool
                print(f"Deleting user pool: {pool_id}")
                cognito_client.delete_user_pool(UserPoolId=pool_id)

                print("Successfully cleaned up all Cognito resources")
                return True

            except cognito_client.exceptions.ResourceNotFoundException:
                print(
                    f"User pool {pool_id} not found. It may have already been deleted."
                )
                return True

            except Exception as e:
                print(f"Error during cleanup: {str(e)}")
                return False
        else:
            print("No matching user pool found")
            return True

    except Exception as e:
        print(f"Error initializing cleanup: {str(e)}")
        return False

################################################
## AgentCore Resources
################################################
def create_agentcore_runtime_execution_role(role_name):
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
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": account_id},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
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
                "Resource": [f"arn:aws:ecr:{region}:{account_id}:repository/*"],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:DescribeLogStreams", "logs:CreateLogGroup"],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
                ],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:DescribeLogGroups"],
                "Resource": [f"arn:aws:logs:{region}:{account_id}:log-group:*"],
            },
            {
                "Effect": "Allow",
                "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
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
                    "StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}
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
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/*",
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
            },
            {
                "Sid": "AllowAgentToUseMemory",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:GetMemoryRecord",
                    "bedrock-agentcore:GetMemory",
                    "bedrock-agentcore:RetrieveMemoryRecords",
                    "bedrock-agentcore:ListMemoryRecords",
                ],
                "Resource": [f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"],
            },
            {
                "Sid": "GetMemoryId",
                "Effect": "Allow",
                "Action": ["ssm:GetParameter"],
                "Resource": [f"arn:aws:ssm:{region}:{account_id}:parameter/*"],
            },
            {
                "Sid": "GetSecrets",
                "Effect": "Allow",
                "Action": ["secretsmanager:GetSecretValue"],
                "Resource": [f"arn:aws:secretsmanager:{region}:{account_id}:secret:{secret_name}*"],
            }
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
            Description="IAM role for Amazon Bedrock AgentCore with required permissions",
        )

        print(f"✅ Created IAM role: {role_name}")
        print(f"Role ARN: {role_response['Role']['Arn']}")

        # Check if policy already exists
        policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

        try:
            iam.get_policy(PolicyArn=policy_arn)
            print(f"ℹ️ Policy {policy_name} already exists")
        except iam.exceptions.NoSuchEntityException:
            # Create policy
            policy_response = iam.create_policy(
                PolicyName=policy_name,
                PolicyDocument=json.dumps(policy_document),
                Description="Policy for Amazon Bedrock AgentCore permissions",
            )
            print(f"✅ Created policy: {policy_name}")
            policy_arn = policy_response["Policy"]["Arn"]

        # Attach policy to role
        try:
            iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            print("✅ Attached policy to role")
        except Exception as e:
            if "already attached" in str(e).lower():
                print("ℹ️ Policy already attached to role")
            else:
                raise

        print(f"Policy ARN: {policy_arn}")

        put_ssm_parameter(
            ssm_docs_agent_role_arn,
            role_response["Role"]["Arn"],
        )
        return role_response["Role"]["Arn"]

    except Exception as e:
        print(f"❌ Error creating IAM role: {str(e)}")
        return None


def delete_agentcore_runtime_execution_role(role_name):
    iam = boto3.client("iam")

    try:
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        policy_arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"

        # Detach policy from role
        try:
            iam.detach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
            print("✅ Detached policy from role")
        except Exception:
            pass

        # Delete role
        try:
            iam.delete_role(RoleName=role_name)
            print(f"✅ Deleted role: {role_name}")
        except Exception:
            pass

        # Delete policy
        try:
            iam.delete_policy(PolicyArn=policy_arn)
            print(f"✅ Deleted policy: {policy_name}")
        except Exception:
            pass

        delete_ssm_parameter(
            ssm_docs_agent_role_arn
        )

    except Exception as e:
        print(f"❌ Error during cleanup: {str(e)}")


def runtime_resource_cleanup(agent_runtime_id):
    try:
        # Initialize AWS clients
        agentcore_control_client = boto3.client("bedrock-agentcore-control", region_name=REGION)
        
        # Delete the AgentCore Runtime
        #runtimes = agentcore_control_client.list_agent_runtimes()
        #for runtime in runtimes['agentRuntimes']:        
        #    response = agentcore_control_client.delete_agent_runtime(
        #        agentRuntimeId=runtime['agentRuntimeId']
        #    )

        response = agentcore_control_client.delete_agent_runtime(
                agentRuntimeId=agent_runtime_id
        )
        print(f"  ✅ Agent runtime {agent_runtime_id} deleted: {response['status']}")
    except Exception as e:
        print(f"  ⚠️  Error during runtime cleanup: {e}")


def ecr_repo_cleanup():
    try: 
        ecr_client = boto3.client("ecr", region_name=REGION)
        # Delete the ECR repository
        print("  🗑️  Deleting ECR repository...")
        repositories = ecr_client.describe_repositories()
        for repo in repositories['repositories']:
            repo_name = repo['repositoryName']
            if any(name in repo_name for name in ['bedrock-agentcore-aws_docs_assistant', 
                                                  'bedrock-agentcore-aws_blog_assistant',
                                                  'bedrock-agentcore-aws_orchestrator_assistant']):
                ecr_client.delete_repository(
                    repositoryName=repo_name,
                    force=True
                )
                print(f"  ✅ ECR repository deleted: {repo_name}")    
    except Exception as e:
        print(f"  ⚠️  Error during ECR cleanup: {e}")


def get_memory_name(agent_name):
    try:
        agentcore_control_client = boto3.client("bedrock-agentcore-control", region_name=REGION)
        resp = agentcore_control_client.list_memories()
        for mem in resp['memories']:
            if agent_name in mem['id']:
                return mem['id']
    except Exception as e:
        print(f"  ⚠️  Error getting memories: {e}")


def short_memory_cleanup(agent_name):
    try:
        agentcore_control_client = boto3.client("bedrock-agentcore-control", region_name=REGION)
        memory_id = get_memory_name(agent_name)
        agentcore_control_client.delete_memory(memoryId=memory_id)
        print(f" ✅ Memory {memory_id} deleted.")
    except Exception as e:
        print(f"  ⚠️  Error deleting memories: {e}")

################################################
## Observability Cleanup
################################################
def delete_observability_resources(agent_name):
    # Configuration
    log_stream_name = "default"
    
    logs_client = boto3.client("logs", region_name=REGION)
    
    complete_log_group = log_group_base_name + agent_name + '-DEFAULT'

    # Delete log stream first (must be done before deleting log group)
    try:
        print(f"  🗑️  Deleting log stream '{log_stream_name}'...")
        logs_client.delete_log_stream(
            logGroupName=complete_log_group, logStreamName=log_stream_name
        )
        print(f"  ✅ Log stream '{log_stream_name}' deleted successfully")
    except Exception as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"  ℹ️  Log stream '{log_stream_name}' doesn't exist")
        else:
            print(f"  ⚠️  Error deleting log stream: {e}")
    
    # Delete log group
    try:
        print(f"  🗑️  Deleting log group '{complete_log_group}'...")
        logs_client.delete_log_group(logGroupName=complete_log_group)
        print(f"  ✅ Log group '{complete_log_group}' deleted successfully")
    except Exception as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"  ℹ️  Log group '{complete_log_group}' doesn't exist")
        else:
            print(f"  ⚠️  Error deleting log group: {e}")

################################################
## Local Files Cleanup
################################################
def local_file_cleanup():
    # List of files to clean up
    files_to_delete = [
        "Dockerfile",
        ".dockerignore",
        ".bedrock_agentcore.yaml",
        "agents/strands_aws_docs.py",
        "agents/orchestrator.py",
        "agents/requirements.txt",
        "agents/strands_aws_blogs_news.py"
    ]
    
    deleted_files = []
    missing_files = []

    for file in files_to_delete:
        if os.path.exists(file):
            try:
                os.unlink(file)
                deleted_files.append(file)
                print(f"  ✅ Deleted {file}")
            except Exception as e:
                print(f"  ⚠️  Error deleting {file}: {e}")
        else:
            missing_files.append(file)
    
    if deleted_files:
        print(f"\n📁 Successfully deleted {len(deleted_files)} files")
    if missing_files:
        print(f"ℹ️  {len(missing_files)} files were already missing: {', '.join(missing_files)}")