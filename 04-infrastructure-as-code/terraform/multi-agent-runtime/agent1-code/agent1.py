from strands import Agent, tool
from typing import Dict, Any
import boto3
import json
import os
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

# Environment variable for Agent2 ARN (will be set by CloudFormation)
AGENT2_ARN = os.getenv('AGENT2_ARN', '')

def invoke_agent2(query: str) -> str:
    """Helper function to invoke agent2 using boto3"""
    import uuid
    try:
        # Get region from environment or use default
        region = os.getenv('AWS_REGION', 'us-west-2')
        agentcore_client = boto3.client('bedrock-agentcore', region_name=region)

        # Invoke agent2 runtime (using AWS sample format)
        response = agentcore_client.invoke_agent_runtime(
            agentRuntimeArn=AGENT2_ARN,
            qualifier="DEFAULT",
            payload=json.dumps({"prompt": query})
        )

        # Handle streaming response (text/event-stream)
        if "text/event-stream" in response.get("contentType", ""):
            result = ""
            for line in response["response"].iter_lines(chunk_size=10):
                if line:
                    line = line.decode("utf-8")
                    # Remove 'data: ' prefix if present
                    if line.startswith("data: "):
                        line = line[6:]
                    result += line
            return result

        # Handle JSON response
        elif response.get("contentType") == "application/json":
            content = []
            for chunk in response.get("response", []):
                content.append(chunk.decode('utf-8'))
            response_data = json.loads(''.join(content))
            return json.dumps(response_data)

        # Handle other response types
        else:
            response_body = response['response'].read()
            return response_body.decode('utf-8')

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return f"Error invoking agent2: {str(e)}\nDetails: {error_details}"

@tool
def call_specialist_agent(query: str) -> Dict[str, Any]:
    """
    Call the specialist agent (agent2) for detailed analysis or complex tasks.
    Use this tool when you need expert analysis or detailed information.

    Args:
        query: The question or task to send to the specialist agent

    Returns:
        The specialist agent's response
    """
    result = invoke_agent2(query)
    return {
        "status": "success",
        "content": [{"text": result}]
    }

def create_orchestrator_agent() -> Agent:
    """Create the orchestrator agent with the tool to call agent2"""
    system_prompt = """You are an orchestrator agent.
    You can handle simple queries directly, but for complex analytical tasks,
    you should delegate to the specialist agent using the call_specialist_agent tool.

    Use the specialist agent when:
    - The query requires detailed analysis
    - The query is about complex topics
    - The user explicitly asks for expert analysis

    Handle simple queries (greetings, basic questions) yourself."""

    return Agent(
        tools=[call_specialist_agent],
        system_prompt=system_prompt,
        name="OrchestratorAgent"
    )

@app.entrypoint
async def invoke(payload=None):
    """Main entrypoint for agent1"""
    try:
        # Get the query from payload
        query = payload.get("prompt", "Hello, how are you?") if payload else "Hello, how are you?"

        # Create and use the orchestrator agent
        agent = create_orchestrator_agent()
        response = agent(query)

        return {
            "status": "success",
            "agent": "agent1",
            "response": response.message['content'][0]['text']
        }

    except Exception as e:
        return {
            "status": "error",
            "agent": "agent1",
            "error": str(e)
        }

if __name__ == "__main__":
    app.run()
