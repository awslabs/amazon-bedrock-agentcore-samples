"""
Deploy resources for the multi-tenant Gateway isolation demo.

Creates:
  1. Lambda tools (one function per target group)
  2. Cognito User Pool with two M2M app clients (insurance + banking scopes)
  3. AgentCore MCP Gateway with Cognito JWT authorizer
  4. Lambda targets attached to the Gateway
  5. Cedar Policy Engine (ENFORCE mode) with per-tenant policies
  6. Attaches Policy Engine to Gateway

All output written to config.json for use by demo.py and cleanup.py.

Usage:
    python deploy.py [--region REGION]
"""

import argparse
import io
import json
import logging
import os
import time
import uuid
import zipfile
from pathlib import Path

import boto3
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

# Constants
GATEWAY_NAME = "MultiTenantIsolation-Demo"
LAMBDA_ROLE_NAME = "MultiTenantIsolationDemoLambdaRole"
POLICIES_DIR = Path(__file__).parent / "policies"

# Tool schemas per target Lambda
TARGETS = {
    "query-tools": {
        "description": "Shared query tools (data access layer)",
        "tools": [
            {
                "name": "query_accounts",
                "description": "Query customer bank accounts",
                "inputSchema": {
                    "type": "object",
                    "properties": {"customer_id": {"type": "string"}},
                    "required": ["customer_id"],
                },
            },
            {
                "name": "query_transactions",
                "description": "Query account transactions",
                "inputSchema": {
                    "type": "object",
                    "properties": {"account_id": {"type": "string"}},
                    "required": ["account_id"],
                },
            },
            {
                "name": "query_claims",
                "description": "Query insurance claims for a member",
                "inputSchema": {
                    "type": "object",
                    "properties": {"member_id": {"type": "string"}},
                    "required": ["member_id"],
                },
            },
            {
                "name": "query_members",
                "description": "Query members on an insurance plan",
                "inputSchema": {
                    "type": "object",
                    "properties": {"plan_id": {"type": "string"}},
                    "required": ["plan_id"],
                },
            },
            {
                "name": "query_providers",
                "description": "Query healthcare providers by specialty",
                "inputSchema": {
                    "type": "object",
                    "properties": {"specialty": {"type": "string"}},
                    "required": ["specialty"],
                },
            },
            {
                "name": "query_benefits",
                "description": "Query plan benefits and coverage details",
                "inputSchema": {
                    "type": "object",
                    "properties": {"plan_id": {"type": "string"}},
                    "required": ["plan_id"],
                },
            },
        ],
    },
    "flag-suspicious": {
        "description": "Flag suspicious banking transactions",
        "tools": [
            {
                "name": "flag_suspicious",
                "description": "Flag a transaction as potentially fraudulent",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "transaction_id": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["transaction_id", "reason"],
                },
            },
        ],
    },
    "submit-decision": {
        "description": "Submit insurance underwriting decisions",
        "tools": [
            {
                "name": "submit_decision",
                "description": "Submit a claims decision",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "claim_id": {"type": "string"},
                        "decision": {"type": "string", "description": "One of: approved, denied, pending"},
                    },
                    "required": ["claim_id", "decision"],
                },
            },
        ],
    },
    "notify-team": {
        "description": "Send notifications to internal teams",
        "tools": [
            {
                "name": "notify_team",
                "description": "Notify an internal team about a decision",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "team": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["team", "message"],
                },
            },
        ],
    },
}

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


# ── AWS Session Setup ────────────────────────────────────────────────────────


def get_aws_context(region=None):
    session = boto3.Session()
    resolved_region = region or session.region_name or os.environ.get("AWS_DEFAULT_REGION")
    if not resolved_region:
        raise ValueError("AWS region not configured. Pass --region or run: aws configure")
    account_id = session.client("sts", region_name=resolved_region).get_caller_identity()["Account"]
    return session, resolved_region, account_id


# ── Step 1: Lambda Deployment ────────────────────────────────────────────────


