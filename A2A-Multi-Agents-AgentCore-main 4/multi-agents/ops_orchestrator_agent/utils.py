import boto3
import json
import time
from boto3.session import Session
import botocore
import requests
import os
import time
import logging
import yaml
from typing import Optional, Dict, Union, List
from pathlib import Path
from botocore.exceptions import ClientError

# set a logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_parameter_from_ssm(
    parameter_name: str,
    region_name: str = "us-west-2",
    decrypt: bool = True
) -> str:
    """
    Retrieve parameter from AWS Systems Manager Parameter Store.

    Args:
        parameter_name: Name of the SSM parameter (e.g., '/ops-orchestrator/tavily-api-key')
        region_name: AWS region where the parameter is stored
        decrypt: Whether to decrypt SecureString parameters

    Returns:
        Parameter value as string

    Raises:
        ClientError: If parameter not found or access denied
    """
    ssm_client = boto3.client('ssm', region_name=region_name)
    try:
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=decrypt
        )
        return response['Parameter']['Value']
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ParameterNotFound':
            logger.error(f"SSM parameter '{parameter_name}' not found in region {region_name}")
        elif error_code == 'AccessDeniedException':
            logger.error(f"Access denied to SSM parameter '{parameter_name}'. Check IAM permissions.")
        else:
            logger.error(f"Error retrieving SSM parameter '{parameter_name}': {e}")
        raise


def load_api_keys_from_ssm(config_data: dict) -> dict:
    """
    Load API keys from SSM Parameter Store based on config.
    Falls back to environment variables if SSM retrieval fails.

    Args:
        config_data: Configuration dictionary containing SSM parameter paths

    Returns:
        Dictionary with API keys: {'TAVILY_API_KEY': '...', 'OPENAI_API_KEY': '...', ...}
    """
    api_keys = {}
    ssm_config = config_data.get('ssm_parameters', {})
    region = ssm_config.get('region', 'us-west-2')
    parameters = ssm_config.get('parameters', {})

    # Map of environment variable names to SSM parameter keys
    key_mapping = {
        'TAVILY_API_KEY': 'tavily_api_key',
        'OPENAI_API_KEY': 'openai_api_key',
        'JIRA_API_KEY': 'jira_api_key'
    }

    for env_var, param_key in key_mapping.items():
        try:
            # Try SSM first
            param_path = parameters.get(param_key)
            if param_path:
                logger.info(f"Retrieving {env_var} from SSM: {param_path}")
                api_keys[env_var] = get_parameter_from_ssm(param_path, region)
                logger.info(f"✅ Successfully retrieved {env_var} from SSM")
            else:
                # Fall back to environment variable
                logger.warning(f"No SSM parameter configured for {env_var}, checking environment variables")
                value = os.getenv(env_var)
                if value:
                    api_keys[env_var] = value
                    logger.info(f"✅ Loaded {env_var} from environment variable")
                else:
                    logger.error(f"❌ {env_var} not found in SSM or environment variables")
        except Exception as e:
            # Fall back to environment variable on any error
            logger.warning(f"Failed to retrieve {env_var} from SSM: {e}. Falling back to environment variable.")
            value = os.getenv(env_var)
            if value:
                api_keys[env_var] = value
                logger.info(f"✅ Loaded {env_var} from environment variable (fallback)")
            else:
                logger.error(f"❌ {env_var} not found in SSM or environment variables")

    return api_keys


def get_secret(secret_name: str, region_name: str = 'us-west-2') -> str:
    """
    Retrieve a secret from AWS Secrets Manager.
    
    Args:
        secret_name: Name of the secret in AWS Secrets Manager
        region_name: AWS region where the secret is stored (default: us-west-2)
        
    Returns:
        The secret value as a string
        
    Raises:
        ValueError: If secret cannot be retrieved
        
    Example:
        # Get OpenAI API key
        api_key = get_secret("prod/openai/api-key")
        
        # Get from different region
        api_key = get_secret("prod/openai/api-key", "us-east-1")
    """
    try:
        # Create a Secrets Manager client
        client = boto3.client('secretsmanager', region_name=region_name)
        
        logger.info(f"Retrieving secret '{secret_name}' from region '{region_name}'")
        
        response = client.get_secret_value(SecretId=secret_name)
        
        # Handle both string and JSON secrets
        secret_string = response['SecretString']
        
        try:
            # Try to parse as JSON first
            secret_data = json.loads(secret_string)
            # If it's a JSON object, look for common key patterns
            if isinstance(secret_data, dict):
                # Try common key patterns for API keys
                for key in ['api_key', 'key', 'value', 'OPENAI_API_KEY', 'TAVILY_API_KEY', 'JIRA_API_KEY']:
                    if key in secret_data:
                        logger.info(f"Successfully retrieved secret '{secret_name}' (JSON format)")
                        return secret_data[key]
                # If no standard key found, return the first value
                if secret_data:
                    logger.info(f"Successfully retrieved secret '{secret_name}' (JSON format, first value)")
                    return list(secret_data.values())[0]
                return secret_string
            return secret_string
        except json.JSONDecodeError:
            # It's a plain string secret
            logger.info(f"Successfully retrieved secret '{secret_name}' (plain string)")
            return secret_string
            
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        if error_code == 'ResourceNotFoundException':
            raise ValueError(f"Secret '{secret_name}' not found in region '{region_name}'. Please check the secret name and region.")
        elif error_code == 'InvalidParameterException':
            raise ValueError(f"Invalid parameter for secret '{secret_name}': {error_message}")
        elif error_code == 'InvalidRequestException':
            raise ValueError(f"Invalid request for secret '{secret_name}': {error_message}")
        elif error_code == 'DecryptionFailureException':
            raise ValueError(f"Failed to decrypt secret '{secret_name}': {error_message}")
        else:
            raise ValueError(f"Failed to retrieve secret '{secret_name}': {error_code} - {error_message}")
    except Exception as e:
        raise ValueError(f"Unexpected error retrieving secret '{secret_name}': {str(e)}")


