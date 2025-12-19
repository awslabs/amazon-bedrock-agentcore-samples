import os
import datetime  
import json
import asyncio
import traceback
import requests

from strands import Agent
from strands import tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_access_token
from strands.models.bedrock import BedrockModel

os.environ["STRANDS_OTEL_ENABLE_CONSOLE_EXPORT"] = "true"
os.environ["OTEL_PYTHON_EXCLUDED_URLS"] = "/ping,/invocations"

SCOPES = [f'api://fec53ef5-97d8-41a2-a604-ae8fab22ec51/read']
SCOPES = os.environ["scope"]

entra_access_token = None  # Global variable to store the access token
tool_name = None


@tool
def create_notebook(name: str) -> str:
    """
    Create a new Microsoft OneNote notebook for the user. Needed before you can create a section or add content.
    
    Args:
        name (str): The display name for the new notebook
        
    Returns:
        str: The ID of the created notebook
    """
    global entra_access_token
    global tool_name 
    tool_name = "create_notebook"
    # Check if we already have a token
    if not entra_access_token:
        return json.dumps({"auth_required": True, "message": f"Entra ID authentication is required for {tool_name}. Please wait while we set up the authorization.", "events": []})

    headers = {
        'Authorization': f'Bearer {entra_access_token}',
        'Content-Type': 'application/json'
    }
    # Create new notebook
    notebook_data = {'displayName': name}
    notebook = requests.post('https://graph.microsoft.com/v1.0/me/onenote/notebooks', 
                            headers=headers, json=notebook_data)
    return json.dumps({"notebook_id": notebook.json()['id']})

@tool
def create_notebook_section(notebook_id: str, section_name: str) -> str:
    """
    Create a new section in an existing OneNote notebook. Section is created for a specific notebook. 
    
    Args:
        notebook_id (str): The ID of the OneNote notebook to create the section in
        section_name (str): The display name for the new section
        
    Returns:
        str: The ID of the created section
    """
    global entra_access_token
    global tool_name 
    tool_name = "create_notebook_section"
    # Check if we already have a token
    if not entra_access_token:
        return json.dumps({"auth_required": True, "message": f"Entra ID authentication is required for {tool_name}. Please wait while we set up the authorization.", "events": []})

    headers = {
        'Authorization': f'Bearer {entra_access_token}',
        'Content-Type': 'application/json'
    }
    # Create new section
    section_data = {'displayName': section_name}
    section = requests.post(f'https://graph.microsoft.com/v1.0/me/onenote/notebooks/{notebook_id}/sections',
                           headers=headers, json=section_data)
    section_id = section.json()['id']
    return json.dumps({"section_id": section_id})

@tool
def add_content_to_notebook_section(section_id: str, page_content) -> str:
    """
    Add content to a OneNote notebook section by creating a new page.
    
    Args:
        section_id (str): The ID of the OneNote section to add content to
        page_content: The HTML content to add as a new page
        
    Returns:
        str: URL to the created notebook page
    """
    global entra_access_token
    global tool_name 
    tool_name = "add_content_to_notebook_section"
    
    # Check if we already have a token
    if not entra_access_token:
        return json.dumps({"auth_required": True, "message": f"Entra ID authentication is required for {tool_name}. Please wait while we set up the authorization.", "events": []})

    headers = {
        'Authorization': f'Bearer {entra_access_token}',
        'Content-Type': 'text/html'
    }
    page = requests.post(f'https://graph.microsoft.com/v1.0/me/onenote/sections/{section_id}/pages',
                        headers=headers, data=page_content)
    url = json.loads(page.text)["links"]["oneNoteWebUrl"]["href"]
    return json.dumps({"oneNoteWebUrl": url})
    
    
# Initialize the agent with tools
model = BedrockModel(model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0")
system_prompt = """You are an Agent who helps user put in their meeting into OneNote notebooks. 
    Identify the notebook name, section name and content based on what the user has provided. 
    Return notebook URL once created."""
agent = Agent(model=model, system_prompt=system_prompt, tools=[create_notebook, create_notebook_section, add_content_to_notebook_section])

# Initialize app and streaming queue
app = BedrockAgentCoreApp()

class StreamingQueue:
    def __init__(self):
        self.finished = False
        self.queue = asyncio.Queue()
        
    async def put(self, item):
        await self.queue.put(item)

    async def finish(self):
        self.finished = True
        await self.queue.put(None)

    async def stream(self):
        while True:
            item = await self.queue.get()
            if item is None and self.finished:
                break
            yield item

queue = StreamingQueue()

async def on_auth_url(url: str):
    print(f"Authorization url: {url}")
    await queue.put(f"Authorization url: {url}")


async def agent_task(user_message: str):
    global tool_name
    try:
        await queue.put("Begin agent execution")
        
        # Call the agent first to see if it needs authentication
        response = agent(user_message)
        
        # Extract text content from the response structure
        response_text = ""
        if isinstance(response.message, dict):
            content = response.message.get('content', [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and 'text' in item:
                        response_text += item['text']
        else:
            response_text = str(response.message)
        
        # Check if the response indicates authentication is required
        # Look for various keywords that indicate authentication issues
        auth_keywords = [
            "authentication", "authorize", "authorization", "auth", 
            "sign in", "login", "access", "permission", "credential",
            "need authentication", "requires authentication"
        ]
        needs_auth = any(keyword.lower() in response_text.lower() for keyword in auth_keywords)
       
        if needs_auth:
            await queue.put(f"Authentication required for {tool_name} access. Starting authorization flow...")
            
            # Trigger the 3LO authentication flow
            try:
                global entra_access_token
                entra_access_token = await need_token_3LO_async(access_token=None)
                await queue.put(f"Authentication successful! Retrying {tool_name}...")
                
                # Retry the agent call now that we have authentication
                response = agent(user_message)
            except Exception as auth_error:
                # print("Exception occurred:")
                # traceback.print_exc()
                print(f"auth_error:", auth_error)
                await queue.put(f"Authentication failed: {str(auth_error)}")
        
        await queue.put(response.message)
        await queue.put("End agent execution")
    except Exception as e:
        await queue.put(f"Error: {str(e)}")
    finally:
        await queue.finish()

@requires_access_token(
    provider_name="ms_entra_oauth_provider",
    scopes=[os.environ["scope"]],
    auth_flow='USER_FEDERATION',
    on_auth_url=on_auth_url,
    force_authentication=True,
)
async def need_token_3LO_async(*, access_token: str):
    global entra_access_token
    entra_access_token = access_token  # Update the global access token
    print("Got access token....", access_token)
    return access_token

from fastapi.responses import StreamingResponse

@app.entrypoint
async def agent_invocation(payload):
    user_message = payload.get("prompt", "No prompt found in input, please guide customer to create a json payload with prompt key")
    
    # Create and start the agent task
    task = asyncio.create_task(agent_task(user_message))
    
    """# Stream results as they come
    async for item in queue.stream():
        yield f"data: {json.dumps({'message': str(item)})}\n\n"
    
    # Ensure the task completes
    await task"""

    # Return the stream, but ensure the task runs concurrently
    async def stream_with_task():
        # Stream results as they come
        async for item in queue.stream():
            yield item
        
        # Ensure the task completes
        await task
    
    return stream_with_task()
    
if __name__ == "__main__":
    app.run()