def get_or_create_lambda_role(iam_client, account_id):
    try:
        resp = iam_client.get_role(RoleName=LAMBDA_ROLE_NAME)
        log.info(f"  IAM role exists: {LAMBDA_ROLE_NAME}")
        return resp["Role"]["Arn"]
    except iam_client.exceptions.NoSuchEntityException:
        pass

    log.info(f"  Creating IAM role: {LAMBDA_ROLE_NAME}")
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    resp = iam_client.create_role(
        RoleName=LAMBDA_ROLE_NAME,
        AssumeRolePolicyDocument=json.dumps(trust),
        Description="Execution role for multi-tenant isolation demo Lambdas",
    )
    iam_client.attach_role_policy(
        RoleName=LAMBDA_ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )
    log.info("  Waiting 10s for IAM role propagation...")
    time.sleep(10)
    return resp["Role"]["Arn"]


def deploy_lambda(lambda_client, function_name, role_arn):
    """Deploy a Python Lambda from the shared handler."""
    log.info(f"  Deploying Lambda: {function_name}...")
    handler_path = Path(__file__).parent / "utils" / "lambda_tools" / "handler.py"
    with open(handler_path, "r", encoding="utf-8") as f:
        code = f.read()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("handler.py", code)
    buf.seek(0)
    zip_bytes = buf.read()

    try:
        resp = lambda_client.create_function(
            FunctionName=function_name,
            Runtime="python3.12",
            Role=role_arn,
            Handler="handler.handler",
            Code={"ZipFile": zip_bytes},
            Description=f"Multi-tenant isolation demo: {function_name}",
            Timeout=30,
            MemorySize=256,
        )
        waiter = lambda_client.get_waiter("function_active_v2")
        waiter.wait(FunctionName=function_name)
        log.info(f"    Created: {resp['FunctionArn']}")
        return resp["FunctionArn"]
    except lambda_client.exceptions.ResourceConflictException:
        resp = lambda_client.update_function_code(FunctionName=function_name, ZipFile=zip_bytes)
        waiter = lambda_client.get_waiter("function_updated_v2")
        waiter.wait(FunctionName=function_name)
        log.info(f"    Updated: {resp['FunctionArn']}")
        return resp["FunctionArn"]


def deploy_all_lambdas(lambda_client, iam_client, account_id):
    log.info("\n[Step 1] Deploying Lambda tool functions...")
    role_arn = get_or_create_lambda_role(iam_client, account_id)
    arns = {}
    for target_name in TARGETS:
        fn_name = f"MTIsolation_{target_name.replace('-', '_')}"
        arns[target_name] = deploy_lambda(lambda_client, fn_name, role_arn)
    log.info(f"  {len(arns)} Lambda functions ready")
    return arns


# ── Step 2: Cognito with Multi-Tenant Scopes ────────────────────────────────


def create_cognito_with_tenant_scopes(region):
    """Create Cognito User Pool with per-tenant OAuth scopes and app clients."""
    log.info("\n[Step 2] Creating Cognito User Pool with tenant scopes...")
    cognito = boto3.client("cognito-idp", region_name=region)

    pool_resp = cognito.create_user_pool(
        PoolName="MultiTenantIsolation-Pool",
        AdminCreateUserConfig={"AllowAdminCreateUserOnly": True},
    )
    pool_id = pool_resp["UserPool"]["Id"]
    log.info(f"  User Pool created: {pool_id}")

    domain_prefix = f"mt-isolation-{uuid.uuid4().hex[:8]}"
    cognito.create_user_pool_domain(Domain=domain_prefix, UserPoolId=pool_id)
    log.info(f"  Domain created: {domain_prefix}")

    cognito.create_resource_server(
        UserPoolId=pool_id,
        Identifier="platform",
        Name="Multi-Tenant Platform",
        Scopes=[
            {"ScopeName": "insurance", "ScopeDescription": "Insurance tenant scope"},
            {"ScopeName": "banking", "ScopeDescription": "Banking tenant scope"},
        ],
    )
    log.info("  Resource server created: platform/insurance, platform/banking")

    # Wait for domain DNS propagation
    log.info("  Waiting 60s for Cognito domain DNS propagation...")
    time.sleep(60)

    clients = {}
    tenant_configs = {
        "insurance": {"client_name": "healthco-client", "scope": "platform/insurance"},
        "banking": {"client_name": "finbank-client", "scope": "platform/banking"},
    }
    for tenant_key, cfg in tenant_configs.items():
        client_resp = cognito.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName=cfg["client_name"],
            GenerateSecret=True,
            AllowedOAuthFlows=["client_credentials"],
            AllowedOAuthScopes=[cfg["scope"]],
            AllowedOAuthFlowsUserPoolClient=True,
            SupportedIdentityProviders=["COGNITO"],
        )
        clients[tenant_key] = {
            "client_id": client_resp["UserPoolClient"]["ClientId"],
            "client_secret": client_resp["UserPoolClient"]["ClientSecret"],
            "scope": cfg["scope"],
        }
        log.info(f"  Client created: {cfg['client_name']} (scope: {cfg['scope']})")

    discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
    token_endpoint = f"https://{domain_prefix}.auth.{region}.amazoncognito.com/oauth2/token"

    return {
        "pool_id": pool_id,
        "domain": domain_prefix,
        "discovery_url": discovery_url,
        "token_endpoint": token_endpoint,
        "clients": clients,
        "all_client_ids": [c["client_id"] for c in clients.values()],
    }


