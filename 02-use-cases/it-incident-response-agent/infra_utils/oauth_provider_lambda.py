"""Custom resource: create/update/delete an AgentCore OAuth2 credential provider.

Generic over IdP. The handler reads `Vendor` from ResourceProperties and
shapes the provider config accordingly.

Vendors handled:
  - CustomOauth2     : Auth0 M2M (client_credentials, with discovery URL)
  - AtlassianOauth2  : Atlassian / Jira 3LO (authorization_code)

Both vendors store the client_secret inside AgentCore Identity. The agent
uses `@requires_access_token(provider_name=...)` and AgentCore performs
the OAuth grant against the IdP internally — the agent never sees the
secret.
"""

import json
import logging
import os

import boto3

from infra_utils import cfnresponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _client_secret(secret_arn: str) -> str:
    secrets = boto3.client("secretsmanager")
    raw = secrets.get_secret_value(SecretId=secret_arn)["SecretString"]
    return json.loads(raw)["client_secret"]


def _build_config(props: dict) -> dict:
    vendor = props["Vendor"]
    client_id = props["ClientId"]
    client_secret = _client_secret(props["SecretArn"])

    if vendor == "CustomOauth2":
        return {
            "customOauth2ProviderConfig": {
                "clientId": client_id,
                "clientSecret": client_secret,
                "oauthDiscovery": {"discoveryUrl": props["DiscoveryUrl"]},
            }
        }
    if vendor == "AtlassianOauth2":
        return {
            "atlassianOauth2ProviderConfig": {
                "clientId": client_id,
                "clientSecret": client_secret,
            }
        }
    raise ValueError(f"unsupported vendor: {vendor}")


def handler(event, context):
    logger.info("oauth_provider_lambda RequestType=%s", event.get("RequestType"))
    try:
        props = event["ResourceProperties"]
        provider_name = props["ProviderName"]
        vendor = props["Vendor"]
        physical_id = provider_name
        control = boto3.client("bedrock-agentcore-control")

        if event["RequestType"] == "Delete":
            try:
                control.delete_oauth2_credential_provider(name=provider_name)
                logger.info("deleted provider %s", provider_name)
            except control.exceptions.ResourceNotFoundException:
                logger.info("provider %s already gone", provider_name)
            except Exception as exc:
                logger.warning("delete failed (continuing): %s", exc)
            cfnresponse.send(
                event, context, cfnresponse.SUCCESS, physicalResourceId=physical_id
            )
            return

        config = _build_config(props)

        try:
            resp = control.create_oauth2_credential_provider(
                name=provider_name,
                credentialProviderVendor=vendor,
                oauth2ProviderConfigInput=config,
            )
            logger.info("created provider %s (%s)", provider_name, vendor)
        except control.exceptions.ConflictException:
            resp = control.update_oauth2_credential_provider(
                name=provider_name,
                credentialProviderVendor=vendor,
                oauth2ProviderConfigInput=config,
            )
            logger.info("updated provider %s (%s)", provider_name, vendor)

        data = {
            "ProviderName": provider_name,
            "ProviderArn": resp.get("credentialProviderArn", ""),
            "CallbackUrl": resp.get("callbackUrl", ""),
        }
        cfnresponse.send(
            event, context, cfnresponse.SUCCESS, data, physicalResourceId=physical_id
        )
    except Exception as exc:
        logger.exception("oauth provider operation failed")
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(exc)})
