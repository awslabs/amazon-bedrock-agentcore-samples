import boto3
import json
import yaml
import os
from typing import Dict, Any


def _get_boto3_client(service_name: str):
    """Get boto3 client with region from environment or default session."""
    region = os.getenv("AWS_REGION") or boto3.session.Session().region_name
    if not region:
        raise ValueError("AWS_REGION must be set either as environment variable or in AWS config")
    return boto3.client(service_name, region_name=region)


def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    ssm = _get_boto3_client("ssm")

    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)

    return response["Parameter"]["Value"]


def put_ssm_parameter(
    name: str, value: str, parameter_type: str = "String", with_encryption: bool = False
) -> None:
    ssm = _get_boto3_client("ssm")

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
    ssm = _get_boto3_client("ssm")
    try:
        ssm.delete_parameter(Name=name)
    except ssm.exceptions.ParameterNotFound:
        pass


def load_api_spec(file_path: str) -> list:
    with open(file_path, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected a list in the JSON file")
    return data


def get_aws_region() -> str:
    region = os.getenv("AWS_REGION") or boto3.session.Session().region_name
    if not region:
        raise ValueError("AWS_REGION must be set either as environment variable or in AWS config")
    return region


def get_aws_account_id() -> str:
    sts = _get_boto3_client("sts")
    return sts.get_caller_identity()["Account"]


def get_cognito_client_secret() -> str:
    client = _get_boto3_client("cognito-idp")
    response = client.describe_user_pool_client(
        UserPoolId=get_ssm_parameter("/app/customersupport/agentcore/userpool_id"),
        ClientId=get_ssm_parameter("/app/customersupport/agentcore/machine_client_id"),
    )
    return response["UserPoolClient"]["ClientSecret"]


def read_config(file_path: str) -> Dict[str, Any]:
    """
    Read configuration from a file path. Supports JSON, YAML, and YML formats.

    Args:
        file_path (str): Path to the configuration file

    Returns:
        Dict[str, Any]: Configuration data as a dictionary

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file format is not supported or invalid
        yaml.YAMLError: If YAML parsing fails
        json.JSONDecodeError: If JSON parsing fails
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    # Get file extension to determine format
    _, ext = os.path.splitext(file_path.lower())

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            if ext == ".json":
                return json.load(file)
            elif ext in [".yaml", ".yml"]:
                return yaml.safe_load(file)
            else:
                # Try to auto-detect format by attempting JSON first, then YAML
                content = file.read()
                file.seek(0)

                # Try JSON first
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # Try YAML
                    try:
                        return yaml.safe_load(content)
                    except yaml.YAMLError:
                        raise ValueError(
                            f"Unsupported configuration file format: {ext}. "
                            f"Supported formats: .json, .yaml, .yml"
                        )

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file {file_path}: {e}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file {file_path}: {e}")
    except Exception as e:
        raise ValueError(f"Error reading configuration file {file_path}: {e}")
