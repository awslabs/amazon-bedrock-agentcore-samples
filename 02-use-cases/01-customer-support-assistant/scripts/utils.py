import boto3
import json

import yaml


def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    ssm = boto3.client("ssm")

    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)

    return response["Parameter"]["Value"]


def load_api_spec(file_path: str) -> list:
    with open(file_path, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected a list in the JSON file")
    return data


def get_aws_region() -> str:
    session = boto3.session.Session()
    return session.region_name


def get_aws_account_id() -> str:
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Account"]


class Gateway:
    pass


def save_config(gateway: Gateway, filepath: str):
    # Extract relevant data as a dict
    config_data = {
        "gateway": {
            "id": gateway["id"],
            "name": gateway["name"],
            "gateway_url": gateway["gateway_url"],
            "gateway_arn": gateway["gateway_arn"],
        },
        "cognito": {"secret": get_cognito_client_secret()},
    }
    # Write YAML file
    with open(filepath, "w") as f:
        yaml.dump(config_data, f, sort_keys=False)


def get_cognito_client_secret() -> str:
    client = boto3.client("cognito-idp")
    response = client.describe_user_pool_client(
        UserPoolId=get_ssm_parameter("/app/customersupport/agentcore/userpool_id"),
        ClientId=get_ssm_parameter("/app/customersupport/agentcore/machine_client_id"),
    )
    return response["UserPoolClient"]["ClientSecret"]


def read_config(file_path: str) -> dict:
    with open(file_path, "r") as f:
        config = yaml.safe_load(f)
    return config
