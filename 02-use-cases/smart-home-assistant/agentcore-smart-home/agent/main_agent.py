import os
import json
import asyncio
import logging
import boto3
import requests
import time
import uuid
from datetime import timedelta

from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models.bedrock import BedrockModel
from strands_tools import current_time
from strands.tools.mcp.mcp_client import MCPClient

from mcp.client.streamable_http import streamablehttp_client
from memory import UserMemoryHooks

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Camera configuration
CAMERA_ROLE_ARN = os.getenv("CAMERA_ROLE_ARN")
CAMERA_REGION = os.getenv("CAMERA_REGION")
CLIP_BUCKET = os.getenv("CLIP_BUCKET")
AWS_REGION = os.getenv("AWS_REGION")
DYNAMO_TABLE = os.getenv("DYNAMO_TABLE")
SECRET_ARN = os.getenv("COGNITO_CONFIG_SECRET_ARN")
MEMORY_ID = os.getenv("MEMORY_ID")
prompt_id = ""

# Initialize AgentCore app
app = BedrockAgentCoreApp()

# Initialize AWS clients
secrets_client = boto3.client('secretsmanager')

# Initialize Bedrock model
model = BedrockModel(
    model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    #model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    max_tokens=500,
)

SYSTEM_PROMPT = """        
You are an intelligent orchestrator agent that helps users with various home automation tasks.

You have access to several tools:
- Camera data queries: Use the MCP server to convert natural language to SQL and query camera database
- Temperature monitoring: Get current temperature readings
- Weather information: Get current weather conditions  
- Time utilities: Get current time and date

When users ask questions, use the appropriate tools to provide helpful and accurate responses.
Always provide clear, helpful responses based on the tool results.
"""


# Initialize AWS clients for camera access
def initialize_aws_clients():
    try:
        from aws import session_manager, kvs_client, s3_client, dynamo_client

        session_manager.initialize_session_manager(CAMERA_ROLE_ARN)
        kvs_client.initialize_kvs_client(region=CAMERA_REGION)
        s3_client.initialize_s3_client(clip_bucket=CLIP_BUCKET, region=AWS_REGION)
        dynamo_client.initialize_dynamo_client(table_name=DYNAMO_TABLE)
        logger.info("AWS clients initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize AWS clients: {e}")
        logger.warning("Camera clip functionality may not work")


def get_current_timestamp():
    return int(time.time())

def get_cognito_config():
    """Get Cognito configuration from AWS Secrets Manager"""
    try:
        response = secrets_client.get_secret_value(SecretId=SECRET_ARN)
        return json.loads(response['SecretString'])
    except Exception as e:
        logger.error(f"Error getting Cognito config from secrets: {e}")
        return None


def get_token(user_pool_id: str, client_id: str, client_secret: str, scope_string: str, region: str) -> dict:
    try:
        user_pool_id_without_underscore = user_pool_id.replace("_", "")
        url = f"https://{user_pool_id_without_underscore}.auth.{region}.amazoncognito.com/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope_string,
        }
        
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as err:
        logger.error(f"Error getting token: {err}")
        return {"error": str(err)}
    


def tool_search(gateway_endpoint, jwt_token, query):
    requestBody = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "x_amz_bedrock_agentcore_search",
            "arguments": {"query": query},
        },
    }
    response = requests.post(
        gateway_endpoint,
        json=requestBody,
        headers={
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
        },
    )

    toolResp = response.json()
    tools = toolResp["result"]["structuredContent"]["tools"]
    return tools


@tool
async def query_camera_data(question) -> str:
    """
    Query camera data using the MCP Gateway
    
    Args:
        question: Natural language question about camera data
        
    Returns:
        Query results as a string
    """
    
    # Get Cognito configuration
    config = get_cognito_config()
    if not config:
        return "Error: Could not retrieve Cognito configuration"

    # Get MCP server URL from environment
    mcp_server_url = config['mcp_server_url']
    if not mcp_server_url:
        return "Error: MCP_SERVER_URL environment variable not set"

    # Get authentication token
    token_response = get_token(
        config['user_pool_id'],
        config['client_id'], 
        config['client_secret'],
        config['scope_string'],
        config['region']
    )
    
    if 'error' in token_response:
        return f"Error getting authentication token: {token_response['error']}"
    
    bearer_token = token_response.get('access_token')
    if not bearer_token:
        return "Error: No access token received"
    
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    
    logger.info('Searching for MCP Tools')
    tool_search_resp = tool_search(mcp_server_url, bearer_token, "sql to athena tool")
    tool_resp_mcp = tool_search_resp[0]['name']

    if not tool_resp_mcp:
        return f"Tool not found. Available tools: {tool_search_resp}"

    try:
        def create_transport():
            return streamablehttp_client(
                mcp_server_url, 
                headers=headers
            )
        
        client = MCPClient(create_transport)
        
        with client:
            
            # Call the text-to-SQL tool
            result = client.call_tool_sync(
                #tool_use_id="process_text_to_athena_1", # replace uuid
                tool_use_id=str(uuid.uuid4()),
                name=tool_resp_mcp,
                arguments={"question": question}
            )
            
            if result and hasattr(result, 'content') and result.content:
                return result.content[0].text
            else:
                print(f'Else return: {result}')
                return result
                    
    except Exception as e:
        logger.error(f"Error calling MCP Gateway: {e}")
        return f"Error querying camera data: {str(e)}"


