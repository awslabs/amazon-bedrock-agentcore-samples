from bedrock_agentcore.runtime.models import PingStatus
from bedrock_agentcore.tools.browser_client import BrowserClient, browser_session
import logging
import random
import time
import threading


# If you only want debug logging for strands
logging.getLogger("strands.multiagent").setLevel(logging.DEBUG)
logging.basicConfig(
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()]
)

# If you want debug logging everywhere
# logging.basicConfig(level=logging.DEBUG)

import logging
from strands import Agent, tool
from strands.multiagent import GraphBuilder
from strands_tools import file_write, file_read, shell, use_aws
from strands.models import BedrockModel

sonnet = BedrockModel(
    model_id="us.anthropic.claude-3-5-sonnet-20240620-v1:0"
)

haiku = BedrockModel(
    model_id="us.anthropic.claude-3-5-haiku-20241022-v1:0"
)

import os
import glob

os.environ["BYPASS_TOOL_CONSENT"] = "true"
from nova_act import NovaAct
import asyncio

print("Starting up...")


# ---------- Agentcore imports --------------------
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@tool(name="background_shopping", description="Based on the incoming shpping request, this agent-as-a-tool starts a background shopping task and writes a result file when done. The live shopping session can be seen on the Bedrock Agentcore console")
def call_browser_tool(request: str):
    """Call the browser tool with a web task to perform. You can provide a simple high level task, which is
    completed asynchronously by a sub agent. Prompt the browser agent via the task description that the response
    should be detailed. At the end of the web browser task, the sub agent will write a
    local file in the format 'result_<session_id>.txt' that you can read results from. Note that browser tool
    can take a while to finish. Notify the user that the browser agent is researching the question, and return
    control to the user so they can ask follow up questions. Special case: when the user asks for a comparison between products,
    you can call multiple browser sessions in parallel, or back to back; they can progress simultaneously."""

    logging.debug(f"In call_browser_tool, request = {request} ")
    # Sanity check
    logging.debug(app.get_async_task_info())

    try:
        print("Starting background thread ...")
        thread = threading.Thread(
            target=_run_browser_task,
            args=(request + " (do a very quick and brief search, the faster you return search results the better. For example, no need to click into the product description if you see the price on the main search results)",),
            daemon=True,
        )
        thread.start()
        print("Started")

    except Exception as e:
        print(f"NovaAct error: {e}")
    

    return {"messages": [{"role": "tool", "content": "running browser search"}]}


def _run_browser_task(request: str):
    with browser_session("us-west-2") as client:
        print("Browser session started... waiting for it to be ready.")
        time.sleep(5)  # Wait for the browser session to be ready
        ws_url, headers = client.generate_ws_headers()

        # generate a random number for port to avoid conflicts
        port = random.randint(8000, 9000)

        # Start viewer server
        # viewer = BrowserViewerServer(client, port=port)
        # viewer_url = viewer.start(open_browser=True)
        starting_url = "https://www.amazon.com"

        task_id = app.add_async_task("using_browser_tool")
        print(task_id)

        print("Starting Nova act ...")

        try:
            with NovaAct(
                cdp_endpoint_url=ws_url,
                cdp_headers=headers,
                preview={"playwright_actuation": True},
                nova_act_api_key=os.environ["NOVA_ACT_API_KEY"],
                starting_page=starting_url,
            ) as nova_act:
                result = nova_act.act(prompt=request, max_steps=20)

                print(result)

                print("Writing response locally...")
                print(result.response)

                filename = f"/tmp/result_{result.metadata.session_id}.txt"

                print(f"writing in - {filename}")
                with open(filename, "w") as f:
                    f.write(f"Session ID: {str(result.metadata.session_id)}\n")
                    f.write(f"Act ID: {str(result.metadata.act_id)}\n")
                    f.write(f"Prompt: {str(result.metadata.prompt)}\n")
                    f.write(f"Response: {str(result.response)}\n")

                success = app.complete_async_task(task_id)
                print(
                    f"[Processor {task_id}] Task completion: {'SUCCESS' if success else 'FAILED'}"
                )
                return {'status':success, 'location': filename}
        except Exception as e:
            success = app.complete_async_task(task_id)
            return {'status': str(e), 'location': 'please check nova act logs'}


@tool
def get_tasks_info():
    """Get status of running web search tasks and list any result files and Nova Act log files"""
    import os
    
    # Get task info
    task_info = app.get_async_task_info()
    logging.debug(task_info)
    
    # Get result files from /tmp
    result_files = glob.glob("/tmp/result_*.txt")
    logging.debug(result_files)
    
    # Get Nova Act log files from /tmp
    nova_act_logs = []
    
    # Look for Nova Act log directories in /tmp
    tmp_dirs = glob.glob("/tmp/tmp*_nova_act_logs")
    for tmp_dir in tmp_dirs:
        if os.path.isdir(tmp_dir):
            # Look for session directories
            session_dirs = glob.glob(f"{tmp_dir}/*")
            for session_dir in session_dirs:
                if os.path.isdir(session_dir):
                    # Find HTML log files
                    log_files = glob.glob(f"{session_dir}/act_*.html")
                    nova_act_logs.extend(log_files)
    
    tasks_result = {
        "message": "Current task information", 
        "task_info": task_info,
        "result_files": result_files,
        "nova_act_logs": nova_act_logs
    }

    logging.debug(f"Nova Act logs found: {nova_act_logs}")
    return tasks_result

