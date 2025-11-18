import os
import boto3
import json
import time
import requests

import botocore
from boto3.session import Session
from botocore.exceptions import ClientError


cognito = boto3.client("cognito-idp")
gateway_client = boto3.client('bedrock-agentcore-control')
iam_client = boto3.client("iam")
boto_session = Session()
region = boto_session.region_name
account_id = boto3.client("sts").get_caller_identity()["Account"]

policy_name = f"HomeAssistantBedrockAgentCorePolicy-{region}"
SmartHomeBucketName = "process-camera-streams-cameraresultsbucket-uzdhzgcitetc"

def create_agentcore_gateway_role(gateway_name):
    agentcore_gateway_role_name = f'agentcore-{gateway_name}-role'
    role_policy = {
        "Version": "2012-10-17",
        "Statement": [{
                "Sid": "VisualEditor0",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:*",
                    "bedrock:*",
                    "agent-credential-provider:*",
                    "iam:PassRole",
                    "secretsmanager:GetSecretValue",
                    "lambda:InvokeFunction"
                ],
                "Resource": "*"
            }
        ]
    }

    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": f"{account_id}"
                    },
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                    }
                }
            }
        ]
    }

    assume_role_policy_document_json = json.dumps(
        assume_role_policy_document
    )

    role_policy_document = json.dumps(role_policy)
    # Create IAM Role
    try:
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_gateway_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )

        # Pause to make sure role is created
        time.sleep(10)
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("Role already exists -- deleting and creating it again")
        policies = iam_client.list_role_policies(
            RoleName=agentcore_gateway_role_name,
            MaxItems=100
        )
        print("policies:", policies)
        for policy_name in policies['PolicyNames']:
            iam_client.delete_role_policy(
                RoleName=agentcore_gateway_role_name,
                PolicyName=policy_name
            )
        print(f"deleting {agentcore_gateway_role_name}")
        iam_client.delete_role(
            RoleName=agentcore_gateway_role_name
        )
        print(f"recreating {agentcore_gateway_role_name}")
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_gateway_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )

    # Attach the policy
    print(f"attaching role policy {agentcore_gateway_role_name}")
    try:
        iam_client.put_role_policy(
            PolicyDocument=role_policy_document,
            PolicyName="AgentCorePolicy",
            RoleName=agentcore_gateway_role_name
        )
    except Exception as e:
        print(e)

    return agentcore_iam_role


def get_or_create_user_pool(USER_POOL_NAME):
    response = cognito.list_user_pools(MaxResults=60)
    for pool in response["UserPools"]:
        if pool["Name"] == USER_POOL_NAME:
            user_pool_id = pool["Id"]
            response = cognito.describe_user_pool(
                UserPoolId=user_pool_id
            )
        
            # Get the domain from user pool description
            user_pool = response.get('UserPool', {})
            domain = user_pool.get('Domain')
        
            if domain:
                region = user_pool_id.split('_')[0] if '_' in user_pool_id else REGION
                domain_url = f"https://{domain}.auth.{region}.amazoncognito.com"
                print(f"Found domain for user pool {user_pool_id}: {domain} ({domain_url})")
            else:
                print(f"No domains found for user pool {user_pool_id}")
            return pool["Id"]
    print('Creating new user pool')
    created = cognito.create_user_pool(PoolName=USER_POOL_NAME)
    user_pool_id = created["UserPool"]["Id"]
    user_pool_id_without_underscore_lc = user_pool_id.replace("_", "").lower()
    cognito.create_user_pool_domain(
        Domain=user_pool_id_without_underscore_lc,
        UserPoolId=user_pool_id
    )
    print("Domain created as well")
    return created["UserPool"]["Id"]


def get_or_create_resource_server(user_pool_id, RESOURCE_SERVER_ID, RESOURCE_SERVER_NAME, SCOPES):
    try:
        existing = cognito.describe_resource_server(
            UserPoolId=user_pool_id,
            Identifier=RESOURCE_SERVER_ID
        )
        return RESOURCE_SERVER_ID
    except cognito.exceptions.ResourceNotFoundException:
        print('creating new resource server')
        cognito.create_resource_server(
            UserPoolId=user_pool_id,
            Identifier=RESOURCE_SERVER_ID,
            Name=RESOURCE_SERVER_NAME,
            Scopes=SCOPES
        )
        return RESOURCE_SERVER_ID