def get_api_key(key_name: str, secret_name: Optional[str] = None, region_name: str = 'us-west-2') -> str:
    """
    Get API key from Secrets Manager with environment variable fallback.
    
    Args:
        key_name: Environment variable name (e.g., 'OPENAI_API_KEY')
        secret_name: AWS Secrets Manager secret name (e.g., 'prod/openai/api-key')
        region_name: AWS region for Secrets Manager
        
    Returns:
        The API key value
        
    Raises:
        ValueError: If key cannot be found in either location
        
    Example:
        # Try Secrets Manager first, fallback to env var
        openai_key = get_api_key('OPENAI_API_KEY', 'prod/openai/api-key')
        
        # Only use environment variable
        openai_key = get_api_key('OPENAI_API_KEY')
    """
    # First try Secrets Manager if secret name provided
    if secret_name:
        try:
            api_key = get_secret(secret_name, region_name)
            logger.info(f"Retrieved {key_name} from AWS Secrets Manager")
            return api_key
        except ValueError as e:
            logger.warning(f"Failed to get {key_name} from Secrets Manager: {e}")
            logger.info(f"Falling back to environment variable...")
    
    # Fallback to environment variable
    env_value = os.getenv(key_name)
    if env_value:
        logger.info(f"Retrieved {key_name} from environment variable")
        return env_value
    
    # If we get here, neither source worked
    sources = []
    if secret_name:
        sources.append(f"AWS Secrets Manager ({secret_name})")
    sources.append(f"environment variable ({key_name})")
    
    raise ValueError(f"Could not find {key_name} in any of: {', '.join(sources)}")


def load_config(config_file: Union[Path, str]) -> Optional[Dict]:
    """
    Load configuration from a local file.

    :param config_file: Path to the local file
    :return: Dictionary with the loaded configuration
    """
    try:
        config_data: Optional[Dict] = None
        logger.info(f"Loading config from local file system: {config_file}")
        content = Path(config_file).read_text()
        config_data = yaml.safe_load(content)
        logger.info(f"Loaded config from local file system: {config_data}")
    except Exception as e:
        logger.error(f"Error loading config from local file system: {e}")
        config_data = None
    return config_data

def setup_cognito_user_pool():
    boto_session = Session()
    region = boto_session.region_name
    
    # Initialize Cognito client
    cognito_client = boto3.client('cognito-idp', region_name=region)
    
    try:
        # Create User Pool
        user_pool_response = cognito_client.create_user_pool(
            PoolName='MCPServerPool',
            Policies={
                'PasswordPolicy': {
                    'MinimumLength': 8
                }
            }
        )
        pool_id = user_pool_response['UserPool']['Id']
        
        # Create App Client
        app_client_response = cognito_client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName='MCPServerPoolClient',
            GenerateSecret=False,
            ExplicitAuthFlows=[
                'ALLOW_USER_PASSWORD_AUTH',
                'ALLOW_REFRESH_TOKEN_AUTH'
            ]
        )
        client_id = app_client_response['UserPoolClient']['ClientId']
        
        # Create User
        cognito_client.admin_create_user(
            UserPoolId=pool_id,
            Username='testuser',
            TemporaryPassword='Temp123!',
            MessageAction='SUPPRESS'
        )
        
        # Set Permanent Password
        cognito_client.admin_set_user_password(
            UserPoolId=pool_id,
            Username='testuser',
            Password='MyPassword123!',
            Permanent=True
        )
        
        # Authenticate User and get Access Token
        auth_response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': 'testuser',
                'PASSWORD': 'MyPassword123!'
            }
        )
        bearer_token = auth_response['AuthenticationResult']['AccessToken']
        
        # Output the required values
        print(f"Pool id: {pool_id}")
        print(f"Discovery URL: https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration")
        print(f"Client ID: {client_id}")
        print(f"Bearer Token: {bearer_token}")
        
        # Return values if needed for further processing
        return {
            'pool_id': pool_id,
            'client_id': client_id,
            'bearer_token': bearer_token,
            'discovery_url':f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
        }
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def get_or_create_user_pool(cognito, USER_POOL_NAME, CREATE_USER_POOL: bool = False):
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
    if CREATE_USER_POOL:
        created = cognito.create_user_pool(PoolName=USER_POOL_NAME)
        user_pool_id = created["UserPool"]["Id"]
        # Create a valid domain name for Cognito (must be unique and follow DNS naming rules)
        import time
        timestamp = str(int(time.time()))
        domain_name = f"mcp-server-{timestamp}"
        cognito.create_user_pool_domain(
            Domain=domain_name,
            UserPoolId=user_pool_id
        )
        print("Domain created as well")
    else:
        print(f"User pool creation set to {CREATE_USER_POOL}. Returning.")
        return
    return created["UserPool"]["Id"]

def get_or_create_resource_server(cognito, user_pool_id, RESOURCE_SERVER_ID, RESOURCE_SERVER_NAME, SCOPES):
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

def get_or_create_m2m_client(cognito, user_pool_id, CLIENT_NAME, RESOURCE_SERVER_ID):
    response = cognito.list_user_pool_clients(UserPoolId=user_pool_id, MaxResults=60)
    for client in response["UserPoolClients"]:
        if client["ClientName"] == CLIENT_NAME:
            describe = cognito.describe_user_pool_client(UserPoolId=user_pool_id, ClientId=client["ClientId"])
            return client["ClientId"], describe["UserPoolClient"]["ClientSecret"]
    print('creating new m2m client')
    created = cognito.create_user_pool_client(
        UserPoolId=user_pool_id,
        ClientName=CLIENT_NAME,
        GenerateSecret=True,
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=[f"{RESOURCE_SERVER_ID}/gateway:read", f"{RESOURCE_SERVER_ID}/gateway:write"],
        AllowedOAuthFlowsUserPoolClient=True,
        SupportedIdentityProviders=["COGNITO"],
        ExplicitAuthFlows=["ALLOW_REFRESH_TOKEN_AUTH"]
    )
    return created["UserPoolClient"]["ClientId"], created["UserPoolClient"]["ClientSecret"]

