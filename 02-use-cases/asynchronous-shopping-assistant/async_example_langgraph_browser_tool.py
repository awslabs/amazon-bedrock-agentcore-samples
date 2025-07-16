
from typing import Annotated

from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict
import time
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_community.agent_toolkits import FileManagementToolkit
from tempfile import TemporaryDirectory
import random
import threading
import logging
import uuid
import os
import json
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
in_memory_store = InMemoryStore()

langchain_logger = logging.getLogger("langchain")
langchain_logger.setLevel(logging.DEBUG)

from nova_act import NovaAct



import asyncio
from bedrock_agentcore.identity.auth import requires_access_token, requires_api_key


@requires_api_key(
    provider_name="NovaActAPIkey" # replace with your own credential provider name
)
async def need_api_key(*, api_key: str):
    print(f'received api key')
    os.environ["NOVA_ACT_API_KEY"]=api_key


try:
    print("Trying to get NOVA_ACT_API_KEY from Bedrock Agentcore Credential provider")    
    asyncio.run(need_api_key(api_key=""))
except Exception as e:
    print(e)
    print("Assuming your NOVA_ACT_API_KEY env var is set up")    

# Exclude ping from obs traces
os.environ["OTEL_PYTHON_EXCLUDED_URLS"]="/ping"
os.environ["OTEL_PYTHON_STARLETTE_EXCLUDED_URLS"]="/ping"
os.environ["OTEL_PYTHON_FASTAPI_EXCLUDED_URLS"]="/ping"



working_directory = TemporaryDirectory()
print(working_directory)
toolkit = FileManagementToolkit(
    root_dir=str(working_directory.name)
)  
file_tools= toolkit.get_tools()

import asyncio


from bedrock_agentcore.runtime.models import PingStatus
from bedrock_agentcore.tools.browser_client import BrowserClient, browser_session


import logging
langchain_logger = logging.getLogger("langchain")
langchain_logger.setLevel(logging.DEBUG)
import os
print("Starting up...")


# ---------- Agentcore imports --------------------
from bedrock_agentcore.runtime import BedrockAgentCoreApp
app = BedrockAgentCoreApp()
#------------------------------------------------



from langchain import PromptTemplate

system_prompt = """You are a shopping assistant with access to a backgorund agent that can
asynchronously help shop for products users are interested in on amazon.com. You research
amazon.com for product details and respond. Remember that the browser tool can run for a long time,
do not try to retrieve results direcrly. Wait for some time before trying to look at results.
You also have access to file system tools, and a tool to manage background tasks. While the background
task is running, DO NOT try to retrieve results (confirm to the user that the background task is running
and wait to check for it later). DO NOT try to provide general infomation instead, if background browser
tool is still running. At the end of the web browser task, the sub agent will write a local file in the 
format 'result_<session_id>.txt' that you can read results from. If the user requests for multiple products,
you can fire off separate browser tool calls in parallel, otherwise, fire off a single session and wait. Be patient, 
browser tool based research can take some time.  Special case: when the user asks for a comparison between products,
    you can call multiple browser sessions in parallel, or back to back; they can progress simultaneously. Lastly, if the user asks for 'results' or asks for what the results of the search
task were, check if any background tasks are running, if one was alreacy run and completed, look for the results file. In all cases,
remember that the browser tool takes time to run, sometimes over 10 mins. DO NOT expect to see results immediately. In the past
you tended to start browser sessions, and check for results immediately. DO NOT repeat this mistake; call the browser tool and wait, do not relaunch the search immediately.
"""

llm = init_chat_model(
    "us.anthropic.claude-3-5-haiku-20241022-v1:0",
    model_provider="bedrock_converse",)



print("Defining state...")
## Define state
class State(TypedDict):
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)


async def chatbot(state: State):
    print("In chatbot")
    messages = [{"role": "system", "content": system_prompt}] + state["messages"]
    async for chunk in llm_with_tools.astream(messages):

        if chunk.content and len(chunk.content) > 0:
            try:
                text = chunk.content[0].get('text', '')
                if text:
                    # Process or accumulate the text here
                    print(f"Extracted text: {text}")
                    yield text
            except Exception as e:
                print(f"Error processing chunk: {e}")
    else:
        print("Empty content or no text in this chunk")