def get_or_create_m2m_client(user_pool_id, CLIENT_NAME, RESOURCE_SERVER_ID, SCOPES=None):
    response = cognito.list_user_pool_clients(UserPoolId=user_pool_id, MaxResults=60)
    for client in response["UserPoolClients"]:
        if client["ClientName"] == CLIENT_NAME:
            describe = cognito.describe_user_pool_client(UserPoolId=user_pool_id, ClientId=client["ClientId"])
            return client["ClientId"], describe["UserPoolClient"]["ClientSecret"]
    print('creating new m2m client')

    # Default scopes if not provided (for backward compatibility)
    if SCOPES is None:
        SCOPES = [f"{RESOURCE_SERVER_ID}/gateway:read", f"{RESOURCE_SERVER_ID}/gateway:write"]

    created = cognito.create_user_pool_client(
        UserPoolId=user_pool_id,
        ClientName=CLIENT_NAME,
        GenerateSecret=True,
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=SCOPES,
        AllowedOAuthFlowsUserPoolClient=True,
        SupportedIdentityProviders=["COGNITO"],
        ExplicitAuthFlows=["ALLOW_REFRESH_TOKEN_AUTH"]
    )
    return created["UserPoolClient"]["ClientId"], created["UserPoolClient"]["ClientSecret"]


def get_token(user_pool_id: str, client_id: str, client_secret: str, scope_string: str, REGION: str) -> dict:
    try:
        user_pool_id_without_underscore = user_pool_id.replace("_", "")
        url = f"https://{user_pool_id_without_underscore}.auth.{REGION}.amazoncognito.com/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope_string,

        }
        print(client_id)
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as err:
        return {"error": str(err)}


def delete_gateway(gatewayId): 
    print("Deleting all targets for gateway", gatewayId)
    list_response = gateway_client.list_gateway_targets(
            gatewayIdentifier = gatewayId,
            maxResults=100
    )
    for item in list_response['items']:
        targetId = item["targetId"]
        print("Deleting target ", targetId)
        gateway_client.delete_gateway_target(
            gatewayIdentifier = gatewayId,
            targetId = targetId
        )
        time.sleep(5)
    print("Deleting gateway ", gatewayId)
    gateway_client.delete_gateway(gatewayIdentifier = gatewayId)


def delete_oauth2_provider(provider_name):
    """Delete Auth2 credential provider for AgentCore."""
    try:
        gateway_client.delete_oauth2_credential_provider(name=provider_name)
    except Exception as e:
        print(f'Error during deletion of oauth2 credential provider: {e}')


def delete_agentcore_runtime_execution_role(role_name: str) -> None:
    """Delete AgentCore runtime execution role and associated policy."""
    try:
        account_id = boto3.client("sts").get_caller_identity()["Account"]
        
        policies = iam_client.list_role_policies(
            RoleName=role_name,
            MaxItems=100
        )

        print("policies:", policies)
        for policy_name in policies['PolicyNames']:
            iam_client.delete_role_policy(
                RoleName=role_name,
                PolicyName=policy_name
            )
        # Delete role
        try:
            iam_client.delete_role(RoleName=role_name)
            print(f"✅ Deleted role: {role_name}")
        except iam.exceptions.ClientError:
            pass

    except iam_client.exceptions.ClientError as e:
        print(f"❌ Error during cleanup: {str(e)}")