def get_token(user_pool_id: str, client_id: str, client_secret: str, scope_string: str, REGION: str) -> dict:
    try:
        # Get the actual domain name for the user pool
        print(f"Going to get the token using the user pool id: {user_pool_id}, client id: {client_id}...")
        cognito = boto3.client("cognito-idp", region_name=REGION)
        user_pool_response = cognito.describe_user_pool(UserPoolId=user_pool_id)
        print(f"Describing the user pool: {user_pool_response}")
        domain = user_pool_response.get('UserPool', {}).get('Domain')
        print(f"Fetched the domain for Cognito: {domain}")
        
        if not domain:
            # Fallback to the old method if no domain is found
            user_pool_id_without_underscore = user_pool_id.replace("_", "").lower()
            print(f"DEBUG: user_pool_id_without_underscore: {user_pool_id_without_underscore}")
            url = f"https://{user_pool_id_without_underscore}.auth.{REGION}.amazoncognito.com/oauth2/token"
        else:
            url = f"https://{domain}.auth.{REGION}.amazoncognito.com/oauth2/token"
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope_string,
        }
        
        print(f"Token endpoint URL: {url}")
        print(f"Client ID: {client_id}")
        print(f"Requested scopes: {scope_string}")
        print("Making token request...")
        
        response = requests.post(url, headers=headers, data=data)
        
        if response.status_code != 200:
            print(f"❌ Token request failed with status {response.status_code}")
            print(f"Response body: {response.text}")
            
            # Provide helpful error messages for common issues
            if response.status_code == 400:
                error_text = response.text.lower()
                if "invalid_client" in error_text:
                    return {"error": "Invalid client credentials. Check client_id and client_secret."}
                elif "invalid_scope" in error_text:
                    return {"error": f"Invalid scope '{scope_string}'. Check if the resource server and scopes exist."}
                elif "unsupported_grant_type" in error_text:
                    return {"error": "Client not configured for client_credentials flow. Check OAuth flow settings."}
                else:
                    return {"error": f"Bad request (400): {response.text}"}
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
        
        response.raise_for_status()
        token_data = response.json()
        print(f"✅ Successfully fetched access token")
        return token_data

    except requests.exceptions.RequestException as err:
        return {"error": str(err)}
    
def create_agentcore_role(agent_name):
    iam_client = boto3.client('iam')
    agentcore_role_name = f'agentcore-{agent_name}-role'
    boto_session = Session()
    region = boto_session.region_name
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BedrockPermissions",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:DescribeLogStreams",
                    "logs:CreateLogGroup"
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:DescribeLogGroups"
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
                ]
            },
            {
            "Effect": "Allow",
            "Action": [
                "xray:PutTraceSegments",
                "xray:PutTelemetryRecords",
                "xray:GetSamplingRules",
                "xray:GetSamplingTargets"
                ],
             "Resource": [ "*" ]
             },
             {
                "Effect": "Allow",
                "Resource": "*",
                "Action": "cloudwatch:PutMetricData",
                "Condition": {
                    "StringEquals": {
                        "cloudwatch:namespace": "bedrock-agentcore"
                    }
                }
            },
             {
                "Effect": "Allow",
                "Resource": "*",
                "Action": "s3:GetObject",
            },
             {
                "Effect": "Allow",
                "Resource": "*",
                "Action": "lambda:InvokeFunction"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:*",
                    "iam:PassRole"
                ],
                "Resource": "*"
            },
            {
                "Sid": "GetAgentAccessToken",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
                ],
                "Resource": [
                  f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default",
                  f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/{agent_name}-*"
                ]
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
    # Check if role already exists before attempting creation
    try:
        # Try to get existing role
        existing_role = iam_client.get_role(RoleName=agentcore_role_name)
        print(f"Role {agentcore_role_name} already exists, using existing role")
        agentcore_iam_role = existing_role['Role']
    except iam_client.exceptions.NoSuchEntityException:
        # Role doesn't exist, create it
        try:
            agentcore_iam_role = iam_client.create_role(
                RoleName=agentcore_role_name,
                AssumeRolePolicyDocument=assume_role_policy_document_json
            )
            print(f"Created new role {agentcore_role_name}")
            # Pause to make sure role is created
            time.sleep(10)
        except iam_client.exceptions.EntityAlreadyExistsException:
            print("Role already exists -- deleting and creating it again")
            policies = iam_client.list_role_policies(
            RoleName=agentcore_role_name,
            MaxItems=100
            )
            print("policies:", policies)
            for policy_name in policies['PolicyNames']:
                iam_client.delete_role_policy(
                    RoleName=agentcore_role_name,
                    PolicyName=policy_name
                )
            print(f"deleting {agentcore_role_name}")
            iam_client.delete_role(
                RoleName=agentcore_role_name
            )
            print(f"recreating {agentcore_role_name}")
            agentcore_iam_role = iam_client.create_role(
                RoleName=agentcore_role_name,
                AssumeRolePolicyDocument=assume_role_policy_document_json
            )

    # Attach the AWSLambdaBasicExecutionRole policy
    print(f"attaching role policy {agentcore_role_name}")
    try:
        iam_client.put_role_policy(
            PolicyDocument=role_policy_document,
            PolicyName="AgentCorePolicy",
            RoleName=agentcore_role_name
        )
    except Exception as e:
        print(e)

    return agentcore_iam_role

def create_agentcore_gateway_role(gateway_name):
    iam_client = boto3.client('iam')
    agentcore_gateway_role_name = f'agentcore-{gateway_name}-role'
    boto_session = Session()
    region = boto_session.region_name
    account_id = boto3.client("sts").get_caller_identity()["Account"]
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
    # Check if role already exists before attempting creation
    try:
        # Try to get existing role
        existing_role = iam_client.get_role(RoleName=agentcore_gateway_role_name)
        print(f"Role {agentcore_gateway_role_name} already exists, using existing role")
        agentcore_iam_role = existing_role['Role']
    except iam_client.exceptions.NoSuchEntityException:
        # Role doesn't exist, create it
        try:
            agentcore_iam_role = iam_client.create_role(
                RoleName=agentcore_gateway_role_name,
                AssumeRolePolicyDocument=assume_role_policy_document_json
            )
            print(f"Created new role {agentcore_gateway_role_name}")
            # Pause to make sure role is created
            time.sleep(10)
        except iam_client.exceptions.EntityAlreadyExistsException:
            print("Role already exists -- deleting and creating it again")
        try:
            policies = iam_client.list_role_policies(
                RoleName=agentcore_gateway_role_name,
                MaxItems=100
            )
        except iam_client.exceptions.NoSuchEntityException:
            print(f"Role {agentcore_gateway_role_name} not found during cleanup")
            policies = {'PolicyNames': []}
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

    # Attach the AWSLambdaBasicExecutionRole policy
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


