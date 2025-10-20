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
OPS_ORCHESTRATOR_AGENT_MEMORY_PROMPT_FPATH: str = os.path.join(MEMORY_PROMPTS_FPATH, 'ops_orchestrator_agent_memory')
# This is the agent that is the lead agent and stores memory for all of this
OPS_ORCHESTRATOR_CUSTOM_EXTRACTION_PROMPT_FPATH: str = os.path.join(OPS_ORCHESTRATOR_AGENT_MEMORY_PROMPT_FPATH, 'custom_extraction_prompt_lead_agent.txt')
# This is the agent memory that is stored for the agent handling and creating tickets
OPS_TICKET_CREATOR_MEMORY_PROMPT_FPATH: str = os.path.join(OPS_ORCHESTRATOR_AGENT_MEMORY_PROMPT_FPATH, 'ticket_creator_agent_memory.txt')
# This is the agent memory responsible for chat operations and report generation
OPS_CHAT_REPORT_MEMORY_PROMPT_FPATH: str = os.path.join(OPS_ORCHESTRATOR_AGENT_MEMORY_PROMPT_FPATH, 'chat_report_agent_memory.txt')

# Gateway configuration constants
# This is the gateway information for the monitoring agent
OPS_ORCHESTRATOR_GATEWAY_NAME = "OpsOrchestratorAgentGW"
OPS_ORCHESTRATOR_GATEWAY_DESC: str = "Gateway for the ops orchestrator agent"
OPS_ORCHESTRATOR_GATEWAY_CREDENTIALS_PATH = "mcp_credentials.json"
REGION_NAME = boto3.Session().region_name
ACCOUNT_ID = boto3.client("sts").get_caller_identity()["Account"]
EXECUTION_ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/GenesisGatewayExecutionRole"
LAMBDA_ARN = f"arn:aws:lambda:{REGION_NAME}:{ACCOUNT_ID}:function:AgentGatewayFunction"

# This is the prompt template directory for the agents
PROMPT_TEMPLATE = config_data['agent_information']['prompt_templates']
PROMPT_TEMPLATE_DIR = PROMPT_TEMPLATE['prompt_template_dir']