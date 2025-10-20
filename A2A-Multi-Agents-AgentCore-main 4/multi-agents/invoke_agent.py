import boto3
import json
import logging
import requests
import urllib.parse
import os
from typing import Optional, Dict, Any
from boto3.session import Session

logger = logging.getLogger(__name__)

# Get region from environment or default to us-west-2
DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-west-2')

def invoke_monitoring_agent(agent_arn, region, prompt, qualifier="DEFAULT", stream=True):
    """
    Invoke the AgentCore Runtime with boto3 - prints raw text output
    
    Args:
        agent_arn: The ARN of the deployed agent
        region: AWS region where the agent is deployed
        prompt: The prompt to send to the agent
        qualifier: The qualifier for the agent (default: DEFAULT)
        stream: Whether to request streaming response (default: True)
    """
    agentcore_client = boto3.client(
        'bedrock-agentcore',
        region_name=region
    )
    
    # Prepare payload with streaming option
    payload = {
        "prompt": prompt,
        "stream": stream
    }
    
    boto3_response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=agent_arn,
        qualifier=qualifier,
        payload=json.dumps(payload)
    )
    
    print(f"Content Type: {boto3_response.get('contentType', 'unknown')}")
    print("=" * 50)
    
    if "text/event-stream" in boto3_response.get("contentType", ""):
        print("Streaming response:")
        response_content = ""
        for line in boto3_response["response"].iter_lines(chunk_size=1):
            if line:
                line_text = line.decode("utf-8")
                print(f"Raw line: {repr(line_text)}")
                if line_text.startswith("data: "):
                    data_part = line_text[6:]
                    print(f"Data part: {repr(data_part)}")
                    # Try to parse as JSON to extract the actual content
                    try:
                        data_json = json.loads(data_part)
                        if isinstance(data_json, str):
                            # If it's a string, print it directly
                            print(data_json, end='', flush=True)
                            response_content += data_json
                        elif 'text' in data_json:
                            # If it has a text field, print that
                            print(data_json['text'], end='', flush=True)
                            response_content += data_json['text']
                        else:
                            # Otherwise print the data part as is
                            print(data_part, end='', flush=True)
                            response_content += data_part
                    except json.JSONDecodeError:
                        # If it's not JSON, just print the data part
                        print(data_part, end='', flush=True)
                        response_content += data_part
        print("\n")  # Add final newline
        return response_content
    else:
        print("Non-streaming response:")
        response_data = boto3_response.get("response", [])
        print(f"Response type: {type(response_data)}")
        
        response_content = ""
        if hasattr(response_data, '__iter__') and not isinstance(response_data, (str, bytes)):
            # It's an iterable (like EventStream)
            for i, event in enumerate(response_data):
                print(f"Event {i}:")
                print(f"  Type: {type(event)}")
                print(f"  Raw: {repr(event)}")
                
                if hasattr(event, 'decode'):
                    # If it's bytes
                    decoded = event.decode("utf-8")
                    print(f"  Decoded: {repr(decoded)}")
                    print(f"  Text: {decoded}")
                    response_content += decoded
                else:
                    # If it's already a string or other type
                    print(f"  Text: {event}")
                    response_content += str(event)
        else:
            # Direct response
            print(f"Direct response: {repr(response_data)}")
            if isinstance(response_data, bytes):
                decoded = response_data.decode("utf-8")
                print(f"Decoded: {decoded}")
                response_content = decoded
            else:
                print(f"Text: {response_data}")
                response_content = str(response_data)
        
        return response_content
                
