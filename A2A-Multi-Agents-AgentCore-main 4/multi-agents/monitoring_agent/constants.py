import os
import json
import boto3
from utils import load_config

# This is the path of the config file that contains information about the 
# agents and the respective primitives
CONFIG_FNAME: str = "config.yaml"
# Load the config file. 
config_data = load_config(CONFIG_FNAME)
print(f"Config data in constants: {json.dumps(config_data, indent=4)}")

# These are the tool use IDs that are initialized for the strands based
# callback handler functions
TOOL_USE_IDS = []
# This is the cognito discovery URL that is used to fetch the region name
# and the user pool ID which is then used to populate this and it is used
# in the auth config for the inbound auth of the agentcore gateway
COGNITO_DISCOVERY_URL = """https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"""
# MCP auth
MCP_PROTOCOL: str = "MCP"
# Authorizer type
AUTH_TYPE_CUSTOM_JWT: str = "CUSTOM_JWT"

# These are the memory prompts that are used for extraction and consolidation
# MONITORING AGENT MEMORY PROMPTS
MEMORY_PROMPTS_FPATH: str = 'custom_memory_prompts'
MONITORING_AGENT_MEMORY_PROMPT_FPATH: str = os.path.join(MEMORY_PROMPTS_FPATH, 'monitoring_agent_memory')
MONITORING_CUSTOM_EXTRACTION_PROMPT_FPATH: str = os.path.join(MONITORING_AGENT_MEMORY_PROMPT_FPATH, 'custom_extraction_prompt.txt')
MONITORING_CONSOLIDATION_EXTRACTION_PROMPT_FPATH: str = os.path.join(MONITORING_AGENT_MEMORY_PROMPT_FPATH, 'custom_consolidation_prompt.txt')
# Gateway configuration constants
# This is the gateway information for the monitoring agent
MONITORING_GATEWAY_NAME = "MonitoringAgentGWNew"
MONITORING_GATEWAY_DESC: str = "Gateway for the monitoring agent"
MONITORING_GATEWAY_CREDENTIALS_PATH = "mcp_credentials.json"
REGION_NAME = boto3.Session().region_name
ACCOUNT_ID = boto3.client("sts").get_caller_identity()["Account"]
LAMBDA_ARN = f"arn:aws:lambda:{REGION_NAME}:{ACCOUNT_ID}:function:AgentGatewayFunction"

# This is the prompt template directory for the agents
# Read the monitoring agent system prompt from the template file
PROMPT_TEMPLATE = config_data['agent_information']['prompt_templates']
PROMPT_TEMPLATE_DIR = PROMPT_TEMPLATE['prompt_template_dir']