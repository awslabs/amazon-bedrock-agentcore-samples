import boto3


def setup_cognito_user_pool(region):
    """Create a Cognito user pool with a test user and return config."""
    cognito_client = boto3.client("cognito-idp", region_name=region)
    try:
        pool = cognito_client.create_user_pool(
            PoolName="AgentCorePool",
            Policies={"PasswordPolicy": {"MinimumLength": 8}},
        )
        pool_id = pool["UserPool"]["Id"]

        client = cognito_client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName="AgentCorePoolClient",
            GenerateSecret=False,
            ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
        )
        client_id = client["UserPoolClient"]["ClientId"]

        cognito_client.admin_create_user(
            UserPoolId=pool_id,
            Username="testuser1",
            TemporaryPassword="Temp123!",
            MessageAction="SUPPRESS",
        )
        cognito_client.admin_set_user_password(
            UserPoolId=pool_id,
            Username="testuser1",
            Password="MyPassword123!",
            Permanent=True,
        )

        auth = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": "testuser1", "PASSWORD": "MyPassword123!"},
        )
        bearer_token = auth["AuthenticationResult"]["AccessToken"]

        discovery_url = (
            f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
            "/.well-known/openid-configuration"
        )
        print(f"Pool ID: {pool_id}")
        print(f"Client ID: {client_id}")
        print(f"Discovery URL: {discovery_url}")
        print(f"Bearer Token: {bearer_token}")

        return {
            "pool_id": pool_id,
            "client_id": client_id,
            "bearer_token": bearer_token,
            "discovery_url": discovery_url,
        }
    except Exception as e:
        print(f"Error setting up Cognito user pool: {e}")
        return None


def reauthenticate_user(client_id, region=None, username="testuser1", password="MyPassword123!"):
    """Reauthenticate a single Cognito user and return their access token."""
    if region is None:
        region = boto3.session.Session().region_name
    cognito_client = boto3.client("cognito-idp", region_name=region)
    try:
        auth = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )
        token = auth["AuthenticationResult"]["AccessToken"]
        print(f"Successfully reauthenticated {username}")
        return token
    except Exception as e:
        print(f"Error reauthenticating {username}: {e}")
        return None