def create_agentcore_gateway_role_s3_smithy(gateway_name):
    iam_client = boto3.client('iam')
    agentcore_gateway_role_name = f'agentcore-{gateway_name}-role'
    boto_session = Session()
    region = boto_session.region_name
    account_id = boto3.client("sts").get_caller_identity()["Account"]
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
                    "lambda:InvokeFunction",
                    "s3:*",
                    # This is used to track the observability 
                    # component of the gateway
                    "cloudwatch:*",
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
    # Check if role already exists before attempting creation
    try:
        # Try to get existing role
        existing_role = iam_client.get_role(RoleName=agentcore_gateway_role_name)
        print(f"Role {agentcore_gateway_role_name} already exists, using existing role")
        agentcore_iam_role = existing_role
    except iam_client.exceptions.NoSuchEntityException:
        # Role doesn't exist, create it
        try:
            agentcore_iam_role = iam_client.create_role(
                RoleName=agentcore_gateway_role_name,
                AssumeRolePolicyDocument=assume_role_policy_document_json
            )
            print(f"Created new role {agentcore_gateway_role_name}")
            # Pause to make sure role is created
            time.sleep(10)
        except iam_client.exceptions.EntityAlreadyExistsException:
            print("Role already exists -- deleting and creating it again")
            try:
                policies = iam_client.list_role_policies(
                    RoleName=agentcore_gateway_role_name,
                    MaxItems=100
                )
            except iam_client.exceptions.NoSuchEntityException:
                print(f"Role {agentcore_gateway_role_name} not found during cleanup")
                policies = {'PolicyNames': []}
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

    # Attach the AWSLambdaBasicExecutionRole policy
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

def create_gateway_lambda(lambda_function_code_path) -> dict[str, int]:
    boto_session = Session()
    region = boto_session.region_name

    return_resp = {"lambda_function_arn": "Pending", "exit_code": 1}
    
    # Initialize Cognito client
    lambda_client = boto3.client('lambda', region_name=region)
    iam_client = boto3.client('iam', region_name=region)

    role_name = 'gateway_lambda_iamrole'
    role_arn = ''
    lambda_function_name = 'gateway_lambda'

    print("Reading code from zip file")
    with open(lambda_function_code_path, 'rb') as f:
        lambda_function_code = f.read()

    try:
        print("Creating IAM role for lambda function")

        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Service": "lambda.amazonaws.com"
                        },
                        "Action": "sts:AssumeRole"
                    }
                ]
            }),
            Description="IAM role to be assumed by lambda function"
        )

        role_arn = response['Role']['Arn']

        print("Attaching policy to the IAM role")

        response = iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
        )

        print(f"Role '{role_name}' created successfully: {role_arn}")
    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == "EntityAlreadyExists":
            response = iam_client.get_role(RoleName=role_name)
            role_arn = response['Role']['Arn']
            print(f"IAM role {role_name} already exists. Using the same ARN {role_arn}")
        else:
            error_message = error.response['Error']['Code'] + "-" + error.response['Error']['Message']
            print(f"Error creating role: {error_message}")
            return_resp['lambda_function_arn'] = error_message

    if role_arn != "":
        print("Creating lambda function")
        # Create lambda function    
        try:
            lambda_response = lambda_client.create_function(
                FunctionName=lambda_function_name,
                Role=role_arn,
                Runtime='python3.12',
                Handler='lambda_function_code.lambda_handler',
                Code = {'ZipFile': lambda_function_code},
                Description='Lambda function example for Bedrock AgentCore Gateway',
                PackageType='Zip'
            )

            return_resp['lambda_function_arn'] = lambda_response['FunctionArn']
            return_resp['exit_code'] = 0
        except botocore.exceptions.ClientError as error:
            if error.response['Error']['Code'] == "ResourceConflictException":
                response = lambda_client.get_function(FunctionName=lambda_function_name)
                lambda_arn = response['Configuration']['FunctionArn']
                print(f"AWS Lambda function {lambda_function_name} already exists. Using the same ARN {lambda_arn}")
                return_resp['lambda_function_arn'] = lambda_arn
            else:
                error_message = error.response['Error']['Code'] + "-" + error.response['Error']['Message']
                print(f"Error creating lambda function: {error_message}")
                return_resp['lambda_function_arn'] = error_message

    return return_resp

def delete_gateway(gateway_client,gatewayId): 
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
    print("Deleting gateway ", gatewayId)
    gateway_client.delete_gateway(gatewayIdentifier = gatewayId)

def delete_all_gateways(gateway_client):
    try:
        list_response = gateway_client.list_gateways(
            maxResults=100
        )
        for item in list_response['items']:
            gatewayId= item["gatewayId"]
            delete_gateway(gatewayId)
    except Exception as e:
        print(e)

