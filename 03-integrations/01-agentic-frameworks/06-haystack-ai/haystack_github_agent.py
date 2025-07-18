import os
os.environ["BYPASS_TOOL_CONSENT"]="true"

from haystack.components.agents import Agent
from haystack.dataclasses import ChatMessage
from haystack_integrations.components.generators.amazon_bedrock import AmazonBedrockChatGenerator
from haystack_integrations.tools.github import GitHubIssueViewerTool
from bedrock_agentcore.runtime import BedrockAgentCoreApp

tool = GitHubIssueViewerTool()

# Create the agent with the web tool
tool_calling_agent = Agent(
    chat_generator=AmazonBedrockChatGenerator(model="us.anthropic.claude-3-7-sonnet-20250219-v1:0"),
    system_prompt="""You're a helpful agent. When asked about GitHub issues, use the github issue viewer tool to find the information and then summarize the findings based on the link provided.""",
    tools=[tool]
)

app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload, context):
    """Handler for agent invocation"""
    payload = payload.get("prompt", "No prompt found in input, please guide customer to create a json payload with prompt key")
    user_message = ChatMessage.from_user(payload)
    result = tool_calling_agent.run(messages=[user_message])
    result = result["messages"][-1].text
    print("context:\n-------\n", context)
    print("result:\n*******\n", result)
    return {"result": result.messages}

app.run()