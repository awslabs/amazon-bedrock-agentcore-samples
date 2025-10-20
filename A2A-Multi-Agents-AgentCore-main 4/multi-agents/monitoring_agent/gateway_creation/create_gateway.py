import os
import sys
import yaml
import json
import logging
import time
sys.path.insert(0, ".")
sys.path.insert(1, "..")
from utils import *
from typing import Dict, List, Any, Union

# Create a logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Remove existing handlers
logger.handlers.clear()

# Add a simple handler
handler = logging.StreamHandler()
formatter = logging.Formatter('[%(asctime)s] p%(process)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# first load the config.yaml file which contains information about the
# gateway that will be required in agentcore gateway creation
# Load the config file. 
config_data = load_config('setup_gateway.yaml')
print(f"Configuration loaded successfully: {json.dumps(config_data, indent=4)}")
gateway_config: Dict = config_data['gateway_config']

# Next, we will create the agentcore gateway role.
agentcore_gateway_iam_role = create_agentcore_gateway_role("sample-lambdagateway")
print("Agentcore gateway role ARN: ", agentcore_gateway_iam_role['Arn'])

# create the gateway with the amazon cognito authorizer for inbound authentication
gateway_client = boto3.client('bedrock-agentcore-control', region_name = boto3.session.Session().region_name)
logger.info(f"Created the gateway client: {gateway_client}")

# fetch the client id and the discovery url from the config file that would contain this information
# from running the pre requisite step of setting up the idp through the idp_setup folder
client_id = gateway_config['auth_info'].get('client_id')
discovery_url = gateway_config['auth_info'].get('discovery_url')
logger.info(f"Going to use the discovery URL: {discovery_url} and client id: {client_id} to connect to the gateway and set upn the inbound auth for it.")
# Now, we will create the custom auth configuration that will be used
# as a mode of inbound authentication for the agent
auth_config = {
    "customJWTAuthorizer": {
        "allowedClients": [client_id], 
        "discoveryUrl": discovery_url
    }
}
# Next, we will go ahead and create the gateway
create_response = gateway_client.create_gateway(
    name=gateway_config.get('name', 'monitoringgtw'), 
    roleArn=agentcore_gateway_iam_role['Arn'], 
    protocolType='MCP', 
    authorizerType='CUSTOM_JWT', 
    authorizerConfiguration=auth_config,
    description=gateway_config.get('description'), 
    # this provides more granular level error messages to what is 
    # happening within the gateway
    exceptionLevel='DEBUG'
)
logger.info(f"Created the agentcore gateway for the monitoring agent: {create_response}")
# retrieve the gateway ID and the gateway URL
gatewayID=create_response['gatewayId']
gatewayURL=create_response['gatewayUrl']
logger.info(f"Going to be using the gateway ID: {gatewayID} and URL: {gatewayURL}")

# Wait for the gateway to be in ACTIVE status before creating targets
logger.info("Waiting for gateway to become ACTIVE...")
max_wait_time = 300  # 5 minutes
poll_interval = 10  # 10 seconds
elapsed_time = 0

while elapsed_time < max_wait_time:
    gateway_status_response = gateway_client.get_gateway(gatewayIdentifier=gatewayID)
    gateway_status = gateway_status_response['status']
    logger.info(f"Current gateway status: {gateway_status}")

    if gateway_status in ['ACTIVE', 'READY']:
        logger.info(f"Gateway is now {gateway_status}. Proceeding with target creation.")
        break
    elif gateway_status in ['FAILED', 'DELETING', 'DELETED']:
        raise Exception(f"Gateway creation failed with status: {gateway_status}")

    time.sleep(poll_interval)
    elapsed_time += poll_interval

if elapsed_time >= max_wait_time:
    raise TimeoutError(f"Gateway did not reach ACTIVE or READY status within {max_wait_time} seconds")

tools_file_path = os.path.join("..", "tools", "lambda_monitoring_tools.json")
with open(tools_file_path, 'r') as f:
    tools_config = json.load(f)
    print(f"Going to use the following tool config in the gateway target creation: {tools_config['tools']}")
      
# next, we will create a target to this gateway. In this case, target refers to the REST endpoints 
# that the gateway will host as tools - right now lambda functions, smithy models and OpenAPI specs are
# supported. In this case, we will be referring to a lambda function which will contain information
# about cloudwatch related tools and a JIRA tool as well.
lambda_target_config = {
    "mcp": {
        "lambda": {
            "lambdaArn": gateway_config['targets']['lambda'].get('role_arn'), 
            "toolSchema":
                {
                    "inlinePayload": tools_config['tools']
                        
                }
        }
    }
}

credential_config = [ 
    {
        "credentialProviderType" : "GATEWAY_IAM_ROLE"
    }
]

target_name: str = 'MonitoringOpsTarget'

# Next, we will create the target and attach it to the gateway we created
response = gateway_client.create_gateway_target(
    gatewayIdentifier=gatewayID, 
    name=target_name,
    description='Monitoring and Jira target', 
    targetConfiguration=lambda_target_config,
    # In this case, we are providing the gateway IAM role as the credential provider for outbound
    # auth and the lambda function uses the JIRA credentials, however, you could very well add another
    # target that is JIRA specific and then have that in the same gateway.
    credentialProviderConfigurations=credential_config
)
logger.info(f"Created the gateway target: {response}")