def cleanup_cognito_resources(pool_id: str) -> bool:
    """Delete Cognito resources including users, app clients, and user pool."""
    try:
        if pool_id:
            try:
                # List and delete all app clients
                clients_response = cognito.list_user_pool_clients(
                    UserPoolId=pool_id, MaxResults=60
                )

                for client in clients_response["UserPoolClients"]:
                    print(f"Deleting app client: {client['ClientName']}")
                    cognito.delete_user_pool_client(
                        UserPoolId=pool_id, ClientId=client["ClientId"]
                    )

                # List and delete all users
                users_response = cognito.list_users(
                    UserPoolId=pool_id, AttributesToGet=["email"]
                )

                for user in users_response.get("Users", []):
                    print(f"Deleting user: {user['Username']}")
                    cognito.admin_delete_user(
                        UserPoolId=pool_id, Username=user["Username"]
                    )

                response = cognito.describe_user_pool(
                    UserPoolId=pool_id
                )
                # Get the domain from user pool description
                user_pool = response.get('UserPool', {})
                domain = user_pool.get('Domain')

                # Delete Domain
                response = cognito.delete_user_pool_domain(
                    Domain=domain,
                    UserPoolId=pool_id
                )

                # Delete the user pool
                print(f"Deleting user pool: {pool_id}")
                cognito.delete_user_pool(UserPoolId=pool_id)

                print("Successfully cleaned up all Cognito resources")
                return True

            except cognito.exceptions.ResourceNotFoundException:
                print(
                    f"User pool {pool_id} not found. "
                    "It may have already been deleted."
                )
                return True

            except cognito.exceptions.ClientError as e:
                print(f"Error during cleanup: {str(e)}")
                return False
        else:
            print("No matching user pool found")
            return True

    except cognito.exceptions.ClientError as e:
        print(f"Error initializing cleanup: {str(e)}")
        return False


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


def create_agentcore_runtime_execution_role_v2 (runtime_name):
    agentcore_runtime_role_name = f'agentcore-{runtime_name}-role'
    role_policy = {
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
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/customer_support_agent-*",
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
                    "bedrock-agentcore:ListEvents",
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
                "Sid": "GatewayAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetGateway",
                    "bedrock-agentcore:InvokeGateway",
                ],
                "Resource": [
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}:gateway/*"
                ],
            },
            {
                "Sid": "AthenaAccess",
                "Effect": "Allow",
                "Action": [
                    "athena:StartQueryExecution",
                    "athena:GetQueryExecution",
                    "athena:GetQueryResults",
                    "athena:StopQueryExecution",
                    "athena:GetWorkGroup",
                ],
                "Resource": [
                    f"arn:aws:athena:{region}:{account_id}:*"
                ],
            },
            {
                "Sid": "GlueAccess",
                "Effect": "Allow",
                "Action": [
                    "glue:GetDatabase",
                    "glue:GetTable",
                    "glue:GetPartitions"
                ],
                "Resource": [
                    f"arn:aws:glue:{region}:{account_id}:*"
                ],
            },
            {
                "Sid": "AthenaS3Access",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:ListBucket",
                    "s3:PutObject",
                    "s3:GetBucketLocation",
                ],
                "Resource": [
                    f"arn:aws:s3:::{SmartHomeBucketName}",
                    f"arn:aws:s3:::{SmartHomeBucketName}/*"
                ],
            },
        ],
    }

    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": f"{account_id}"
                    },
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                    }
                }
            }
        ]
    }

    assume_role_policy_document_json = json.dumps(
        assume_role_policy_document
    )

    role_policy_document = json.dumps(role_policy)
    # Create IAM Role
    try:
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_runtime_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )

        # Pause to make sure role is created
        time.sleep(10)
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("Role already exists -- deleting and creating it again")
        policies = iam_client.list_role_policies(
            RoleName=agentcore_runtime_role_name,
            MaxItems=100
        )
        print("policies:", policies)
        for policy_name in policies['PolicyNames']:
            iam_client.delete_role_policy(
                RoleName=agentcore_runtime_role_name,
                PolicyName=policy_name
            )
        print(f"deleting {agentcore_runtime_role_name}")
        iam_client.delete_role(
            RoleName=agentcore_runtime_role_name
        )
        print(f"recreating {agentcore_runtime_role_name}")
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_runtime_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json
        )

    # Attach the policy
    print(f"attaching role policy {agentcore_runtime_role_name}")
    try:
        iam_client.put_role_policy(
            PolicyDocument=role_policy_document,
            PolicyName="AgentCorePolicy",
            RoleName=agentcore_runtime_role_name
        )
    except Exception as e:
        print(e)

    return agentcore_iam_role