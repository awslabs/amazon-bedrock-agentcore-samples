"""
Shared AWS utilities for deployment scripts.
"""

import json
import logging
from typing import Any, Optional

import boto3
import yaml
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def get_aws_region() -> str:
    session = boto3.session.Session()
    return session.region_name or "us-east-1"


def get_aws_account_id() -> str:
    return boto3.client("sts").get_caller_identity()["Account"]


def get_ssm_parameter(name: str, decrypt: bool = True) -> Optional[str]:
    try:
        resp = boto3.client("ssm").get_parameter(Name=name, WithDecryption=decrypt)
        return resp["Parameter"]["Value"]
    except ClientError:
        return None


def put_ssm_parameter(name: str, value: str, secure: bool = False) -> None:
    boto3.client("ssm").put_parameter(
        Name=name,
        Value=value,
        Type="SecureString" if secure else "String",
        Overwrite=True,
    )
    logger.info(f"SSM parameter set: {name}")


def delete_ssm_parameter(name: str) -> None:
    try:
        boto3.client("ssm").delete_parameter(Name=name)
    except ClientError:
        pass


def read_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        if path.endswith((".yaml", ".yml")):
            return yaml.safe_load(f)
        return json.load(f)


def get_cognito_client_secret(user_pool_id: str, client_id: str) -> str:
    resp = boto3.client("cognito-idp").describe_user_pool_client(
        UserPoolId=user_pool_id, ClientId=client_id
    )
    return resp["UserPoolClient"]["ClientSecret"]