def create_gateway_target(target_type, gateway_id, target_name, target_descr, target_config, oauth_provider_arn, oauth_scopes):
    """
    Creates a gateway target for either Lambda or OpenAPI.
    
    Args:
        gateway_id: The gateway identifier
        target_name: Name for the target
        target_descr: Description for the target
        target_config: Target configuration dict (either Lambda or OpenAPI)
    
    Returns:
        The target ID of the created target
    """
    from constants import REGION_NAME
    # initialize the agentcore gateway client that will be used for 
    # creating a target
    agentcore_client = boto3.client('bedrock-agentcore-control', region_name=REGION_NAME)
    if target_type in ['smithy', 'lambda']:
        CREDENTIAL_INFO = [
                {"credentialProviderType": "GATEWAY_IAM_ROLE"}
            ]
        print(f"Going to use the smithy/lambda type target credential information: {CREDENTIAL_INFO}")
    elif target_type in ['openapi']:
        # Enhanced OpenAPI target support with OAuth2 for GitHub and Jira APIs
        # Check if OAuth2 provider ARN is provided in target_config
        
        if oauth_provider_arn:
            # Use OAuth2 authentication for external APIs like GitHub/Jira
            CREDENTIAL_INFO = [
                {
                    "credentialProviderType": "OAUTH",
                    "credentialProvider": {
                        "oauthCredentialProvider": {
                            "providerArn": oauth_provider_arn,
                            "scopes": oauth_scopes
                        }
                    }
                }
            ]
            print(f"Going to use OAuth2 credential provider for openAPI target: {oauth_provider_arn}")
        else:
            # Use GATEWAY_IAM_ROLE when no OAuth provider is specified
            CREDENTIAL_INFO = [
                {"credentialProviderType": "GATEWAY_IAM_ROLE"}
            ]
            print(f"Going to use GATEWAY_IAM_ROLE for openAPI target without OAuth: {CREDENTIAL_INFO}")
    # Create the agentcore gateway target using the gateway ID, 
    # the target name, target description, the configuration and the credential provider
    # config. For this, we will use the "GATEWAY_IAM_ROLE". This is for those targets that
    # are lambda functions but for openAPI or Smithy models that make API calls outside to
    # third party, we will use the OAuth type
    response = agentcore_client.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name=target_name,
        description=target_descr,
        targetConfiguration=target_config,
        credentialProviderConfigurations=CREDENTIAL_INFO,
    )
    return response["targetId"]

def upload_smithy_to_s3(smithy_file_path, bucket_name, object_key):
    """
    Upload a Smithy JSON file to S3 and return the S3 URI.
    """
    from constants import REGION_NAME
    try:
        s3_client = boto3.client('s3', region_name=REGION_NAME)
        
        # Check if bucket exists, create if it doesn't
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except s3_client.exceptions.NoSuchBucket:
            print(f"Creating S3 bucket: {bucket_name}")
            if REGION_NAME == 'us-east-1':
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': REGION_NAME}
                )
        
        # Upload the file
        print(f"Uploading {smithy_file_path} to s3://{bucket_name}/{object_key}")
        s3_client.upload_file(smithy_file_path, bucket_name, object_key)
        
        s3_uri = f"s3://{bucket_name}/{object_key}"
        print(f"✅ Successfully uploaded file to: {s3_uri}")
        return s3_uri
        
    except Exception as e:
        print(f"❌ Failed to upload file to S3: {e}")
        raise

def create_target_config(target_info):
    """
    Creates target configuration based on target type (Lambda, OpenAPI, or Smithy).
    """
    target_type = target_info.get('type')
    
    if target_type == 'lambda':
        lambda_config = target_info.get('lambda', {})
        lambda_arn = lambda_config.get('arn')
        tools_config_paths = lambda_config.get('tools_config', [])
        
        # Load tools from config files
        tools_list = []
        for config_path in tools_config_paths:
            try:
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                    tools_list.extend(config_data.get('tools', []))
            except Exception as e:
                print(f"Error loading tools config from {config_path}: {e}")
        
        return {
            "mcp": {
                "lambda": {
                    "lambdaArn": lambda_arn,
                    "toolSchema": {"inlinePayload": tools_list},
                }
            }
        }
    
    elif target_type == 'openapi':
        print(f"Target type is OpenAPI, going to create the openAPI s3 schema for this")
        openapi_config = target_info.get('openapi', {})
        s3_uri = openapi_config.get('s3_uri')
        
        return {
            "mcp": {
                "openApiSchema": {
                    "s3": {
                        "uri": s3_uri
                    }
                }
            }
        }
    
    elif target_type == 'smithy':
        smithy_config = target_info.get('smithy', {})
        s3_uri = smithy_config.get('s3_uri')
        
        return {
            "mcp": {
                "smithyModel": {
                    "s3": {
                        "uri": s3_uri
                    }
                }
            }
        }
    
    else:
        raise ValueError(f"Unsupported target type: {target_type}")

def check_existing_target(gateway_id, target_name):
    """
    Check if a target with the given name exists in the gateway.
    
    Args:
        gateway_id: The gateway identifier
        target_name: Name of the target to check
    
    Returns:
        Target info dict if found, None otherwise
    """
    from constants import REGION_NAME
    try:
        agentcore_client = boto3.client('bedrock-agentcore-control', region_name=REGION_NAME)
        list_response = agentcore_client.list_gateway_targets(
            gatewayIdentifier=gateway_id,
            maxResults=100
        )
        
        for target in list_response.get('items', []):
            if target.get('name') == target_name:
                return target
        return None
        
    except Exception as e:
        print(f"Error checking for existing target {target_name}: {e}")
        return None

