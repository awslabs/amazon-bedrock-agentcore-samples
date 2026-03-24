"""
Post-deploy script: Configures Cognito JWT inbound auth on the AgentCore Runtime
and attaches the IAM policy needed for outbound identity credential retrieval.

The agentcore CLI does not yet expose authorizationConfiguration in agentcore.json,
so this script applies it via the boto3 control plane API after deployment.

Run this once after 'agentcore deploy -y'.

Usage:
    python configure_inbound_auth.py
"""

import boto3
import json
import os
import re
import subprocess
import sys


def find_project_dir() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    for entry in os.listdir(base):
        candidate = os.path.join(base, entry)
        if os.path.isdir(candidate) and os.path.isdir(os.path.join(candidate, "agentcore")):
            return candidate
    raise FileNotFoundError("No agentcore project directory found. Run 'agentcore create' first.")


def get_runtime_id() -> str:
    project_dir = find_project_dir()
    result = subprocess.run(
        ["agentcore", "status", "--json"],
        capture_output=True,
        text=True,
        cwd=project_dir,
    )
    clean = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", result.stdout).strip()
    status = json.loads(clean)
    for resource in status.get("resources", []):
        if resource.get("resourceType") == "agent" and resource.get("deploymentState") == "deployed":
            arn = resource.get("identifier", "")
            return arn.split("/")[-1]
    raise ValueError("No deployed agent found. Run 'agentcore deploy -y' first.")


def get_gateway_url(region: str) -> str:
    ctrl = boto3.client("bedrock-agentcore-control", region_name=region)
    gateways = ctrl.list_gateways()
    for gw in gateways.get("items", []):
        if "GatewayAuthDemo" in gw.get("name", ""):
            detail = ctrl.get_gateway(gatewayIdentifier=gw["gatewayId"])
            return detail.get("gatewayUrl", "")
    raise ValueError("GatewayAuthDemo gateway not found. Run 'agentcore deploy -y' first.")


def main():
    try:
        with open("cognito_config.json") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("ERROR: cognito_config.json not found. Run 'python setup_cognito.py' first.")
        sys.exit(1)

    region = config["region"]
    runtime_id = get_runtime_id()
    print(f"Configuring runtime: {runtime_id}")

    ctrl = boto3.client("bedrock-agentcore-control", region_name=region)
    iam = boto3.client("iam")
    sts = boto3.client("sts")
    account = sts.get_caller_identity()["Account"]

    current = ctrl.get_agent_runtime(agentRuntimeId=runtime_id)
    role_name = current["roleArn"].split("/")[-1]

    # Get gateway URL to set as env var
    gateway_url = get_gateway_url(region)
    print(f"Gateway URL: {gateway_url}")

    # Configure JWT inbound auth + gateway env var
    ctrl.update_agent_runtime(
        agentRuntimeId=runtime_id,
        agentRuntimeArtifact=current["agentRuntimeArtifact"],
        roleArn=current["roleArn"],
        networkConfiguration=current["networkConfiguration"],
        authorizerConfiguration={
            "customJWTAuthorizer": {
                "discoveryUrl": config["discovery_url"],
                "allowedClients": [config["user_client_id"]],
            }
        },
        environmentVariables={"AGENTCORE_GATEWAY_URL": gateway_url},
    )
    print("JWT inbound auth configured.")

    # Attach IAM policy for AgentCore Identity outbound credential retrieval
    print(f"Attaching IAM policy to role: {role_name}")
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="AgentCoreIdentityOutbound",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetResourceApiKey",
                        "bedrock-agentcore:GetResourceOauth2Token",
                    ],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": ["secretsmanager:GetSecretValue"],
                    "Resource": f"arn:aws:secretsmanager:{region}:{account}:secret:bedrock-agentcore*",
                },
            ],
        }),
    )
    print("IAM policy attached.")

    # Ensure the managed gateway credential exists (recreate if missing)
    providers = ctrl.list_oauth2_credential_providers()
    existing = {p["name"] for p in providers.get("credentialProviders", [])}
    if "MyGateway-oauth" not in existing:
        print("Recreating managed gateway credential 'MyGateway-oauth'...")
        ctrl.create_oauth2_credential_provider(
            name="MyGateway-oauth",
            credentialProviderVendor="CustomOauth2",
            oauth2ProviderConfigInput={
                "customOauth2ProviderConfig": {
                    "clientId": config["agent_client_id"],
                    "clientSecret": config["agent_client_secret"],
                    "oauthDiscovery": {
                        "discoveryUrl": config["discovery_url"],
                    },
                }
            },
        )
        print("  MyGateway-oauth created.")
    else:
        print("  MyGateway-oauth credential exists.")

    print("\nWait ~30s for changes to propagate, then run: python invoke.py")


if __name__ == "__main__":
    main()
