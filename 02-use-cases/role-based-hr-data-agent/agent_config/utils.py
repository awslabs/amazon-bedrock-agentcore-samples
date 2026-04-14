"""
Utility helpers for agent_config.
"""

import json
import logging
from typing import Any, Optional

import boto3
import yaml
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def get_ssm_parameter(name: str, decrypt: bool = True) -> Optional[str]:
    """Retrieve a parameter from AWS Systems Manager Parameter Store."""
    try:
        client = boto3.client("ssm")
        response = client.get_parameter(Name=name, WithDecryption=decrypt)
        return response["Parameter"]["Value"]
    except ClientError as e:
        logger.warning("AWS Systems Manager parameter not found: %s — %s", name, e.response["Error"]["Code"])
        return None


def read_config(path: str) -> dict:
    """Read a JSON or YAML config file and return as dict."""
    with open(path, "r", encoding="utf-8") as f:
        if path.endswith(".yaml") or path.endswith(".yml"):
            return yaml.safe_load(f)
        return json.load(f)
