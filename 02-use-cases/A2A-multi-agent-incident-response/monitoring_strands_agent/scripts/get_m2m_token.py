"""
Script to get M2M token for monitoring agent using bedrock_agentcore.identity.auth
"""

import sys
from urllib.parse import quote
from bedrock_agentcore.identity.auth import requires_access_token
from utils import get_ssm_parameter, get_aws_info


def get_token(provider_name: str) -> str:
    """
    Get M2M bearer token for the specified provider.

    Args:
        provider_name: The provider name for authentication

    Returns:
        str: Bearer token
    """

    @requires_access_token(
        provider_name=provider_name,
        scopes=[],
        auth_flow="M2M",
        into="bearer_token",
        force_authentication=True,
    )
    def _get_token_with_auth(bearer_token: str = str()) -> str:
        return bearer_token

    return _get_token_with_auth()


def main():
    try:
        # Get provider name from SSM
        provider_name = get_ssm_parameter("/monitoragent/agentcore/provider-name")

        # Get agent runtime ID from SSM
        agent_id = get_ssm_parameter("/monitoragent/agentcore/runtime-id")

        # Get AWS info
        account_id, region = get_aws_info()

        # Construct agent ARN
        agent_arn = (
            f"arn:aws:bedrock-agentcore:{region}:{account_id}:runtime/{agent_id}"
        )

        # Construct agent card URL
        escaped_agent_arn = quote(agent_arn, safe="")
        agent_card_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations/.well-known/agent-card.json"

        # Get token
        token = get_token(provider_name)

        # Print bearer token and agent card URL
        print(f"Bearer Token: {token}")
        print(f"Agent Card URL: {agent_card_url}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
