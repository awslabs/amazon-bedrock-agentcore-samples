#!/usr/bin/env python3
"""
AgentCore Gateway and Runtime Setup Toolkit
Configurable setup script for creating AgentCore runtime and gateway using YAML configuration.
"""

import os
import boto3
import logging
from bedrock_agentcore_starter_toolkit import Runtime
from . import utils


class AgentCoreToolkit:
    def __init__(self, config=None):
        self.config = config
        self.region = os.environ.get("AWS_DEFAULT_REGION", self.config["aws"]["region"])
        self._setup_logging()

    def _derive_gateway_names(self, gateway_name):
        """Derive all gateway-related names from the gateway name"""
        return {
            "iam_role_name": f"{gateway_name}-role",
            "user_pool_name": f"{gateway_name}-pool",
            "resource_server_id": f"{gateway_name}-id",
            "resource_server_name": f"{gateway_name}-name",
            "client_name": f"{gateway_name}-client",
        }

    def _derive_runtime_names(self, runtime_name):
        """Derive all runtime-related names from the runtime name"""
        return {
            "user_pool_name": f"{runtime_name}-pool",
            "resource_server_id": f"{runtime_name}-id",
            "resource_server_name": f"{runtime_name}-name",
            "client_name": f"{runtime_name}-client",
            "agent_name": runtime_name.replace("-", "_"),
        }

    def _derive_target_names(self, runtime_name):
        """Derive target-related names from the runtime name"""
        return {
            "name": f"{runtime_name}-target",
            "identity_provider_name": f"{runtime_name}-identity",
        }

    def _setup_logging(self):
        """Configure logging"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            handlers=[logging.StreamHandler()],
        )
        logging.getLogger("strands").setLevel(logging.INFO)

    def _check_required_files(self, runtime_config):
        """Check if required files exist for a runtime"""
        required_files = [
            runtime_config["entrypoint"],
            runtime_config["requirements_file"],
        ]
        for file in required_files:
            if not os.path.exists(file):
                raise FileNotFoundError(f"Required file {file} not found")
        print(f"Required files found for {runtime_config['name']} ✓")

    def setup_gateway_cognito(self):
        """Setup Cognito resources for gateway"""
        print("Setting up Gateway Cognito resources...")

        cognito = boto3.client("cognito-idp", region_name=self.region)
        gw_config = self.config["gateway"]

        # Derive names from gateway name
        derived_names = self._derive_gateway_names(gw_config["name"])

        # Create user pool
        gw_user_pool_id = utils.get_or_create_user_pool(
            self.region, cognito, derived_names["user_pool_name"]
        )
        print(f"Gateway User Pool ID: {gw_user_pool_id}")

        # Create resource server
        scopes = [
            {"ScopeName": scope["name"], "ScopeDescription": scope["description"]}
            for scope in self.config["scopes"]
        ]
        utils.get_or_create_resource_server(
            cognito,
            gw_user_pool_id,
            derived_names["resource_server_id"],
            derived_names["resource_server_name"],
            scopes,
        )

        # Create client
        scope_names = [
            f"{derived_names['resource_server_id']}/{scope['name']}"
            for scope in self.config["scopes"]
        ]
        gw_client_id, gw_client_secret = utils.get_or_create_m2m_client(
            cognito,
            gw_user_pool_id,
            derived_names["client_name"],
            derived_names["resource_server_id"],
            scope_names,
        )

        gw_discovery_url = f"https://cognito-idp.{self.region}.amazonaws.com/{gw_user_pool_id}/.well-known/openid-configuration"

        return {
            "user_pool_id": gw_user_pool_id,
            "client_id": gw_client_id,
            "client_secret": gw_client_secret,
            "discovery_url": gw_discovery_url,
            "scope_string": " ".join(scope_names),
            "resource_server_id": derived_names["resource_server_id"],
        }

    def setup_runtime_cognito(self, runtime_config):
        """Setup Cognito resources for a single runtime"""
        print(f"Setting up Runtime Cognito resources for {runtime_config['name']}...")

        cognito = boto3.client("cognito-idp", region_name=self.region)

        # Derive names from runtime name
        derived_names = self._derive_runtime_names(runtime_config["name"])

        # Create user pool
        rt_user_pool_id = utils.get_or_create_user_pool(
            self.region, cognito, derived_names["user_pool_name"]
        )
        print(f"Runtime User Pool ID: {rt_user_pool_id}")

        # Create resource server
        scopes = [
            {"ScopeName": scope["name"], "ScopeDescription": scope["description"]}
            for scope in self.config["scopes"]
        ]
        utils.get_or_create_resource_server(
            cognito,
            rt_user_pool_id,
            derived_names["resource_server_id"],
            derived_names["resource_server_name"],
            scopes,
        )

        # Create client
        scope_names = [
            f"{derived_names['resource_server_id']}/{scope['name']}"
            for scope in self.config["scopes"]
        ]
        rt_client_id, rt_client_secret = utils.get_or_create_m2m_client(
            cognito,
            rt_user_pool_id,
            derived_names["client_name"],
            derived_names["resource_server_id"],
            scope_names,
        )

        rt_discovery_url = f"https://cognito-idp.{self.region}.amazonaws.com/{rt_user_pool_id}/.well-known/openid-configuration"

        return {
            "user_pool_id": rt_user_pool_id,
            "client_id": rt_client_id,
            "client_secret": rt_client_secret,
            "discovery_url": rt_discovery_url,
            "scope_string": " ".join(scope_names),
        }

    def create_gateway(self, gateway_cognito):
        """Create AgentCore Gateway"""
        print("Creating AgentCore Gateway...")

        gw_config = self.config["gateway"]
        derived_names = self._derive_gateway_names(gw_config["name"])

        # Create IAM role
        iam_role = utils.create_agentcore_gateway_role(derived_names["iam_role_name"])
        print(f"Gateway IAM Role ARN: {iam_role['Role']['Arn']}")

        auth_config = {
            "customJWTAuthorizer": {
                "allowedClients": [gateway_cognito["client_id"]],
                "discoveryUrl": gateway_cognito["discovery_url"],
            }
        }

        gw_info = utils.get_or_create_agentcore_gateway(
            self.region, iam_role, auth_config, gw_config
        )
        return gw_info

    def setup_runtime(self, runtime_config, runtime_cognito):
        """Setup and launch AgentCore Runtime"""
        print(f"Setting up AgentCore Runtime for {runtime_config['name']}...")

        self._check_required_files(runtime_config)

        # Derive agent name from runtime name
        derived_names = self._derive_runtime_names(runtime_config["name"])

        agentcore_runtime = Runtime()

        auth_config = {
            "customJWTAuthorizer": {
                "allowedClients": [runtime_cognito["client_id"]],
                "discoveryUrl": runtime_cognito["discovery_url"],
            }
        }

        response = agentcore_runtime.configure(
            entrypoint=runtime_config["entrypoint"],
            auto_create_execution_role=runtime_config.get(
                "auto_create_execution_role", True
            ),
            auto_create_ecr=runtime_config.get("auto_create_ecr", True),
            requirements_file=runtime_config["requirements_file"],
            region=self.region,
            authorizer_configuration=auth_config,
            protocol=runtime_config.get("protocol", "MCP"),
            agent_name=derived_names["agent_name"],
        )
        print(f"AgentCore Runtime configured for {runtime_config['name']}: {response}")
        print(f"Launching MCP server {runtime_config['name']} to AgentCore Runtime...")
        launch_result = agentcore_runtime.launch(auto_update_on_conflict=True)

        agent_arn = launch_result.agent_arn
        encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
        agent_url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

        print(f"Agent ARN: {agent_arn}")
        return {"agent_arn": agent_arn, "agent_url": agent_url}

    def create_gateway_target(
        self, gateway_info, runtime_info, runtime_cognito, target_config
    ):
        """Create gateway target and configure authentication"""
        print("Creating Oauth Credential Provider")
        cognito_provider_arn = utils.get_or_create_oauth2_credential_provider(
            self.region, target_config["identity_provider_name"], runtime_cognito
        )
        print(f"Creating gateway target {target_config['name']}...")
        # Create gateway target
        target_creation_params = {
            "gateway_id": gateway_info["gateway_id"],
            "agent_url": runtime_info["agent_url"],
            "scope_string": runtime_cognito["scope_string"],
            "name": target_config["name"],
            "cognito_provider_arn": cognito_provider_arn,
        }
        gw_target_info = utils.get_or_create_agentcore_gateway_target(
            self.region, target_creation_params
        )
        return gw_target_info

    def run(self):
        """Execute the complete setup process"""
        print("Starting AgentCore Gateway and Runtime setup...")

        # Setup gateway Cognito resources
        gateway_cognito = self.setup_gateway_cognito()

        # Create gateway
        gateway_info = self.create_gateway(gateway_cognito)

        # Process multiple runtimes and targets
        runtime_infos = []
        for runtime_config in self.config["runtime"]:
            # Setup runtime Cognito resources
            runtime_cognito = self.setup_runtime_cognito(runtime_config)

            # Setup runtime
            runtime_info = self.setup_runtime(runtime_config, runtime_cognito)
            runtime_infos.append(runtime_info)

            # Derive target configuration from runtime name
            target_config = self._derive_target_names(runtime_config["name"])
            self.create_gateway_target(
                gateway_info, runtime_info, runtime_cognito, target_config
            )

        # Display gateway connection information
        gateway_info_result = self.display_gateway_info(
            gateway_info["gateway_id"], gateway_cognito
        )

        print("\n✅ Setup completed successfully!")
        print(f"Gateway ID: {gateway_info['gateway_id']}")
        for i, runtime_info in enumerate(runtime_infos):
            print(f"Runtime {i+1} Agent ARN: {runtime_info['agent_arn']}")
        return gateway_info_result

    def display_gateway_info(self, gateway_id, gateway_cognito):
        """Display gateway connection information"""
        print("\n" + "=" * 60)
        print("GATEWAY CONNECTION INFORMATION")
        print("=" * 60)

        # Get gateway URL
        gateway_url = f"https://{gateway_id}.gateway.bedrock-agentcore.{self.config['aws']['region']}.amazonaws.com/mcp"
        print(f"Gateway URL: {gateway_url}")

        # Display Cognito information
        print(f"User Pool ID: {gateway_cognito['user_pool_id']}")
        print(f"Client ID: {gateway_cognito['client_id']}")
        print(f"Client Secret: {gateway_cognito['client_secret']}")

        # Get access token
        access_token = self._get_access_token(gateway_cognito)
        if access_token:
            print(f"Access Token: {access_token}")
        print("=" * 60)

        return {
            "gateway_url": gateway_url,
            "user_pool_id": gateway_cognito["user_pool_id"],
            "client_id": gateway_cognito["client_id"],
            "client_secret": gateway_cognito["client_secret"],
            "access_token": access_token,
        }

    def _get_access_token(self, gateway_cognito):
        """Get access token using client credentials flow"""
        try:
            # Get scope configuration
            scope_names = [
                f"{gateway_cognito['resource_server_id']}/{scope['name']}"
                for scope in self.config["scopes"]
            ]
            scope_string = " ".join(scope_names)

            # Get token using utils
            token_response = utils.get_token(
                gateway_cognito["user_pool_id"],
                gateway_cognito["client_id"],
                gateway_cognito["client_secret"],
                scope_string,
                self.config["aws"]["region"],
            )
            return token_response["access_token"]
        except Exception as e:
            print(f"Warning: Could not retrieve access token: {e}")
            return None


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="AgentCore Gateway and Runtime Setup Toolkit"
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--gateway-name", required=True, help="Gateway name")
    parser.add_argument("--gateway-description", help="Gateway description")
    parser.add_argument(
        "--runtime-configs",
        required=True,
        help='JSON string of runtime configurations: [{"name":"runtime1","description":"desc","entrypoint":"path","requirements_file":"path"}]',
    )

    args = parser.parse_args()

    # Parse runtime configs from JSON
    try:
        runtime_configs = json.loads(args.runtime_configs)
    except json.JSONDecodeError:
        print("Error: Invalid JSON format for --runtime-configs")
        return 1

    # Build config structure with hardcoded scope
    config = {
        "aws": {"region": args.region},
        "gateway": {
            "name": args.gateway_name,
            "description": args.gateway_description or f"{args.gateway_name} Gateway",
        },
        "runtime": runtime_configs,
        "scopes": [
            {
                "name": "invoke",
                "description": "Scope for invoking the agentcore gateway",
            }
        ],
    }

    toolkit = AgentCoreToolkit(config)
    toolkit.run()


if __name__ == "__main__":
    main()
