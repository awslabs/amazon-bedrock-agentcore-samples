"""Custom resource: create/update/delete an AgentCore OAuth2 credential provider.

The provider stores the Auth0 M2M client_id / client_secret inside
AgentCore Identity. At runtime, the agent uses
`@requires_access_token(provider_name=..., auth_flow="M2M")` and AgentCore
performs the client_credentials grant against Auth0 internally.

The agent never sees the client_secret. The trigger Lambda doesn't either.
"""

import json
import logging
import os

import boto3

from infra_utils import cfnresponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AUTH0_SECRET_ARN = os.environ["AUTH0_SECRET_ARN"]


def _client_secret() -> str:
    secrets = boto3.client("secretsmanager")
    raw = secrets.get_secret_value(SecretId=AUTH0_SECRET_ARN)["SecretString"]
    return json.loads(raw)["client_secret"]


def handler(event, context):
    logger.info("oauth_provider_lambda RequestType=%s", event.get("RequestType"))
    try:
        props = event["ResourceProperties"]
        provider_name = props["ProviderName"]
        physical_id = provider_name
        control = boto3.client("bedrock-agentcore-control")

        if event["RequestType"] == "Delete":
            try:
                control.delete_oauth2_credential_provider(name=provider_name)
                logger.info("deleted provider %s", provider_name)
            except control.exceptions.ResourceNotFoundException:
                logger.info("provider %s already gone", provider_name)
            except Exception as exc:  # best-effort delete
                logger.warning("delete failed (continuing): %s", exc)
            cfnresponse.send(
                event, context, cfnresponse.SUCCESS, physicalResourceId=physical_id
            )
            return

        config = {
            "customOauth2ProviderConfig": {
                "clientId": props["ClientId"],
                "clientSecret": _client_secret(),
                "oauthDiscovery": {
                    "discoveryUrl": props["DiscoveryUrl"],
                },
            }
        }

        try:
            resp = control.create_oauth2_credential_provider(
                name=provider_name,
                credentialProviderVendor="CustomOauth2",
                oauth2ProviderConfigInput=config,
            )
            logger.info("created provider %s", provider_name)
        except control.exceptions.ConflictException:
            resp = control.update_oauth2_credential_provider(
                name=provider_name,
                credentialProviderVendor="CustomOauth2",
                oauth2ProviderConfigInput=config,
            )
            logger.info("updated provider %s", provider_name)

        data = {
            "ProviderName": provider_name,
            "ProviderArn": resp.get("credentialProviderArn", ""),
        }
        cfnresponse.send(
            event, context, cfnresponse.SUCCESS, data, physicalResourceId=physical_id
        )
    except Exception as exc:
        logger.exception("oauth provider operation failed")
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": str(exc)})
