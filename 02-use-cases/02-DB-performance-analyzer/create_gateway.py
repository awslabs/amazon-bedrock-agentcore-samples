import boto3
import os

agentcore_client = boto3.client('bedrock-agentcore-control', 
                              region_name =os.getenv('AWS_REGION', 'us-west-2'), 
                              endpoint_url = "ENDPOINT_URL")

COGNITO_USERPOOL_ID=os.getenv('COGNITO_USERPOOL_ID')
COGNITO_APP_CLIENT_ID=os.getenv('COGNITO_APP_CLIENT_ID')

auth_config = {
    "customJWTAuthorizer": { 
        #"allowedAudience": ["MCPGateway"],
        "allowedClients":  [COGNITO_APP_CLIENT_ID],
        "discoveryUrl": "https://cognito-idp.us-west-2.amazonaws.com/{COGNITO_USERPOOL_ID}/.well-known/openid-configuration"
    }
}

# CreateGateway
create_response = agentcore_client.create_gateway(name=os.getenv('GATEWAY_NAME','Aurora-Postgres-DB-Analyzer-Gateway'),
    roleArn = os.getenv('ROLE_ARN'), # The IAM Role must have permissions to create/list/get/delete Gateway 
    protocolType='MCP',
    authorizerType='CUSTOM_JWT',
    authorizerConfiguration=auth_config, 
    description=os.getenv('GATEWAY_DESCRIPTION', 'Aurora Postgres DB Analyzer Gateway'),
    
)
print(create_response) # need to print gatway id here from the response.



