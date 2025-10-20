import sys
import json
import requests
from uuid import uuid4
from urllib.parse import quote
from typing import Optional, Dict
from pathlib import Path

# Import utils from monitoring_agent
sys.path.insert(0, str(Path(__file__).parent / "monitoring_agent"))
from utils import get_access_token, load_config


def get_bearer_token_from_config(
    config_path: Optional[str] = None
) -> Optional[str]:
    """
    Get bearer token using IDP configuration from config.yaml.

    Args:
        config_path: Path to the config.yaml file

    Returns:
        Bearer token string or None if failed
    """
    if not config_path:
        # get the current config file path
        config_path = input("Enter the relative path to the config.yaml file: ")
        if not config_path:
            print("❌ Config path is required")
            return None

    # Load config
    config_data = load_config(config_path)
    if not config_data:
        print(f"❌ Failed to load {config_path}")
        return None

    # Get IDP setup from config
    idp_setup = config_data.get('idp_setup', {})
    user_pool_id = idp_setup.get('user_pool_id')
    client_id = idp_setup.get('client_id')
    client_secret = idp_setup.get('client_secret')
    discovery_url = idp_setup.get('discovery_url')
    domain = idp_setup.get('domain')
    resource_server_identifier = idp_setup.get('resource_server_identifier')
    scopes = idp_setup.get('scopes', [])

    if not all([user_pool_id, client_id, client_secret]):
        print("❌ Missing IDP configuration in config.yaml")
        return None

    if not resource_server_identifier:
        print("❌ Missing resource_server_identifier in config.yaml")
        return None

    if not scopes:
        print("❌ Missing scopes in config.yaml")
        return None

    # Build scope string from config
    scope_string = " ".join([f"{resource_server_identifier}/{scope}" for scope in scopes])
    print(f"📋 Using scopes: {scope_string}")

    print("🔐 Getting OAuth token...")

    # Get token
    token_response = get_access_token(
        user_pool_id=user_pool_id,
        client_id=client_id,
        client_secret=client_secret,
        scope_string=scope_string,
        discovery_url=discovery_url,
        domain=domain,
    )

    if "error" in token_response:
        print(f"❌ Token request failed: {token_response['error']}")
        return None

    if "access_token" not in token_response:
        print(f"❌ No access_token in response: {token_response}")
        return None

    access_token = token_response["access_token"]
    print(f"✅ Successfully obtained access token")

    return access_token


def fetch_agent_card(
    agent_arn: Optional[str] = None,
    bearer_token: Optional[str] = None,
    config_path: Optional[str] = None,
    region: str = "us-west-2"
) -> Optional[Dict]:
    """
    Fetch agent card from Amazon Bedrock AgentCore.

    Args:
        agent_arn: The agent ARN. If not provided, will prompt for input.
        bearer_token: OAuth bearer token. If not provided, will get from config.
        config_path: Path to config.yaml file. If not provided, will prompt for input.
        region: AWS region (default: us-west-2)

    Returns:
        Agent card dictionary or None if failed
    """
    # Get agent ARN from user input if not provided
    if not agent_arn:
        agent_arn = input("Enter the Agent ARN: ").strip()
        if not agent_arn:
            print("❌ Agent ARN is required")
            return None

    # Get bearer token from config if not provided
    if not bearer_token:
        bearer_token = get_bearer_token_from_config(config_path)
        if not bearer_token:
            return None

    # URL encode the agent ARN
    escaped_agent_arn = quote(agent_arn, safe='')

    # Construct the URL based on the agent ARN and region
    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations/.well-known/agent-card.json"

    # Generate a unique session ID
    session_id = str(uuid4())
    print(f"Generated session ID: {session_id}")

    # Set headers
    headers = {
        'Accept': '*/*',
        'Authorization': f'Bearer {bearer_token}',
        'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': session_id
    }

    print(f"🚀 Fetching agent card from: {url}")

    try:
        # Make the request
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # Parse and pretty print JSON
        agent_card = response.json()
        print("\n" + "="*50)
        print("AGENT CARD:")
        print("="*50)
        print(json.dumps(agent_card, indent=2))

        return agent_card

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching agent card: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return None


if __name__ == "__main__":
    fetch_agent_card()