def _run_browser_task(request: str):
    
    
    with browser_session('us-west-2') as client:
        print("Browser session started... waiting for it to be ready.")
        time.sleep(5)  # Wait for the browser session to be ready
        ws_url, headers = client.generate_ws_headers()

        #generate a random number for port to avoid conflicts
        port = random.randint(8000, 9000)

        #Start viewer server
        # viewer = BrowserViewerServer(client, port=port)
        # viewer_url = viewer.start(open_browser=True)
        starting_url="https://www.amazon.com"
        

        task_id = app.add_async_task("using_browser_tool")
        print(task_id)

        print("Starting Nova act ...")
        with NovaAct(
            cdp_endpoint_url=ws_url,
            cdp_headers=headers,
            preview={"playwright_actuation": True},
            nova_act_api_key=os.environ["NOVA_ACT_API_KEY"],
            starting_page=starting_url,
        ) as nova_act:
            result = nova_act.act(prompt=request, max_steps=5)

            print(result)
            
            print("Writing response locally...")
            print(result.response)

            filename = f"./result_{result.metadata.session_id}.txt"

            print(f"writing in - {filename}")
            with open(filename,'w') as f:
                f.write(f"Session ID: {str(result.metadata.session_id)}\n")
                f.write(f"Act ID: {str(result.metadata.act_id)}\n")
                f.write(f"Prompt: {str(result.metadata.prompt)}\n")
                f.write(f"Response: {str(result.response)}\n")
  
            success = app.complete_async_task(task_id)
            print(f"[Processor {task_id}] Task completion: {'SUCCESS' if success else 'FAILED'}")
            




def call_browser_tool(state: State):
    """Call the browser tool with a web task to perform. You can provide a simple high level task, which is
    completed asynchronously by a sub agent. Prompt the browser agent via the task description that the response
    should be detailed. At the end of the web browser task, the sub agent will write a 
    local file in the format 'result_<session_id>.txt' that you can read results from. Note that browser tool
    can take a while to finish. Notify the user that the browser agent is researching the question, and return
    control to the user so they can ask follow up questions. Special case: when the user asks for a comparison between products,
    you can call multiple browser sessions in parallel, or back to back; they can progress simultaneously."""

    print("In call_browser_tool, state=",state)
    print(state)
    # Sanity check
    print(app.get_async_task_info)

    try:
        print("Starting background thread ...")
        thread = threading.Thread(
            target=_run_browser_task,
            args=(state['messages'][0],),
            daemon=True,
        )
        thread.start()
        print("Started")
                
    except Exception as e:
        print(f"NovaAct error: {e}")

        


    return {"messages": [{"role": "tool", "content": "running browser search"}]}

def get_tasks_info(state: State):
    """Get status of running web search tasks"""
    task_info = app.get_async_task_info()
    return {"message": "Current task information", "task_info": task_info}

tools = [call_browser_tool, get_tasks_info]+file_tools
llm_with_tools = llm.bind_tools(tools)

print("Configuring graph...")
graph_builder.add_node("chatbot", chatbot)

tool_node = ToolNode(tools=tools)

graph_builder.add_node("tools", tool_node)

graph_builder.add_conditional_edges(
    "chatbot",
    tools_condition,
)
# Any time a tool is called, we return to the chatbot to decide the next step
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "chatbot")

checkpointer = InMemorySaver()

graph = graph_builder.compile(checkpointer=checkpointer, store=in_memory_store)
graph_configured = True
    

# ---------- Genesis Entrypoint --------------------------

@app.entrypoint
async def agent_invocation(payload, context):
    
    print("received payload")
    print(payload)
    
    tmp_msg = {"messages": [{"role": "user", "content": payload.get("prompt", "No prompt found in input, please guide customer as to what tools can be used")}]}
    
    # async for chunk in graph.astream(tmp_msg, stream_mode="updates"):
    #     # {'chatbot': {'messages': [AIMessage(content=[{'type': 'text', 'text':
    #     message_content = chunk['chatbot']['messages'][0].content if chunk.get('chatbot', {}).get('messages') and len(chunk['chatbot']['messages']) > 0 else ""
    #     yield message_content
    config = {"configurable": {"thread_id": payload.get("thread_id", context.session_id)}}
    print("In ep")
    async for chunk in graph.astream(tmp_msg, stream_mode="messages", config=config):
        try:
            
            print("----")
            print(chunk)
            print("----")
            yield chunk['chatbot']['messages'][0].content
        except Exception as e:
            print(e)

        # TODO - fix streaming

        # if 'chatbot' in chunk and 'messages' in chunk['chatbot'] and chunk['chatbot']['messages']:
        #     message_content = chunk['chatbot']['messages'][0].content
            
        #     # Format the output based on content type
        #     if isinstance(message_content, list):
        #         for item in message_content:
        #             if item.get('type') == 'text':
        #                 # Just yield the text content
        #                 yield item.get('text', '')
        #             elif item.get('type') == 'tool_use':
        #                 # Format tool use in a cleaner way
        #                 tool_name = item.get('name', 'unknown_tool')
        #                 yield f"\n[Using tool: {tool_name}]\n"
        #     else:
        #         # If it's just a string, yield it directly
        #         yield message_content

app.run()
