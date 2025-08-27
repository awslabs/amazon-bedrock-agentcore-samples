"""
Deployment script for Device Management Strands Agent Runtime
"""
from bedrock_agentcore_starter_toolkit import Runtime
import time
import utils
import os
from dotenv import load_dotenv
import argparse

# Reading environment variables from .env and .env.runtime files
# load_dotenv() automatically loads from .env file
# Variables from .env.runtime will also be available if loaded separately
load_dotenv()
load_dotenv('.env.runtime')  # Explicitly load .env.runtime file

script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"Python file directory: {script_dir}")

# Setting parameters
parser = argparse.ArgumentParser(
    prog='device_management_strands_agent_runtime',
    description='Device Management Strands Agent with MCP Gateway',
    epilog='Input Parameters'
)

parser.add_argument('--gateway_id', help="Gateway Id", required=True)
parser.add_argument('--agent_name', help="Name of the agent", default="device_management_agent_29_jul_21")
parser.add_argument('--execution_role', help="IAM execution role ARN")

args = parser.parse_args()

# Parameter Validations
if args.gateway_id is None:
    raise Exception("Gateway Id is required")

if args.agent_name is None:
    args.agent_name = os.getenv("AGENT_NAME", "device-management-agent")

print(f"Deploying agent: {args.agent_name}")
print(f"Gateway ID: {args.gateway_id}")

# Create AgentCore client
try:
    (boto_session, agentcore_client) = utils.create_agentcore_client()
except Exception as e:
    print(f"Error creating AgentCore client: {e}")
    print("Make sure your AWS credentials are configured and utils.py has the create_agentcore_client function")
    exit(1)

# Launch configurations
FilesToCopy = [
    "strands_agent_runtime.py",
    "access_token.py",
    "utils.py", 
    "requirements-runtime.txt"
]

# Environment variables for the runtime
# Loading from both .env and .env.runtime files
EnvVariables = {
    # AWS configuration
    "AWS_DEFAULT_REGION": os.getenv("AWS_REGION", "us-west-2"),
    "AWS_REGION": os.getenv("AWS_REGION", "us-west-2"),
    
    # Cognito configuration
    "COGNITO_DOMAIN": os.getenv("COGNITO_DOMAIN"),
    "COGNITO_CLIENT_ID": os.getenv("COGNITO_CLIENT_ID"),
    "COGNITO_CLIENT_SECRET": os.getenv("COGNITO_CLIENT_SECRET"),
    "COGNITO_DISCOVERY_URL": os.getenv("COGNITO_DISCOVERY_URL"),
    "COGNITO_AUTH_URL": os.getenv("COGNITO_AUTH_URL"),
    "COGNITO_TOKEN_URL": os.getenv("COGNITO_TOKEN_URL"),
    "COGNITO_PROVIDER_NAME": os.getenv("COGNITO_PROVIDER_NAME"),
    
    # MCP Server configuration
    "MCP_SERVER_URL": os.getenv("MCP_SERVER_URL"),
    
    # IAM Role configuration
    "ROLE_ARN": os.getenv("ROLE_ARN"),
    
    # Bedrock AgentCore Runtime configuration
    "ENDPOINT_URL": os.getenv("ENDPOINT_URL"),
    "AGENT_NAME": os.getenv("AGENT_NAME", "device-management-agent"),
    "AGENT_DESCRIPTION": os.getenv("AGENT_DESCRIPTION", "Device Management Agent for IoT devices"),
    
    # Model configuration
    "BEDROCK_MODEL_ID": os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0"),
}

# Get gateway endpoint
try:
    gatewayEndpoint = utils.get_gateway_endpoint(agentcore_client=agentcore_client, gateway_id=args.gateway_id)
    print(f"Gateway Endpoint: {gatewayEndpoint}")
    if gatewayEndpoint:
        # Override MCP_SERVER_URL with the actual gateway endpoint
        EnvVariables["MCP_SERVER_URL"] = gatewayEndpoint
        EnvVariables["gateway_endpoint"] = gatewayEndpoint  # Keep for backward compatibility
    else:
        print("Gateway endpoint is empty, using value from .env file")
