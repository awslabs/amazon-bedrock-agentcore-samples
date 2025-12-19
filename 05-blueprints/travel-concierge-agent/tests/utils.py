#!/usr/bin/env python3
"""
Shared utilities for test scripts.

Provides common functions for:
- Configuration loading (deployment-config.json, amplify_outputs.json)
- AWS resource discovery (CloudFormation exports, SSM parameters)
- OAuth authentication (Cognito client credentials flow)
- Formatted console output
"""

import json
import base64
import uuid
from pathlib import Path
from typing import Dict, Tuple
import boto3
from colorama import Fore, Style, init

init(autoreset=True)

REGION = "us-east-1"


def print_msg(message: str, level: str = "info") -> None:
    """
    Print formatted message with color.

    Args:
        message: Message to print
        level: 'success' (green), 'error' (red), 'info' (yellow)
    """
    if level == "success":
        print(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")
    elif level == "error":
        print(f"{Fore.RED}✗ {message}{Style.RESET_ALL}")
    elif level == "info":
        print(f"{Fore.YELLOW}ℹ {message}{Style.RESET_ALL}")
    else:
        print(message)


def print_section(title: str, width: int = 60) -> None:
    """Print section header."""
    print("\n" + "=" * width)
    print(title)
    print("=" * width)


def get_deployment_config() -> Dict:
    """
    Load deployment configuration from deployment-config.json.

    Returns:
        Dict with deploymentId and other config values
    """
    config_path = Path(__file__).parent.parent / "deployment-config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {"deploymentId": "default"}


def get_amplify_config() -> Dict:
    """
    Load Amplify configuration from amplify_outputs.json.

    Returns:
        Dict with auth config (user_pool_id, client_id, etc.)
    """
    amplify_path = Path(__file__).parent.parent / "amplify_outputs.json"
    if amplify_path.exists():
        with open(amplify_path) as f:
            return json.load(f)
    raise FileNotFoundError(
        "amplify_outputs.json not found. Run 'npm run deploy:amplify' first."
    )


def get_stack_exports(prefix: str = None) -> Dict[str, str]:
    """
    Get CloudFormation exports with given prefix.

    Args:
        prefix: Export name prefix to filter by. If None, uses AgentStack-{deploymentId}-

    Returns:
        Dict mapping export key (without prefix) to value
    """
    cfn = boto3.client("cloudformation", region_name=REGION)
    exports = cfn.list_exports()

    # Use deployment ID in prefix if not specified
    if prefix is None:
        deployment_config = get_deployment_config()
        deployment_id = deployment_config.get("deploymentId", "default")
        prefix = f"AgentStack-{deployment_id}-"

    result = {}
    for export in exports.get("Exports", []):
        name = export["Name"]
        if name.startswith(prefix):
            key = name.replace(prefix, "")
            result[key] = export["Value"]

    return result


def get_cognito_domain(user_pool_id: str) -> str:
    """Get Cognito user pool domain."""
    cognito = boto3.client("cognito-idp", region_name=REGION)
    response = cognito.describe_user_pool(UserPoolId=user_pool_id)
    return response["UserPool"]["Domain"]


def get_client_secret(user_pool_id: str, client_id: str) -> str:
    """Get Cognito client secret."""
    cognito = boto3.client("cognito-idp", region_name=REGION)
    response = cognito.describe_user_pool_client(
        UserPoolId=user_pool_id, ClientId=client_id
    )
    return response["UserPoolClient"]["ClientSecret"]


def get_oauth_token(scope: str = "concierge-gateway/invoke") -> Tuple[str, Dict]:
    """
    Get OAuth token using machine client credentials flow.

    Args:
        scope: OAuth scope to request

    Returns:
        Tuple of (access_token, config_dict)
    """
    import requests

    # Load configs
    deployment_config = get_deployment_config()
    deployment_id = deployment_config["deploymentId"]
    amplify_config = get_amplify_config()
    user_pool_id = amplify_config["auth"]["user_pool_id"]

    # Get machine client ID from exports
    cfn = boto3.client("cloudformation", region_name=REGION)
    exports = cfn.list_exports()

    client_id = None
    for export in exports.get("Exports", []):
        if f"ConciergeAgent-{deployment_id}-Auth-MachineClientId" in export["Name"]:
            client_id = export["Value"]
            break

    if not client_id:
        raise ValueError("Could not find MachineClientId in CloudFormation exports")

    # Get client secret and domain
    client_secret = get_client_secret(user_pool_id, client_id)
    domain = get_cognito_domain(user_pool_id)

    # Request token
    token_url = f"https://{domain}.auth.{REGION}.amazoncognito.com/oauth2/token"
    auth_string = f"{client_id}:{client_secret}"
    auth_b64 = base64.b64encode(auth_string.encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_b64}",
    }
    data = {"grant_type": "client_credentials", "scope": scope}

    response = requests.post(token_url, headers=headers, data=data, timeout=30)
    if response.status_code != 200:
        raise Exception(f"Failed to get OAuth token: {response.text}")

    config = {
        "deployment_id": deployment_id,
        "user_pool_id": user_pool_id,
        "client_id": client_id,
        "domain": domain,
    }

    return response.json()["access_token"], config


def get_agent_config() -> Dict:
    """
    Get full agent configuration for testing.

    Returns:
        Dict with runtime_arn, access_token, deployment_id, etc.
    """
    access_token, config = get_oauth_token()
    exports = get_stack_exports()

    return {
        "runtime_arn": exports.get("MainRuntimeArn"),
        "runtime_id": exports.get("MainRuntimeId"),
        "gateway_url": exports.get("GatewayUrl"),
        "gateway_id": exports.get("GatewayId"),
        "memory_id": exports.get("MemoryId"),
        "access_token": access_token,
        **config,
    }


def generate_session_id() -> str:
    """Generate UUID4 session ID."""
    return str(uuid.uuid4())


def process_streaming_response(response, verbose: bool = True) -> str:
    """
    Process streaming response and print events.

    Args:
        response: requests.Response object with streaming enabled
        verbose: Whether to print each event

    Returns:
        Accumulated text content
    """
    event_num = 0
    text_content = ""

    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue

        event_num += 1

        # Strip SSE prefix
        raw_line = line[6:] if line.startswith("data: ") else line

        if verbose:
            # Truncate long lines
            display = raw_line[:200] + "..." if len(raw_line) > 200 else raw_line
            print(f"{Fore.CYAN}[{event_num:3d}]{Style.RESET_ALL} {display}", flush=True)

        # Try to extract text content
        try:
            import json

            data = json.loads(raw_line)
            if isinstance(data, dict):
                if "data" in data and isinstance(data["data"], str):
                    text_content += data["data"]
                elif "event" in data and isinstance(data.get("event"), dict):
                    delta_text = (
                        data.get("event", {})
                        .get("contentBlockDelta", {})
                        .get("delta", {})
                        .get("text", "")
                    )
                    if delta_text:
                        text_content += delta_text
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

    if verbose:
        print(f"\n{Fore.GREEN}Total events: {event_num}{Style.RESET_ALL}")

    return text_content
