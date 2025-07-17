"""
Configuration module that reads from the central JSON configuration file
"""
import os
import json
import sys
from pathlib import Path

# Find the project root directory (parent of client directory)
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_FILE = PROJECT_ROOT / "configs" / "bedrock-agentcore-config.json"

# Load configuration from JSON file
try:
    with open(CONFIG_FILE, 'r') as f:
        CONFIG = json.load(f)
except Exception as e:
    print(f"❌ Error loading configuration file: {e}")
    print(f"   Path: {CONFIG_FILE}")
    sys.exit(1)

# Extract values from configuration
DEFAULT_REGION = CONFIG["aws"]["default_region"]
DEFAULT_PROFILE = CONFIG["aws"]["default_profile"]
DEFAULT_ACCOUNT = CONFIG["aws"]["default_account"]

# Get gateway URL from configuration
GATEWAY_ID = CONFIG["bedrock_agentcore"]["production_endpoints"]["gateway_id"]
BEDROCK_AGENTCORE_GATEWAY_URL = CONFIG["bedrock_agentcore"]["production_endpoints"]["gateway_url"]

# Get Lambda Function URL from configuration
try:
    DEFAULT_FUNCTION_URL = CONFIG["environments"]["dev"]["function_url"]
except KeyError:
    print("⚠️  Function URL not found in configuration. Using default.")
    DEFAULT_FUNCTION_URL = "https://ms4tq3xffsg2nbv4e7nflhelte0rkaxl.lambda-url.us-east-1.on.aws"

# Chat Settings
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4000

# Authentication
DEFAULT_TOKEN_FILE = os.path.expanduser("~/.okta_token")

# Timeouts
REQUEST_TIMEOUT = 300
TOOLS_TIMEOUT = 300  # 5 minutes for tool operations

def get_base_url(function_url):
    """Get base URL without /stream suffix"""
    return function_url.replace("/stream", "")

def get_stream_url(function_url):
    """Get streaming URL by adding /stream suffix if not present"""
    base_url = get_base_url(function_url)
    return f"{base_url}/stream"

def get_chat_url(function_url):
    """Get non-streaming chat URL"""
    return get_base_url(function_url) + "/chat"

def get_tools_url(function_url):
    """Get tools fetch URL"""
    return get_base_url(function_url) + "/api/tools/fetch"

def get_conversations_url(function_url):
    """Get conversations list URL"""
    return get_base_url(function_url) + "/api/conversations"

def get_conversation_url(function_url, conversation_id):
    """Get specific conversation URL"""
    return f"{get_base_url(function_url)}/api/conversations/{conversation_id}"

def get_conversation_clear_url(function_url, conversation_id):
    """Get conversation clear URL"""
    return f"{get_base_url(function_url)}/api/conversations/{conversation_id}/clear"

# Print configuration summary
def print_config_summary():
    """Print configuration summary"""
    print(f"📋 Configuration:")
    print(f"   AWS Region: {DEFAULT_REGION}")
    print(f"   AWS Profile: {DEFAULT_PROFILE}")
    print(f"   Lambda Function URL (Base): {DEFAULT_FUNCTION_URL}")
    print(f"   Lambda Function URL (Stream): {get_stream_url(DEFAULT_FUNCTION_URL)}")
    print(f"   Gateway ID: {GATEWAY_ID}")
    print(f"   Gateway URL: {BEDROCK_AGENTCORE_GATEWAY_URL}")
    print(f"   Token File: {DEFAULT_TOKEN_FILE}")