@tool
def get_camera_clip(camera, start_timestamp, end_timestamp) -> str:
    """Generate a video clip from camera footage for a specific time period.

    IMPORTANT CONSTRAINTS:
    - Duration (end - start) MUST be between 5 and 180 seconds
    - Maximum: 3 minutes. Longer requests WILL FAIL.
    - For longer footage, make multiple calls with 3-minute segments

    Args:
        camera: The camera location to get footage from (backyard)
        start_timestamp: Start time (ISO8601: 'YYYY-MM-DDTHH:MM:SSZ'). Example: '2023-05-01T14:25:00Z'
        end_timestamp: End time (ISO8601: 'YYYY-MM-DDTHH:MM:SSZ'). Must be 5-180 seconds after start_timestamp.
        prompt_id: Prompt ID - Unique identifier, get it from get_prompt_id() function

    Returns:
        String with the URL to the generated video clip or error message
    """
    from services.camera_service import generate_camera_clip
    from aws.dynamo_client import insert_item

    initialize_aws_clients()

    # Validate camera
    valid_cameras = ["backyard"]
    if camera not in valid_cameras:
        return f"Invalid camera location. Must be one of: {', '.join(valid_cameras)}"

    try:
        logger.info(f"Generating clip for camera: {camera} ({start_timestamp} to {end_timestamp})")

        # Generate clip using camera service
        result = generate_camera_clip(camera, start_timestamp, end_timestamp)

        # If URL is not generated
        if 'url' not in result:
            logger.error(f"No URL generated for camera: {camera} | Error: {result}")
            return f"Failed to generate clip on get_camera_clip(): {result}"

        timestamp = get_current_timestamp()
        
        global prompt_id
        if prompt_id == "":
            return "Prompt_ID not captured to generate the clip"
        
        dynamo_data = {
            "prompt_id": prompt_id,
            "timestamp": timestamp,
            "s3_uri": result
        }

        resp = insert_item(dynamo_data)
        logger.info(f"Data inserted on Dynamo: {resp}")

        # Handle result
        if "error" in result:
            return f"Error: {result['error']}"
        elif "url" in result:
            #return f"Video clip generated successfully! Download URL: {result['url']}"
            #return f"Video clip generated successfully! Download available for: {prompt_id}"
            return f"Video clip generated successfully! Pre-Signet URL available."
        else:
            return f"Unexpected result from camera service: {result}"

    except Exception as e:
        logger.error(f"Error generating clip for camera '{camera}': {str(e)}")
        return f"Failed to generate clip: {str(e)}"


@tool
def get_temperature() -> str:
    """Get current temperature"""
    # Simple mock implementation - replace with actual sensor data
    return "Current temperature: 22°C"


@tool
def get_weather() -> str:
    """Get current weather information"""
    # Simple mock implementation - replace with actual weather API
    return "Current weather: Sunny, 22°C, light breeze"


agent = Agent(
    #hooks=[support_hooks],
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[query_camera_data, get_camera_clip, get_temperature, get_weather, current_time],
)


@app.entrypoint
async def invoke(payload):
    logger.info(f'Payload: {payload}')

    user_message = payload.get("prompt", "Hello! How can I help you with camera data?")
    logger.info(f"Processing query: {user_message}")

    session_id = payload.get("session_id")
    if not session_id:
        logger.error(f"Request with no session_id")
        raise Exception("Request with no session_id")

    user_email = payload.get("user_email")
    if not user_email:
        logger.error(f"Request with no user_id")
        raise Exception("Request with no user_id")

    prompt_uuid = payload.get("prompt_uuid")
    global prompt_id
    prompt_id = prompt_uuid
    if not prompt_id:
        logger.error(f"Request with no prompt_uuid")
        raise Exception("Request with no prompt_uuid")

    support_hooks = UserMemoryHooks(MEMORY_ID)
    logger.info(f"Memory hooks: {support_hooks}")
    
    # add state
    agent.state.set("actor_id", user_email) 
    agent.state.set("session_id", session_id)
    # add memory hook
    agent.hooks.add_hook(support_hooks)

    # Stream the response
    tool_active = False
    async for item in agent.stream_async(user_message):
        if 'event' in item:
            event = item['event']
            # Check for tool start
            if 'contentBlockStart' in event and 'toolUse' in event['contentBlockStart'].get('start', {}):
                tool_active = True
                event_formatted = {
                    'event': event
                }
                yield json.dumps(event_formatted) + "\n"
            # Check for tool end
            elif 'contentBlockStop' in event and tool_active:
                tool_active = False
                event_formatted = {
                    'event': event
                }
                yield json.dumps(event_formatted) + "\n"
        elif 'start_event_loop' in item:
            yield json.dumps(item) + "\n"
        elif 'current_tool_use' in item and tool_active:
            yield json.dumps(item['current_tool_use']) + "\n"
        elif 'data' in item:
            yield json.dumps({"data": item['data']}) + "\n"

# Local Test
# async def main(prompt):
#    async for response in invoke(
#         {
#             "prompt": prompt,
#             "session_id": "0a7cde91-bad9-4b93-b49b-161ca9143b23",
#             "user_email": "anybody@amazon.com",
#             "prompt_uuid": "6747925e-4e3d-41d6-a59f-dd320360f2de"
#         }
#    ):
#       print(response, end='')

if __name__ == "__main__":
    app.run()
    # Local Test
    #asyncio.run(main("How is weather today?"))
    #asyncio.run(main("Find latest event in cameras"))
    #asyncio.run(main("show me the backyard 12:14-12:16 yesterday."))