def get_http_client_config(region: Optional[str] = None) -> Dict[str, str]:
    """
    Prompt the user to enter discovery URL, client ID, agent ARN, and access token.
    Returns a dictionary with the configuration values.
    """
    if not region:
        region = DEFAULT_REGION
    
    print("\n" + "="*60)
    print("🔧 AGENT RUNTIME HTTP CLIENT CONFIGURATION")
    print("="*60)
    
    # Get discovery URL
    discovery_url = input("\nEnter the Cognito Discovery URL: ").strip()
    if not discovery_url:
        raise ValueError("Discovery URL cannot be empty")
    
    # Get client ID
    client_id = input("Enter the Cognito App Client ID: ").strip()
    if not client_id:
        raise ValueError("Client ID cannot be empty")
    
    # Get agent ARN
    agent_arn = input("Enter the Agent ARN: ").strip()
    if not agent_arn:
        raise ValueError("Agent ARN cannot be empty")
    
    # Get access token
    access_token = input("Enter the Cognito Access Token: ").strip()
    if not access_token:
        raise ValueError("Access token cannot be empty")
    
    return {
        "discovery_url": discovery_url,
        "client_id": client_id,
        "agent_arn": agent_arn,
        "access_token": access_token,
        "region": region
    }

def invoke_agent_http(config: Dict[str, str], prompt: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Invoke the AgentCore Runtime using HTTP client with bearer token authentication.
    
    Args:
        config: Configuration dictionary with discovery_url, client_id, agent_arn, access_token, region
        prompt: The prompt to send to the agent
        verbose: Whether to enable verbose logging
    
    Returns:
        Dictionary containing the response or error information
    """
    region = config.get("region", DEFAULT_REGION)
    bedrock_endpoint = f"https://bedrock-agentcore.{region}.amazonaws.com"
    
    # URL encode the agent ARN
    escaped_agent_arn = urllib.parse.quote(config["agent_arn"], safe='')
    
    # Construct the URL
    url = f"{bedrock_endpoint}/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"
    
    # Set up headers
    headers = {
        "Authorization": f"Bearer {config['access_token']}",
        "X-Amzn-Trace-Id": "agent-invoker-trace-id",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": f"session-{hash(prompt) % 10000000:07d}"
    }
    
    # Enable verbose logging if requested
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger("urllib3.connectionpool").setLevel(logging.DEBUG)
    
    print(f"\n🚀 Invoking agent with prompt: '{prompt[:50]}...'")
    print(f"📡 Region: {region}")
    print(f"🔗 Endpoint: {bedrock_endpoint}")
    
    try:
        # Make the request
        response = requests.post(
            url,
            headers=headers,
            data=json.dumps({"payload": json.dumps({"prompt": prompt})})
        )
        
        # Handle response
        result = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "success": response.status_code == 200
        }
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                result["data"] = response_data
                print(f"✅ Success! Status Code: {response.status_code}")
                if verbose:
                    print(f"📄 Response: {json.dumps(response_data, indent=2)}")
            except json.JSONDecodeError:
                result["data"] = response.text
                print(f"✅ Success! Status Code: {response.status_code}")
                if verbose:
                    print(f"📄 Response (text): {response.text}")
        else:
            try:
                error_data = response.json()
                result["error"] = error_data
                print(f"❌ Error! Status Code: {response.status_code}")
                print(f"🔍 Error Details: {json.dumps(error_data, indent=2)}")
            except json.JSONDecodeError:
                result["error"] = response.text
                print(f"❌ Error! Status Code: {response.status_code}")
                print(f"🔍 Error Details: {response.text}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        error_result = {
            "status_code": None,
            "success": False,
            "error": f"Request failed: {str(e)}"
        }
        print(f"❌ Request failed: {e}")
        return error_result

def get_session_inputs():
    """
    Get session inputs for agent ARN, region, and qualifier
    """
    print("🤖 Multi-turn Agent Conversation")
    print("-" * 40)
    
    # Get agent ARN
    agent_arn = input("Enter the Agent ARN: ").strip()
    while not agent_arn:
        print("Agent ARN cannot be empty.")
        agent_arn = input("Enter the Agent ARN: ").strip()
    
    # Get region
    region = input(f"Enter the AWS region (press Enter for '{DEFAULT_REGION}'): ").strip()
    if not region:
        region = DEFAULT_REGION
    
    # Get qualifier (with default)
    qualifier = input("Enter the qualifier (press Enter for 'DEFAULT'): ").strip()
    if not qualifier:
        qualifier = "DEFAULT"
    
    return agent_arn, region, qualifier

def multi_turn_conversation(agent_arn, region, qualifier):
    """
    Start a multi-turn conversation with the agent
    """
    print(f"\n💬 Starting conversation with agent...")
    print(f"ARN: {agent_arn}")
    print(f"Region: {region}")
    print(f"Qualifier: {qualifier}")
    print("-" * 40)
    print("Type 'quit' or 'exit' to end the conversation")
    print("-" * 40)
    
    while True:
        try:
            # Get user prompt
            prompt = input("\n💭 You: ").strip()
            
            # Check for exit commands
            if prompt.lower() in ['quit', 'exit', 'bye']:
                print("\n👋 Goodbye!")
                break
            
            if not prompt:
                print("Please enter a prompt or type 'quit' to exit.")
                continue
            
            # Invoke agent
            print("\n🤖 Agent is thinking...")
            response = invoke_monitoring_agent(
                agent_arn=agent_arn,
                region=region,
                prompt=prompt,
                qualifier=qualifier
            )
            
            if response:
                print(f"\n🤖 Agent response received")
            else:
                print("\n🤖 Agent: No response received")
            
        except KeyboardInterrupt:
            print("\n\n👋 Conversation interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Continuing conversation...")

def multi_turn_http_conversation(config: Dict[str, str]):
    """
    Start a multi-turn conversation using HTTP client with bearer token auth
    """
    print(f"\n💬 Starting HTTP conversation with agent...")
    print(f"ARN: {config['agent_arn']}")
    print(f"Region: {config['region']}")
    print(f"Discovery URL: {config['discovery_url']}")
    print("-" * 40)
    print("Type 'quit' or 'exit' to end the conversation")
    print("-" * 40)
    
    while True:
        try:
            # Get user prompt
            prompt = input("\n💭 You: ").strip()
            
            # Check for exit commands
            if prompt.lower() in ['quit', 'exit', 'bye']:
                print("\n👋 Goodbye!")
                break
            
            if not prompt:
                print("Please enter a prompt or type 'quit' to exit.")
                continue
            
            # Invoke agent using HTTP client
            print("\n🤖 Agent is thinking...")
            result = invoke_agent_http(config, prompt, verbose=False)
            
            if result["success"]:
                response_data = result.get("data", "No response data")
                print(f"\n🤖 Agent: {response_data}")
            else:
                print(f"\n❌ Agent Error: {result.get('error', 'Unknown error')}")
            
        except KeyboardInterrupt:
            print("\n\n👋 Conversation interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Continuing conversation...")

def main():
    """
    Main function with choice between boto3 and HTTP client approaches
    """
    print("🤖 Agent Runtime Invoker")
    print("="*40)
    print("Choose invocation method:")
    print("1. Boto3 (IAM authentication)")
    print("2. HTTP Client (Bearer token authentication)")
    print("="*40)
    
    choice = input("Enter your choice (1 or 2): ").strip()
    
    if choice == "1":
        # Original boto3 approach
        try:
            agent_arn, region, qualifier = get_session_inputs()
            multi_turn_conversation(agent_arn, region, qualifier)
        except KeyboardInterrupt:
            print("\n\n❌ Operation cancelled by user.")
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    elif choice == "2":
        # New HTTP client approach
        try:
            region = input(f"Enter AWS region (press Enter for '{DEFAULT_REGION}'): ").strip()
            if not region:
                region = DEFAULT_REGION
                
            config = get_http_client_config(region)
            multi_turn_http_conversation(config)
        except KeyboardInterrupt:
            print("\n\n❌ Operation cancelled by user.")
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    else:
        print("❌ Invalid choice. Please run the script again.")

# Interactive usage
if __name__ == "__main__":
    main()