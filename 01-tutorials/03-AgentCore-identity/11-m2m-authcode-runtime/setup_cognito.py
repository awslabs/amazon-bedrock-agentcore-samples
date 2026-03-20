"""
Setup script: Creates a Cognito User Pool for AgentCore Runtime inbound JWT auth.
Used by both M2M and Auth Code (3LO) flow samples.

Usage:
    python setup_cognito.py

Outputs:
    cognito_config.json
"""

import boto3
import json
from boto3.session import Session

POOL_NAME = "M2MAuthCodeDemoPool"
USERNAME = "testuser"
PASSWORD = "AgentCoreTest1!"
TEMP_PASSWORD = "TempPass123!"


def setup_cognito():
    session = Session()
    region = session.region_name
    cognito = boto3.client("cognito-idp", region_name=region)

    print("Creating Cognito User Pool...")
    pool = cognito.create_user_pool(
        PoolName=POOL_NAME,
        Policies={"PasswordPolicy": {"MinimumLength": 8}},
    )
    pool_id = pool["UserPool"]["Id"]
    print(f"  Pool ID: {pool_id}")

    print("Creating App Client (for user login / inbound auth)...")
    user_client = cognito.create_user_pool_client(
        UserPoolId=pool_id,
        ClientName=f"{POOL_NAME}UserClient",
        GenerateSecret=False,
        ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
    )
    user_client_id = user_client["UserPoolClient"]["ClientId"]
    print(f"  User Client ID: {user_client_id}")

    print(f"Creating test user '{USERNAME}'...")
    cognito.admin_create_user(
        UserPoolId=pool_id,
        Username=USERNAME,
        TemporaryPassword=TEMP_PASSWORD,
        MessageAction="SUPPRESS",
    )
    cognito.admin_set_user_password(
        UserPoolId=pool_id,
        Username=USERNAME,
        Password=PASSWORD,
        Permanent=True,
    )

    print("Verifying authentication...")
    cognito.initiate_auth(
        ClientId=user_client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": USERNAME, "PASSWORD": PASSWORD},
    )

    discovery_url = (
        f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
        "/.well-known/openid-configuration"
    )

    config = {
        "pool_id": pool_id,
        "client_id": user_client_id,
        "discovery_url": discovery_url,
        "region": region,
        "username": USERNAME,
        "password": PASSWORD,
    }

    with open("cognito_config.json", "w") as f:
        json.dump(config, f, indent=2)

    print("\nCognito setup complete!")
    print(f"\nValues for agentcore.json (runtime inbound auth):")
    print(f"  discoveryUrl : {discovery_url}")
    print(f"  allowedClients: [\"{user_client_id}\"]")
    print(f"\nConfiguration saved to cognito_config.json")

    return config


if __name__ == "__main__":
    setup_cognito()