# ── Step 3: Gateway + Targets ────────────────────────────────────────────────


def setup_gateway(region, cognito_config, lambda_arns):
    """Create AgentCore Gateway with Cognito JWT auth and Lambda targets."""
    log.info("\n[Step 3] Creating AgentCore MCP Gateway...")
    gw_client = GatewayClient(region_name=region)
    gw_client.logger.setLevel(logging.WARNING)

    authorizer_config = {
        "customJWTAuthorizer": {
            "allowedClients": cognito_config["all_client_ids"],
            "discoveryUrl": cognito_config["discovery_url"],
        }
    }

    gateway = gw_client.create_mcp_gateway(
        name=GATEWAY_NAME,
        authorizer_config=authorizer_config,
        enable_semantic_search=False,
    )
    log.info(f"  Gateway created: {gateway['gatewayUrl']}")

    # Fix IAM permissions for Lambda invocation
    gw_client.fix_iam_permissions(gateway)
    log.info("  Waiting 30s for IAM propagation...")
    time.sleep(30)

    # Add Lambda targets
    log.info("  Adding Lambda targets...")
    gateway_arn = gateway["gatewayArn"]
    lambda_client = boto3.client("lambda", region_name=region)

    for target_name, cfg in TARGETS.items():
        gw_client.create_mcp_gateway_target(
            gateway=gateway,
            name=f"{target_name}",
            target_type="lambda",
            target_payload={
                "lambdaArn": lambda_arns[target_name],
                "toolSchema": {"inlinePayload": cfg["tools"]},
            },
        )
        log.info(f"    Target added: {target_name} ({len(cfg['tools'])} tools)")

        # Add Lambda resource policy for Gateway invocation
        statement_id = "AllowAgentCoreGateway"
        try:
            lambda_client.remove_permission(
                FunctionName=lambda_arns[target_name].split(":")[-1],
                StatementId=statement_id,
            )
        except Exception:
            pass
        lambda_client.add_permission(
            FunctionName=lambda_arns[target_name].split(":")[-1],
            StatementId=statement_id,
            Action="lambda:InvokeFunction",
            Principal="bedrock-agentcore.amazonaws.com",
            SourceArn=gateway_arn,
        )

    return {
        "gateway_id": gateway["gatewayId"],
        "gateway_arn": gateway_arn,
        "gateway_url": gateway["gatewayUrl"],
        "role_arn": gateway.get("roleArn"),
    }


# ── Step 4: Policy Engine + Cedar Policies ───────────────────────────────────


