import boto3
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get environment variables
AWS_REGION = os.getenv('AWS_REGION')
ENDPOINT_URL = os.getenv('ENDPOINT_URL')
COGNITO_USERPOOL_ID = os.getenv('COGNITO_USERPOOL_ID')
COGNITO_APP_CLIENT_ID = os.getenv('COGNITO_APP_CLIENT_ID')
GATEWAY_NAME = os.getenv('GATEWAY_NAME', 'Device-Management-Gateway')
ROLE_ARN = os.getenv('ROLE_ARN')
GATEWAY_DESCRIPTION = os.getenv('GATEWAY_DESCRIPTION', 'Device Management Gateway')

# Initialize the Bedrock Agent Core Control client
bedrock_agent_core_client = boto3.client(
    'bedrock-agentcore-control', 
    region_name=AWS_REGION, 
    endpoint_url=ENDPOINT_URL
)

# Configure the authentication
auth_config = {
    "customJWTAuthorizer": { 
        "allowedClients": [COGNITO_APP_CLIENT_ID],
        "discoveryUrl": f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USERPOOL_ID}/.well-known/openid-configuration"
    }
}

# Create the gateway
create_response = bedrock_agent_core_client.create_gateway(
    name=GATEWAY_NAME,
    roleArn=ROLE_ARN,  # The IAM Role must have permissions to create/list/get/delete Gateway 
    protocolType='MCP',
    authorizerType='CUSTOM_JWT',
    authorizerConfiguration=auth_config, 
    description=GATEWAY_DESCRIPTION
)

# Print the gateway ID and other information
gateway_id = create_response.get('gatewayId')
print(f"Gateway created successfully!")
print(f"Gateway ID: {gateway_id}")
print(f"Gateway ARN: {create_response.get('gatewayArn')}")
print(f"Creation Time: {create_response.get('creationTime')}")