def create_targets_from_config(gateway_id, gateway_config, bucket_name):
    """
    Loop through targets configuration and create gateway targets based on target_type.
    Checks if target exists before creating new one.
    """
    import glob
    import os
    import time
    created_targets = []
    target_type = gateway_config.get('target_type', 'smithy')
    targets_config = gateway_config.get('targets')
    
    # Check if we should use an existing target
    use_existing_target = gateway_config.get('existing_target', False)
    existing_target_name = gateway_config.get('target_name')
    
    if use_existing_target and existing_target_name:
        print(f"Checking for existing target: {existing_target_name}")
        existing_target = check_existing_target(gateway_id, existing_target_name)
        if existing_target:
            print(f"✅ Using existing target: {existing_target_name} (ID: {existing_target['targetId']})")
            created_targets.append({
                'id': existing_target['targetId'],
                'name': existing_target_name,
                'type': target_type,
                'existing': True
            })
            return created_targets
        else:
            print(f"Target {existing_target_name} not found, will create new one")
    
    if target_type == 'smithy':
        # Handle Smithy targets from directory paths
        smithy_paths = targets_config.get('smithy')
        print(f"Getting the smithy files: {smithy_paths}")
        if smithy_paths:
            print(f"Processing Smithy targets: {smithy_paths}")
            for smithy_file in smithy_paths:
                try:
                    # Convert to absolute path
                    if not os.path.isabs(smithy_file):
                        smithy_file = os.path.abspath(smithy_file)
                    print(f"Found Smithy JSON file: {smithy_file}")
                    # Verify file exists
                    if not os.path.exists(smithy_file):
                        print(f"❌ Smithy file not found: {smithy_file}")
                        continue
                    
                    # Create S3 bucket name and object key
                    file_name = os.path.basename(smithy_file)
                    object_key = f"smithy-specs/{file_name}"
                    
                    # Upload to S3
                    s3_uri = upload_smithy_to_s3(smithy_file, bucket_name, object_key)
                    
                    # Create target configuration
                    # Use existing target name if specified, otherwise use default
                    target_name = existing_target_name if use_existing_target and existing_target_name else "monitor"
                    target_descr = f"Smithy target for monitoring tools from {file_name}"
                    # define the target config for the create target config function
                    target_config = {
                        "mcp": {
                            "smithyModel": {
                                "s3": {
                                    "uri": s3_uri
                                }
                            }
                        }
                    }
                    
                    print(f"Creating Smithy target: {target_name}")
                    target_id = create_gateway_target(target_type, gateway_id, target_name, target_descr, target_config)
                    created_targets.append({
                        'id': target_id,
                        'name': target_name,
                        'type': 'smithy',
                        's3_uri': s3_uri
                    })
                    print(f"✅ Created Smithy target: {target_name} (ID: {target_id})")
                except Exception as e:
                    print(f"❌ Failed to create Smithy target for {smithy_file}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
    elif target_type == 'lambda':
        # Handle Lambda targets from new configuration format
        lambda_configs = targets_config.get('lambda', [])
        print(f"Processing Lambda targets: {lambda_configs}")
        
        for lambda_config in lambda_configs:
            try:
                function_name = lambda_config.get('function_name')
                if not function_name:
                    print("❌ Lambda function_name is required")
                    continue
                
                # Use role_arn if provided, otherwise get from Lambda function
                function_arn = lambda_config.get('role_arn')
                if not function_arn:
                    # Get the Lambda function ARN
                    lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
                    try:
                        function_response = lambda_client.get_function(FunctionName=function_name)
                        function_arn = function_response['Configuration']['FunctionArn']
                        print(f"Found Lambda function ARN: {function_arn}")
                    except Exception as e:
                        print(f"❌ Lambda function {function_name} not found: {e}")
                        continue
                else:
                    print(f"Using provided Lambda function ARN: {function_arn}")
                
                credential_provider = lambda_config.get('credential_provider', 'GATEWAY_IAM_ROLE')
                
                # Load tools from config_struct if provided
                tools = lambda_config.get('tools', [])
                config_struct_path = lambda_config.get('config_struct')
                if config_struct_path:
                    try:
                        # Convert relative path to absolute path from project root
                        if not os.path.isabs(config_struct_path):
                            config_struct_path = os.path.abspath(config_struct_path)
                        
                        print(f"Loading tools from config struct: {config_struct_path}")
                        with open(config_struct_path, 'r') as f:
                            config_data = json.load(f)
                            tools = config_data.get('tools', [])
                            print(f"Loaded {len(tools)} tools from config struct")
                    except Exception as e:
                        print(f"❌ Error loading config struct from {config_struct_path}: {e}")
                        print("Continuing with empty tools list...")
                        tools = []
                
                # Use existing target name if specified, otherwise use default
                target_name = existing_target_name if use_existing_target and existing_target_name else "CloudWatchMonitoringLambda"
                target_descr = f"Lambda target for CloudWatch monitoring tools - {function_name}"
                
                # Create Lambda target configuration using the correct format
                target_config = {
                    "mcp": {
                        "lambda": {
                            "lambdaArn": function_arn,
                            "toolSchema": {
                                "inlinePayload": tools
                            }
                        }
                    }
                }
                
                print(f"Creating Lambda target: {target_name}")
                target_id = create_gateway_target(target_type, gateway_id, target_name, target_descr, target_config)
                created_targets.append({
                    'id': target_id,
                    'name': target_name,
                    'type': 'lambda',
                    'function_arn': function_arn
                })
                print(f"✅ Created Lambda target: {target_name} (ID: {target_id})")
                
            except Exception as e:
                print(f"❌ Failed to create Lambda target for {lambda_config.get('function_name', 'Unknown')}: {e}")
                import traceback
                traceback.print_exc()
                continue
                
    elif target_type == 'openapi':
        # Handle OpenAPI targets with OAuth2 support for GitHub and Jira
        # Check if targets_config is a list (direct config) or dict (nested config)
        if isinstance(targets_config, list):
            openapi_configs = targets_config
        else:
            openapi_configs = targets_config.get('openapi', [])
        
        # Loop through each target configuration
        for target in openapi_configs:
            created_target = create_openapi_oauth_target(
                target=target,
                gateway_id=gateway_id,
                bucket_name=bucket_name
            )
            if created_target:
                created_targets.append(created_target)
    
    return created_targets

def create_openapi_oauth_target(target: Dict, gateway_id: str, bucket_name: str) -> Optional[Dict]:
    """
    Create a single OpenAPI OAuth target from configuration.
    
    Args:
        target: Target configuration dictionary
        gateway_id: Gateway identifier
        bucket_name: S3 bucket name for spec upload
    
    Returns:
        Created target information dict or None if failed
    """
    try:
        target_name = target.get('name', f"OpenAPITarget_{int(time.time())}")
        spec_file = target.get('spec_file')
        api_type = target.get('api_type', 'unknown')
        scopes = target.get('scopes', [])
        
        print(f"🔧 Setting up {target_name} ({api_type.upper()}) OpenAPI OAuth target...")
        
        # Check if spec file exists
        if not spec_file or not os.path.exists(spec_file):
            print(f"⚠️  OpenAPI spec file not found: {spec_file}")
            return None
        
        # Upload OpenAPI spec to S3
        object_key = f"openapi-specs/{api_type}_api_spec.yaml"
        s3_uri = upload_smithy_to_s3(spec_file, bucket_name, object_key)
        
        # Create OAuth2 credential provider based on API type
        provider_arn = None
        try:
            if api_type.lower() == 'github':
                provider_arn = setup_github_oauth2_provider()
            elif api_type.lower() == 'jira':
                provider_arn = setup_jira_oauth2_provider()
            else:
                print(f"❌ Unsupported API type: {api_type}")
                return None
        except ValueError as e:
            print(f"⚠️  Skipping {target_name} - {e}")
            return None
        
        # Create target configuration with OAuth provider ARN
        target_config = {
            "mcp": {
                "openApiSchema": {
                    "s3": {
                        "uri": s3_uri
                    }
                }
            }
        }
        
        # Create the target
        target_id = create_gateway_target(
            target_type='openapi',
            gateway_id=gateway_id,
            target_name=target_name,
            target_descr=f"OpenAPI OAuth target for {api_type.upper()} APIs",
            target_config=target_config,
            oauth_provider_arn=provider_arn,
            oauth_scopes=scopes
        )
        
        created_target = {
            'id': target_id,
            'name': target_name,
            'type': 'openapi_oauth',
            's3_uri': s3_uri,
            'provider_arn': provider_arn,
            'api_type': api_type,
            'spec_file': spec_file
        }
        
        print(f"✅ Created {api_type.upper()} OpenAPI OAuth target: {target_name} (ID: {target_id})")
        return created_target
        
    except Exception as e:
        print(f"❌ Failed to create OpenAPI OAuth target {target.get('name', 'Unknown')}: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_oauth2_credential_provider(provider_name: str, auth_config: Dict) -> str:
    """
    Create an OAuth2 credential provider for external APIs.
    
    Args:
        provider_name: Name for the credential provider
        auth_config: Dictionary containing OAuth2 configuration:
            - client_id: OAuth client ID
            - client_secret: OAuth client secret
            - auth_endpoint: Authorization endpoint URL
            - token_endpoint: Token endpoint URL
            - issuer: Issuer URL/domain
            - response_types: List of response types (default: ["code"])
    
    Returns:
        The credential provider ARN
    """
    from constants import REGION_NAME
    from botocore.config import Config
    
    sdk_config = Config(
        region_name=REGION_NAME,
        retries={"max_attempts": 2, "mode": "standard"},
    )

    acps = boto3.client(
        service_name="bedrock-agentcore-control",
        config=sdk_config,
    )

    provider_config = {
        "customOauth2ProviderConfig": {
            "oauthDiscovery": {
                "authorizationServerMetadata": {
                    "issuer": auth_config.get("issuer"),
                    "authorizationEndpoint": auth_config.get("auth_endpoint"),
                    "tokenEndpoint": auth_config.get("token_endpoint"),
                    "responseTypes": auth_config.get("response_types", ["code"])
                }
            },
            "clientId": auth_config.get("client_id"),
            "clientSecret": auth_config.get("client_secret")
        }
    }

    try:
        response = acps.create_oauth2_credential_provider(
            name=provider_name,
            credentialProviderVendor="CustomOauth2",
            oauth2ProviderConfigInput=provider_config
        )
        
        credential_provider_arn = response['credentialProviderArn']
        print(f"✅ Created OAuth2 credential provider: {provider_name}")
        print(f"Provider ARN: {credential_provider_arn}")
        return credential_provider_arn
        
    except Exception as e:
        print(f"❌ Failed to create OAuth2 credential provider {provider_name}: {e}")
        raise

def setup_github_oauth2_provider() -> str:
    """
    Setup GitHub OAuth2 credential provider using environment variables.
    
    Required environment variables:
    - GITHUB_CLIENT_ID: GitHub OAuth app client ID
    - GITHUB_CLIENT_SECRET: GitHub OAuth app client secret
    
    Returns:
        The GitHub credential provider ARN
    """
    github_client_id = os.environ.get('GITHUB_CLIENT_ID')
    github_client_secret = os.environ.get('GITHUB_CLIENT_SECRET')
    
    if not github_client_id or not github_client_secret:
        raise ValueError("GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET environment variables are required")
    
    auth_config = {
        "client_id": github_client_id,
        "client_secret": github_client_secret,
        "auth_endpoint": "https://github.com/login/oauth/authorize",
        "token_endpoint": "https://github.com/login/oauth/access_token",
        "issuer": "https://github.com",
        "response_types": ["code"]
    }
    
    return create_oauth2_credential_provider("Gthbnew", auth_config)

def setup_jira_oauth2_provider() -> str:
    """
    Setup Jira OAuth2 credential provider using environment variables.
    
    Required environment variables:
    - JIRA_DOMAIN: Your Jira domain (e.g., 'yourcompany.atlassian.net')
    - JIRA_CLIENT_ID: Jira OAuth app client ID  
    - JIRA_CLIENT_SECRET: Jira OAuth app client secret
    
    Returns:
        The Jira credential provider ARN
    """
    jira_domain = os.environ.get('JIRA_DOMAIN')
    jira_client_id = os.environ.get('JIRA_CLIENT_ID')
    jira_client_secret = os.environ.get('JIRA_CLIENT_SECRET')
    
    if not all([jira_domain, jira_client_id, jira_client_secret]):
        raise ValueError("JIRA_DOMAIN, JIRA_CLIENT_ID, and JIRA_CLIENT_SECRET environment variables are required")
    
    # Ensure domain format is correct (without https://)
    if jira_domain.startswith('https://'):
        jira_domain = jira_domain[8:]
    elif jira_domain.startswith('http://'):
        jira_domain = jira_domain[7:]
    
    auth_config = {
        "client_id": jira_client_id,
        "client_secret": jira_client_secret,
        "auth_endpoint": f"https://{jira_domain}/oauth/authorize",
        "token_endpoint": f"https://{jira_domain}/oauth/token",
        "issuer": f"https://{jira_domain}",
        "response_types": ["code"]
    }
    
    return create_oauth2_credential_provider("Jiramcpnew", auth_config)

def create_openapi_targets_with_oauth(gateway_id: str, bucket_name: str) -> List[Dict]:
    """
    Create OpenAPI targets for GitHub and Jira with OAuth2 authentication.
    
    Args:
        gateway_id: Gateway identifier
        bucket_name: S3 bucket for storing OpenAPI specs
    
    Returns:
        List of created target information
    """
    created_targets = []
    
    # Configuration for API providers
    api_configs = {
        "github": {
            "spec_file": "tools/github_api_spec.yaml",
            "target_name": "GitHubAPITarget",
            "scopes": ["repo", "issues", "pull_requests"],
            "setup_provider": setup_github_oauth2_provider
        },
        "jira": {
            "spec_file": "tools/jira_api_spec.yaml", 
            "target_name": "JiraAPITarget",
            "scopes": ["read:jira-work", "write:jira-work"],
            "setup_provider": setup_jira_oauth2_provider
        }
    }
    
    for api_name, config in api_configs.items():
        try:
            print(f"\n🔧 Setting up {api_name.upper()} OpenAPI OAuth target...")
            
            # Check if spec file exists
            if not os.path.exists(config["spec_file"]):
                print(f"⚠️  OpenAPI spec file not found: {config['spec_file']}")
                continue
            
            # Upload OpenAPI spec to S3
            object_key = f"openapi-specs/{api_name}_api_spec.yaml"
            s3_uri = upload_smithy_to_s3(config["spec_file"], bucket_name, object_key)
            
            # Create OAuth2 credential provider
            try:
                provider_arn = config["setup_provider"]()
            except ValueError as e:
                print(f"⚠️  Skipping {api_name.upper()} - {e}")
                continue
            
            # Create target configuration with OAuth provider ARN
            target_config = {
                "mcp": {
                    "openApiSchema": {
                        "s3": {
                            "uri": s3_uri
                        }
                    }
                }
            }
            
            # Create the target
            target_id = create_gateway_target(
                target_type='openapi',
                gateway_id=gateway_id,
                target_name=config["target_name"],
                target_descr=f"OpenAPI OAuth target for {api_name.upper()} APIs",
                target_config=target_config
            )
            
            created_targets.append({
                'id': target_id,
                'name': config["target_name"],
                'type': 'openapi_oauth',
                's3_uri': s3_uri,
                'provider_arn': provider_arn,
                'api': api_name
            })
            
            print(f"✅ Created {api_name.upper()} OpenAPI OAuth target: {config['target_name']} (ID: {target_id})")
            
        except Exception as e:
            print(f"❌ Failed to create {api_name.upper()} OAuth target: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    return created_targets

def create_cognito_domain(
    user_pool_id: str, 
    domain_name: Optional[str] = None,
    region: Optional[str] = None
) -> Dict[str, str]:
    """
    Create a domain for the Cognito User Pool.
    
    Args:
        user_pool_id: The Cognito User Pool ID
        domain_name: Optional custom domain name. If not provided, creates one from pool ID
        region: AWS region. If not provided, uses current session region
        
    Returns:
        Dictionary containing domain information with 'domain' and 'domain_url' keys
        
    Raises:
        Exception: If domain creation fails
    """
    if region is None:
        boto_session = Session()
        region = boto_session.region_name
    
    cognito_client = boto3.client('cognito-idp', region_name=region)
    
    try:
        # Check if domain already exists for this user pool
        try:
            response = cognito_client.describe_user_pool(UserPoolId=user_pool_id)
            user_pool = response.get('UserPool', {})
            existing_domain = user_pool.get('Domain')
            
            if existing_domain:
                domain_url = f"https://{existing_domain}.auth.{region}.amazoncognito.com"
                logger.info(f"Domain already exists for user pool {user_pool_id}: {existing_domain}")
                return {
                    'domain': existing_domain,
                    'domain_url': domain_url,
                    'status': 'existing'
                }
        except Exception as e:
            logger.error(f"Error checking existing domain: {e}")
        
        # Generate domain name if not provided
        if domain_name is None:
            # Create domain name from pool ID - remove first underscore and convert to lowercase
            if '_' in user_pool_id:
                domain_name = user_pool_id.replace('_', '', 1).lower()
            else:
                domain_name = user_pool_id.lower()
        
        # Ensure domain name is valid (alphanumeric and hyphens only, lowercase)
        domain_name = domain_name.lower().replace('_', '-')
        
        logger.info(f"Creating Cognito domain: {domain_name} for pool: {user_pool_id}")
        
        # Create the domain
        response = cognito_client.create_user_pool_domain(
            Domain=domain_name,
            UserPoolId=user_pool_id
        )
        
        domain_url = f"https://{domain_name}.auth.{region}.amazoncognito.com"
        
        logger.info(f"Successfully created domain: {domain_name}")
        logger.info(f"Domain URL: {domain_url}")
        
        return {
            'domain': domain_name,
            'domain_url': domain_url,
            'status': 'created',
            'cloudfront_domain': response.get('CloudFrontDomain', '')
        }
        
    except cognito_client.exceptions.InvalidParameterException as e:
        if 'Domain already associated' in str(e):
            # Domain might be associated with another pool
            logger.warning(f"Domain {domain_name} already in use: {e}")
            # Try with a timestamp suffix
            import time
            timestamp_suffix = str(int(time.time()))[-6:]
            new_domain_name = f"{domain_name}-{timestamp_suffix}"
            
            logger.info(f"Trying with timestamped domain: {new_domain_name}")
            response = cognito_client.create_user_pool_domain(
                Domain=new_domain_name,
                UserPoolId=user_pool_id
            )
            
            domain_url = f"https://{new_domain_name}.auth.{region}.amazoncognito.com"
            
            return {
                'domain': new_domain_name,
                'domain_url': domain_url,
                'status': 'created_with_suffix',
                'cloudfront_domain': response.get('CloudFrontDomain', '')
            }
        else:
            logger.error(f"Invalid parameter for domain creation: {e}")
            raise
            
    except Exception as e:
        logger.error(f"Error creating Cognito domain: {e}")
        raise