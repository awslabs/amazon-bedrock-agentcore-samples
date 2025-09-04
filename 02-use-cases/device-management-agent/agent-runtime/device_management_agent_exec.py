"""
Execution script for Device Management Strands Agent Runtime
Interactive chat interface for testing the deployed agent
"""
import boto3
import utils
import json
from dotenv import load_dotenv
import os
import argparse

# Reading environment variables
load_dotenv()

# Setting up command line arguments
parser = argparse.ArgumentParser(
    prog='device_management_agent_exec',
    description='Execute Device Management Strands Agent',
    epilog='Interactive chat with your deployed agent'
)

parser.add_argument('--agent_arn', help="Agent Runtime ARN", required=True)
parser.add_argument('--session_id', help="Session ID for continuing conversation", default='start')

args = parser.parse_args()

# Validate agent ARN
if not args.agent_arn:
    print("❌ Agent ARN is required. Use --agent_arn parameter")
    exit(1)

print(f"🚀 Connecting to agent: {args.agent_arn}")

# Create AgentCore client
try:
    (boto_session, agentcore_client) = utils.create_agentcore_client()
    # Client for data plane
    agentcore_client = boto_session.client("bedrock-agentcore")
    print("✅ Successfully connected to AWS Bedrock AgentCore")
except Exception as e:
    print(f"❌ Error connecting to AgentCore: {e}")
    exit(1)

sessionId = args.session_id

print("=" * 70)
print("🏠  WELCOME TO DEVICE MANAGEMENT ASSISTANT  🏠")
print("=" * 70)
print("✨ I can help you with:")
print("   📱 List all devices in your system")
print("   ⚙️  Get device settings and configurations") 
print("   📡 Manage WiFi networks on devices")
print("   👥 List users and check user activity")
print("   🔧 Update device configurations")
print()
print("💡 Example commands:")
print("   • 'List all devices'")
print("   • 'Show settings for device DEV001'")
print("   • 'List WiFi networks for Living Room Router'")
print("   • 'Update WiFi SSID to MyNewNetwork on device DEV001'")
print()
print("🚪 Type 'exit' to quit anytime")
print("=" * 70)
print()

# Run the agent in a loop for interactive conversation
while True:
    try:
        user_input = input("👤 You: ").strip()

        if not user_input:
            print("💭 Please enter a message or type 'exit' to quit")
            continue

        if user_input.lower() in ["exit", "quit", "bye", "goodbye"]:
            print()
            print("=" * 50)
            print("👋 Thanks for using Device Management Assistant!")
            print("🎉 Your devices are in good hands!")
            print("=" * 50)
            break

        print("🤖 DeviceBot: ", end="", flush=True)

        try:
            # Invoke the agent
            if sessionId == 'start':
                boto3_response = agentcore_client.invoke_agent_runtime(
                    agentRuntimeArn=args.agent_arn,
                    qualifier="DEFAULT",
                    payload=json.dumps({"prompt": user_input})
                )
            else:
                boto3_response = agentcore_client.invoke_agent_runtime(
                    agentRuntimeArn=args.agent_arn,
                    qualifier="DEFAULT",
                    payload=json.dumps({"prompt": user_input}),
                    runtimeSessionId=sessionId
                )

            # Update session ID
            sessionId = boto3_response['runtimeSessionId']
            
            # Handle streaming response
            if "text/event-stream" in boto3_response.get("contentType", ""):
                content = []
                for line in boto3_response["response"].iter_lines(chunk_size=1):
                    if line:
                        line = line.decode("utf-8")
                        if line.startswith("data: "):
                            line = line[6:]
                            print(line, end="", flush=True)
                            content.append(line)
                print()  # New line after streaming content
            else:
                # Handle non-streaming response
                try:
                    events = []
                    for event in boto3_response.get("response", []):
                        events.append(event)
                except Exception as e:
                    events = [f"Error reading EventStream: {e}"]
                
                for event in events:
                    try:
                        event_data = json.loads(event.decode("utf-8"))
                        if isinstance(event_data, dict):
                            # Pretty print structured responses
                            if 'response' in event_data:
                                print(event_data['response'])
                            else:
                                print(json.dumps(event_data, indent=2))
                        else:
                            print(event_data)
                    except json.JSONDecodeError:
                        print(event.decode("utf-8"))

        except Exception as e:
            print(f"❌ Error invoking agent: {str(e)}")
            print("💡 Please check your agent ARN and try again")

        print()

    except KeyboardInterrupt:
        print()
        print("=" * 50)
        print("👋 Device Management Assistant interrupted!")
        print("🎉 See you next time!")
        print("=" * 50)
        break
    except Exception as e:
        print(f"❌ An unexpected error occurred: {str(e)}")
        print("💡 Please try again or type 'exit' to quit")
        print()

print("🔚 Session ended. Session ID was:", sessionId)