def create_policy_engine_and_policies(region, gateway_info):
    """Create Cedar policy engine, upload policies, and attach to Gateway."""
    log.info("\n[Step 4] Creating Cedar Policy Engine...")
    control = boto3.client("bedrock-agentcore-control", region_name=region)

    engine_name = f"MTIsolation_Engine_{int(time.time()) % 100000}"
    resp = control.create_policy_engine(
        name=engine_name,
        description="Per-tenant tool isolation via Cedar scope matching",
        clientToken=str(uuid.uuid4()),
    )
    engine_id = resp["policyEngineId"]
    engine_arn = resp["policyEngineArn"]
    log.info(f"  Policy Engine created: {engine_id}")

    # Wait for ACTIVE
    log.info("  Waiting for ACTIVE status...")
    for _ in range(60):
        status = control.get_policy_engine(policyEngineId=engine_id).get("status")
        if status == "ACTIVE":
            break
        if status in ("CREATE_FAILED", "UPDATE_FAILED", "DELETE_FAILED"):
            raise RuntimeError(f"Policy Engine failed: {status}")
        time.sleep(5)
    log.info("  Policy Engine ACTIVE")

    # Upload Cedar policies from files (inject gateway ARN into resource clause)
    gateway_arn = gateway_info["gateway_arn"]
    log.info("  Uploading Cedar policies...")
    policy_ids = []
    for policy_file in sorted(POLICIES_DIR.glob("*.cedar")):
        statement = policy_file.read_text()
        # Replace generic 'resource' with gateway-scoped resource
        statement = statement.replace(
            "  resource\n",
            f'  resource == AgentCore::Gateway::"{gateway_arn}"\n',
        )
        policy_name = policy_file.stem
        resp = control.create_policy(
            policyEngineId=engine_id,
            name=policy_name,
            description=f"Tenant isolation: {policy_name}",
            definition={"cedar": {"statement": statement}},
        )
        policy_id = resp["policyId"]

        # Wait for policy ACTIVE
        for _ in range(20):
            p_status = control.get_policy(policyEngineId=engine_id, policyId=policy_id).get("status")
            if p_status == "ACTIVE":
                break
            if p_status in ("CREATE_FAILED",):
                raise RuntimeError(f"Policy {policy_name} failed: {p_status}")
            time.sleep(3)

        policy_ids.append(policy_id)
        log.info(f"    Policy ACTIVE: {policy_name}")

    # Attach Policy Engine to Gateway (ENFORCE mode)
    log.info("\n[Step 5] Attaching Policy Engine to Gateway (ENFORCE mode)...")
    gateway_id = gateway_info["gateway_id"]
    gw = control.get_gateway(gatewayIdentifier=gateway_id)
    control.update_gateway(
        gatewayIdentifier=gateway_id,
        name=gw["name"],
        roleArn=gw["roleArn"],
        protocolType=gw.get("protocolType", "MCP"),
        authorizerType=gw.get("authorizerType", "CUSTOM_JWT"),
        authorizerConfiguration=gw.get("authorizerConfiguration", {}),
        policyEngineConfiguration={"arn": engine_arn, "mode": "ENFORCE"},
    )

    # Wait for Gateway READY after update
    for _ in range(60):
        status = control.get_gateway(gatewayIdentifier=gateway_id).get("status")
        if status == "READY":
            break
        if status in ("FAILED", "UPDATE_UNSUCCESSFUL"):
            raise RuntimeError(f"Gateway update failed: {status}")
        time.sleep(5)
    log.info("  Policy Engine attached to Gateway")

    return {
        "engine_id": engine_id,
        "engine_arn": engine_arn,
        "policy_ids": policy_ids,
    }


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Deploy multi-tenant isolation demo")
    parser.add_argument("--region", help="AWS region", default=None)
    args = parser.parse_args()

    _, region, account_id = get_aws_context(args.region)
    log.info("=" * 65)
    log.info("Multi-Tenant Gateway Isolation Demo - Deployment")
    log.info("=" * 65)
    log.info(f"  Region:  {region}")
    log.info(f"  Account: {account_id}")

    lambda_client = boto3.client("lambda", region_name=region)
    iam_client = boto3.client("iam", region_name=region)

    # Step 1: Deploy Lambda tools
    lambda_arns = deploy_all_lambdas(lambda_client, iam_client, account_id)

    # Step 2: Create Cognito with tenant scopes
    cognito_config = create_cognito_with_tenant_scopes(region)

    # Step 3: Create Gateway + Lambda targets
    gateway_info = setup_gateway(region, cognito_config, lambda_arns)

    # Step 4-5: Create Policy Engine, upload Cedar policies, attach to Gateway
    policy_info = create_policy_engine_and_policies(region, gateway_info)

    # Save config
    config = {
        "region": region,
        "account_id": account_id,
        "cognito": cognito_config,
        "gateway": gateway_info,
        "policy_engine": policy_info,
        "lambda_arns": lambda_arns,
    }
    config_path = Path(__file__).parent / "config.json"
    config_path.write_text(json.dumps(config, indent=2))

    log.info(f"\n{'=' * 65}")
    log.info("Deployment complete!")
    log.info(f"  Gateway URL:      {gateway_info['gateway_url']}")
    log.info(f"  Policy Engine:    {policy_info['engine_id']}")
    log.info("  Config saved to:  config.json")
    log.info("\n  Next: python demo.py")
    log.info("=" * 65)


if __name__ == "__main__":
    main()
