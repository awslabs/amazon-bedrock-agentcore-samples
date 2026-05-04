#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
CLI for creating and managing Cognito OAuth2 credential providers.

Creates machine-client app clients for each HR persona with the correct
OAuth scopes, then stores credentials in SSM for use by test scripts.

Usage:
  python scripts/cognito_credentials_provider.py create --config prerequisite/prereqs_config.yaml
  python scripts/cognito_credentials_provider.py list
  python scripts/cognito_credentials_provider.py delete --client-id <id>
"""

import json
import sys

import boto3
import click

from scripts.utils import get_ssm_parameter, put_ssm_parameter, read_config

# Persona definitions: name → scopes + tenant context
# tenant context is written to SSM as the client_id→context mapping used by
# the Gateway interceptors (tenant_mapping.py) to resolve tenantId from JWT sub.
PERSONAS = {
    "hr-manager": {
        "description": "Full access to all HR data",
        "scopes": [
            "hr-dlp-gateway/read",
            "hr-dlp-gateway/pii",
            "hr-dlp-gateway/address",
            "hr-dlp-gateway/comp",
        ],
        "tenantId": "tenant-alpha",
        "role": "hr-manager",
        "department": "Human Resources",
        "username": "hr-manager",
    },
    "hr-specialist": {
        "description": "Employee profiles + PII, no compensation",
        "scopes": ["hr-dlp-gateway/read", "hr-dlp-gateway/pii"],
        "tenantId": "tenant-alpha",
        "role": "hr-specialist",
        "department": "Human Resources",
        "username": "hr-specialist",
    },
    "employee": {
        "description": "Basic search only",
        "scopes": ["hr-dlp-gateway/read"],
        "tenantId": "tenant-alpha",
        "role": "employee",
        "department": "Engineering",
        "username": "employee",
    },
    "admin": {
        "description": "Full administrative access",
        "scopes": [
            "hr-dlp-gateway/read",
            "hr-dlp-gateway/pii",
            "hr-dlp-gateway/address",
            "hr-dlp-gateway/comp",
        ],
        "tenantId": "tenant-alpha",
        "role": "admin",
        "department": "IT",
        "username": "admin",
    },
}


@click.group()
def cli():
    """Manage Cognito credential providers for HR Data Agent personas."""


@cli.command()
@click.option("--config", default="prerequisite/prereqs_config.yaml", show_default=True)
@click.option("--region", default=None)
def create(config: str, region: str):
    """Create one app client per persona and store credentials in SSM."""
    cfg = read_config(config)
    region = region or cfg.get("aws", {}).get("region", "us-east-1")
    user_pool_id = get_ssm_parameter("/app/hrdlp/cognito-user-pool-id")
    if not user_pool_id:
        click.echo("ERROR: Cognito User Pool ID not found in SSM.", err=True)
        sys.exit(1)

    cognito = boto3.client("cognito-idp", region_name=region)
    clients = []

    tenant_mapping: dict = {}

    for persona, meta in PERSONAS.items():
        resp = cognito.create_user_pool_client(
            UserPoolId=user_pool_id,
            ClientName=f"hr-dlp-{persona}",
            GenerateSecret=True,
            AllowedOAuthFlows=["client_credentials"],
            AllowedOAuthFlowsUserPoolClient=True,
            AllowedOAuthScopes=meta["scopes"],
            AccessTokenValidity=60,
            TokenValidityUnits={"AccessToken": "minutes"},
        )
        client_data = resp["UserPoolClient"]
        client_id = client_data["ClientId"]
        client_secret = client_data["ClientSecret"]

        put_ssm_parameter(f"/app/hrdlp/personas/{persona}/client-id", client_id)
        put_ssm_parameter(f"/app/hrdlp/personas/{persona}/client-secret", client_secret, secure=True)

        # Build entry for interceptor tenant mapping
        tenant_mapping[client_id] = {
            "tenantId": meta["tenantId"],
            "role": meta["role"],
            "department": meta["department"],
            "username": meta["username"],
        }

        clients.append({"persona": persona, "client_id": client_id, "scopes": meta["scopes"]})
        click.echo(f"  Created client for {persona}: {client_id}")

    # Write mapping to SSM — interceptors (tenant_mapping.py) read this at cold-start
    put_ssm_parameter("/app/hrdlp/client-tenant-mapping", json.dumps(tenant_mapping))
    click.echo(f"\nCreated {len(clients)} persona clients.")
    click.echo("Tenant mapping stored in SSM: /app/hrdlp/client-tenant-mapping")


@cli.command("list")
@click.option("--config", default="prerequisite/prereqs_config.yaml", show_default=True)
@click.option("--region", default=None)
def list_clients(config: str, region: str):
    """List existing app clients in the User Pool."""
    cfg = read_config(config)
    region = region or cfg.get("aws", {}).get("region", "us-east-1")
    user_pool_id = get_ssm_parameter("/app/hrdlp/cognito-user-pool-id")
    if not user_pool_id:
        click.echo("ERROR: User Pool ID not found in SSM.", err=True)
        sys.exit(1)

    cognito = boto3.client("cognito-idp", region_name=region)
    paginator = cognito.get_paginator("list_user_pool_clients")
    for page in paginator.paginate(UserPoolId=user_pool_id):
        for c in page["UserPoolClients"]:
            click.echo(f"  {c['ClientName']:40s}  {c['ClientId']}")


@cli.command()
@click.option("--client-id", required=True)
@click.option("--config", default="prerequisite/prereqs_config.yaml", show_default=True)
@click.option("--region", default=None)
def delete(client_id: str, config: str, region: str):
    """Delete a specific app client."""
    cfg = read_config(config)
    region = region or cfg.get("aws", {}).get("region", "us-east-1")
    user_pool_id = get_ssm_parameter("/app/hrdlp/cognito-user-pool-id")
    cognito = boto3.client("cognito-idp", region_name=region)
    cognito.delete_user_pool_client(UserPoolId=user_pool_id, ClientId=client_id)
    click.echo(f"Deleted client: {client_id}")


if __name__ == "__main__":
    cli()