except Exception as e:
    print(f"Warning: Could not get gateway endpoint: {e}")
    print("Using value from .env file")

aws_region = boto_session.region_name
print(f"AWS region: {aws_region}")

print(f"Environment variables: {EnvVariables}")

# Exclusions for dockerignore file
excluded_prefixes = ('.venv', '.ipynb_checkpoints', '__pycache__', '.git', 'images')
dockerignoreappend = ['.venv/', '.ipynb_checkpoints/', '__pycache__/', '.git/', 'images/']

for root, dirs, files in os.walk(script_dir):
    # Modify dirs in-place to exclude unwanted directories
    dirs[:] = [d for d in dirs if not d.startswith(excluded_prefixes)]
    
    relativePathDir = os.path.split(root)[-1]
    
    if root != script_dir:
        if relativePathDir not in FilesToCopy:
            dockerignoreappend.append(f"{relativePathDir}/")
    else:
        for file in files:
            if file not in FilesToCopy: #and not file.startswith('.env'):
                dockerignoreappend.append(f"{file}")

print("Cleaning up existing docker files before configuration")
cleanup_files = [".dockerignore", "Dockerfile", ".bedrock_agentcore.yaml"]
for cleanup_file in cleanup_files:
    file_path = os.path.join(script_dir, cleanup_file)
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"Removed {cleanup_file}")

# Authentication configuration for Cognito
auth_config = {
    "customJWTAuthorizer": {
        "allowedClients": [
            os.getenv("COGNITO_CLIENT_ID")
        ],
        "discoveryUrl": f"https://{os.getenv('COGNITO_DOMAIN')}/.well-known/openid_configuration"
    }
}

# Credential configuration for OAuth
credential_config = {
    "credentialProviderType": "OAUTH",
    "credentialProvider": {
        "oauthCredentialProvider": {
            "providerArn": os.getenv("OAUTH_PROVIDER_ARN", ""),
            "scopes": ["openid"]
        }
    }
}

# Initialize AgentCore Runtime
agentcore_runtime = Runtime()

print("Configuring Agent Runtime")
try:
    response = agentcore_runtime.configure(
        entrypoint="strands_agent_runtime.py",
        execution_role=args.execution_role or os.getenv("ROLE_ARN"),
        auto_create_ecr=True,
        requirements_file="requirements-runtime.txt",
        region=aws_region,
        agent_name=args.agent_name,
        # Uncomment if you want to use credential configuration
        # authorizer_configuration=credential_config
    )
    print("Configuration successful")
except Exception as e:
    print(f"Configuration failed: {e}")
    exit(1)

print("Appending to .dockerignore file")
with open(os.path.join(script_dir, ".dockerignore"), "a") as f:
    f.write("\n")
    f.write("# Auto-generated exclusions\n")
    for ignorefile in dockerignoreappend:
        f.write(ignorefile + "\n")

print("Launching Agent...")
try:
    launch_result = agentcore_runtime.launch(env_vars=EnvVariables)
    print(f"Agent created with ARN: {launch_result.agent_arn}")
except Exception as e:
    print(f"Launch failed: {e}")
    exit(1)

# Monitor deployment status
print("Monitoring deployment status...")
status_response = agentcore_runtime.status()
print(f"Initial status: {status_response}")

status = status_response.endpoint['status']
end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']

while status not in end_status:
    print(f"Current status: {status}")
    time.sleep(10)
    try:
        status_response = agentcore_runtime.status()
        status = status_response.endpoint['status']
    except Exception as e:
        print(f"Error checking status: {e}")
        break

print(f"Final status: {status}")

if status == 'READY':
    print("🎉 Agent deployment successful!")
    
    # Quick test
    print("Running quick test...")
    try:
        invoke_response = agentcore_runtime.invoke({
            "prompt": "Hello! Can you help me with device management?"
        })
        print(f"Test response: {invoke_response}")
    except Exception as e:
        print(f"Test invocation failed: {e}")
        
elif status in ['CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']:
    print(f"❌ Agent deployment failed with status: {status}")
    print("Check the AWS console for detailed error logs")
else:
    print(f"⚠️  Agent deployment ended with unexpected status: {status}")

print("Deployment script completed.")