reporting_agent = Agent(name="reporting_assistant", 
                        system_prompt="""You are a report generation agent. Once the shopping session is completed, you can read
                         one or more results_<sessionid>.txt files and respond to the user with the content you see.
                         
                         If no result files are available but Nova Act log files are found, you can read those HTML log files
                         to extract information about the shopping session and provide a summary to the user. These log files
                         are typically located at paths like /tmp/tmp*_nova_act_logs/*/act_*.html and contain detailed
                         information about the browser session. These log files are very large, so do not try to read the 
                         entire file, all at once.""",
                        tools=[file_read, get_tasks_info, shell, file_write],
                        model = haiku)

fronting_agent = Agent(name="fronting_assistant", 
                    system_prompt="""You are a shopping assistant for amazon.com. You receive a request from the user, and answer immediately
                     if it is a generic question, or route to a background shopping agent. If you decide to go on with background 
                     shopping you must return `shop_background.start` in your text response. You may also read any reports or results
                     generated by other agents; this will be in the format `/tmp/result_<session_id>`. 
                     You also have a tool to check the status of running tasks. 
                     
                     DO NOT use the reporting agent tool right after creating a browser session. Ask the user to wait for results. """,
                    tools = [get_tasks_info, file_read],
                    model = sonnet)

shopping_agent = Agent(name="shopping_assistant", 
                    system_prompt="""You are a background shopping assistant. You receive a request from the user, and
                     asynchronously search amazon.com and report back to the customer. Once you start a shopping session, 
                     recognize that this will take a long time to complete. After starting one or more sessions in parallel,
                     return immediately to the user with an appropriate message. 
                     
                     NOTE 1: If a shopping session is running/active, do not start another one unless you need to, or if it is a different shopping request
                     from earlier. 
                    
                     NOTE 2: in case the user asks for a comparison between two (or more) products, start 2 (or more) browser sessions in parallel. 
                    
                     NOTE 3: Do not take a long time to research this; use a maximum of 5 steps to complete the search (where one step is a click, scroll etc);
                     do whatever minimum research required to directly answer the user question. 

                     NOTE 4: DO NOT ask follow up questions, start analyzing the task immediately using the web search tool.
                    
                    Lastly, if the user asks for the status of the search or for a report, use the appropriate tools to assist.""",
                    tools = [call_browser_tool],
                    model = sonnet)




def only_if_shopping_needed(state):
    """Only pass through if shopping is required."""
    logging.debug("---------------------------------------------------------")
    logging.debug(state)
    # Eg. state:

    # GraphState(
    # task='please search for price of echo pop on amazon.com?', 
    # status=<Status.EXECUTING: 'executing'>, 
    # completed_nodes=
    #   {
    #   GraphNode(node_id='start', 
    #   executor=<strands.agent.agent.Agent object at 0xffff828fbfd0>, dependencies=set(), 
    #   execution_status=<Status.COMPLETED: 'completed'>, 
    #   result=NodeResult(result=AgentResult(stop_reason='end_turn', 
    #   message={
    #       'role': 'assistant', 
    #       'content': [{'text': "Certainly! I'd be happy to help you search for the price of the Echo Pop on Amazon.com. To do this, I'll need to use our background shopping agent to perform the search. Let me initiate that process for you.\n\nshop_background.start\n\nI've started a background shopping task to search for the Echo Pop on Amazon.com. This process will take a little time to complete as it needs to access the website and gather the information. \n\nWhile we wait for the results, is there anything specific you'd like to know about the Echo Pop besides its price? For example, are you interested in its features, color options, or customer reviews?"}]}
    logging.debug("---------------------------------------------------------")
    logging.debug(f"task: {state.task}")

    start_node = state.results.get("start")

    # Check if research result contains success indicator
    result_text = str(start_node.result)
    logging.debug("-------!!!-------")
    logging.debug(result_text.lower())
    condition = "shop_background.start" in result_text.lower()
    if condition:
        logging.debug(f"starting shopping task since condition is {condition}")
        print(f"starting shopping task since condition is {condition}")
    else:
        logging.debug(f"not starting shopping task since condition is {condition}")
    logging.debug("-------!!!-------")
    return "shop_background.start" in result_text.lower()


def only_if_background_task_is_done(state):
    tasks = get_tasks_info()
    # Return True if there are no active tasks AND either result files or Nova Act logs are available
    if tasks['task_info']['active_count'] == 0 and (tasks['result_files'] != [] or tasks['nova_act_logs'] != []):
        return True
    else:
        return False

builder = GraphBuilder()

builder.add_node(fronting_agent, "start")
builder.add_node(shopping_agent, "shop")
builder.add_node(reporting_agent, "report")

builder.add_edge("start", "shop", condition=only_if_shopping_needed)
builder.add_edge("start", "report", condition=only_if_background_task_is_done)
builder.set_entry_point("start")

graph = builder.build()

@app.entrypoint
def handler(payload, context):
    if "test" in payload:
        # Directly test nova act
        result = _run_browser_task(request=payload.get("test"))
        return result
    elif "prompt" in payload:
        result = graph(payload.get("prompt"))
        # print(result) # GraphResults object
        return {"result": result.results['start'].result.message}
    else:
        return {"result": "You must provide a `prompt` or `test` key to proceed. ✋"}

app.run()

