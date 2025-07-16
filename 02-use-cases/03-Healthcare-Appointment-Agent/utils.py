import httpx
import os
from dotenv import load_dotenv
import boto3
import requests

#Reading environment variables
load_dotenv()

def create_agentcore_client():
    #create boto3 session and client
    if os.getenv("awscred_profile_name") is None:
        boto_session = boto3.Session(region_name=os.getenv("aws_default_region")) #using default profile
    else:
        boto_session = boto3.Session(profile_name=os.getenv("awscred_profile_name"), region_name=os.getenv("aws_default_region"))

    agentcore_client = boto_session.client(
        "bedrock-agentcore-control"
    )

    return boto_session, agentcore_client

def create_http_client(**kwargs) -> httpx.AsyncClient:
    """Create an HTTPX client with SSL verification disabled."""
    kwargs['verify'] = False
    # Optionally add other configurations
    kwargs.setdefault('timeout', httpx.Timeout(30.0))
    return httpx.AsyncClient(**kwargs)

def get_gateway_endpoint(agentcore_client, gateway_id):
    response = agentcore_client.get_gateway(
        gatewayIdentifier=gateway_id\
    )

    return response['gatewayUrl']

def list_gateways(agentcore_client):
    response = agentcore_client.list_gateways()

    return response['items']

def get_oath_token():
    response = requests.post(
        os.getenv("cognito_token_url"),
        data=f"grant_type=client_credentials&client_id={os.getenv('cognito_client_id')}&client_secret={os.getenv('cognito_client_secret')}&scope={os.getenv('cognito_auth_scope')}",
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )

    #print(response.json())
    return response.json()['access_token']