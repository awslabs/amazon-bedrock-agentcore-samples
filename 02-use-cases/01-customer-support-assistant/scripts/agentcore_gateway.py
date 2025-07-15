from typing import List
import json
import argparse
import os
import boto3

from utils import (
    get_aws_region,
    get_ssm_parameter,
    load_api_spec,
    save_config,
)


REGION = get_aws_region()

gateway_client = boto3.client(
    "bedrock-agentcore-control",
    endpoint_url=f"https://bedrock-agentcore-control.{REGION}.amazonaws.com",
    region_name=REGION,
)


def delete_gateway():
    pass


def create_gateway(gateway_name: str, api_spec: List):  # noqa: F821
    # Use Cognito for Inbound OAuth to our Gateway

    lambda_target_config = {
        "mcp": {
            "lambda": {
                "lambdaArn": get_ssm_parameter(
                    "/app/customersupport/agentcore/lambda_arn"
                ),
                "toolSchema": {"inlinePayload": api_spec},
            }
        }
    }

    auth_config = {
        "customJWTAuthorizer": {
            "allowedClients": [
                get_ssm_parameter("/app/customersupport/agentcore/machine_client_id")
            ],
            "discoveryUrl": get_ssm_parameter(
                "/app/customersupport/agentcore/cognito_discovery_url"
            ),
        }
    }

    execution_role_arn = get_ssm_parameter(
        "/app/customersupport/agentcore/gateway_iam_role"
    )

    print(f"Creating gateway in region {REGION} with name: {gateway_name}")
    print(
        f"Creating gateway with target_source: \n{json.dumps(lambda_target_config, indent=2)}"
    )

    print(f"Creating gateway with execution_role_arn: {execution_role_arn}")

    print(
        f"Creating gateway with authorizer_config: \n{json.dumps(auth_config, indent=2)}"
    )

    create_response = gateway_client.create_gateway(
        name=gateway_name,
        roleArn=execution_role_arn,  # The IAM Role must have permissions to create/list/get/delete Gateway
        protocolType="MCP",
        authorizerType="CUSTOM_JWT",
        authorizerConfiguration=auth_config,
        description="Agentcore Gateway",
    )

    print(f"Gateway Created: {json.dumps(create_response, indent=2, default=str)}")

    credential_config = [{"credentialProviderType": "GATEWAY_IAM_ROLE"}]
    gateway_id = create_response["gatewayId"]
    arn = create_response["gatewayArn"]
    create_target_response = gateway_client.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name="LambdaUsingSDK",
        description="Lambda Target using SDK",
        targetConfiguration=lambda_target_config,
        credentialProviderConfigurations=credential_config,
    )

    print(
        f"Gateway Created: {json.dumps(create_target_response, indent=2, default=str)}"
    )

    return {
        "id": gateway_id,
        "name": gateway_name,
        "gateway_url": create_response["gatewayUrl"],
        "gateway_arn": create_response["gatewayArn"],
    }


if __name__ == "__main__":
    # setting parameters
    parser = argparse.ArgumentParser(
        description="Setup Gateway", epilog="Input Parameters"
    )

    parser.add_argument("--gateway_name", required=True, help="The name of gateway")

    args = parser.parse_args()

    api_spec = load_api_spec(os.path.join("lambda", "api_spec.json"))

    gateway = create_gateway(gateway_name=args.gateway_name, api_spec=api_spec)

    print(f"Gateway created with id: {gateway['id']}. Creating gateway target.")

    save_config(gateway, "gateway.config")

    print("Gateway config saved in gateway.config")
