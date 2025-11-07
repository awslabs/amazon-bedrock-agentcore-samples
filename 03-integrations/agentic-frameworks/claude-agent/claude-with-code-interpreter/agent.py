from code_int_mcp.server import code_int_mcp_server
from claude_agent_sdk import (
    AssistantMessage,
    UserMessage,
    ResultMessage,
    ClaudeAgentOptions,
    TextBlock,
    ToolUseBlock,
    ClaudeSDKClient,
    ToolResultBlock
)
from bedrock_agentcore.runtime import BedrockAgentCoreApp
import logging
import json

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

@app.entrypoint
async def main(payload):
    """
        Entrypoint to the agent. Takes the user prompt, uses code interpreter tools to execute the prompt.
        Yields intermediate responses for streaming.
    """
    prompt = payload["prompt"]
    session_id = payload.get("session_id", "")

    # Variables to capture response
    agent_responses = []
    code_int_session_id = session_id

    options = ClaudeAgentOptions(
            mcp_servers={"codeint": code_int_mcp_server},
            model="global.anthropic.claude-sonnet-4-5-20250929-v1:0",
            allowed_tools=["mcp__codeint__execute_code","mcp__codeint__execute_command","mcp__codeint__write_files","mcp__codeint__read_files"],
            system_prompt=f"""You are an AI assistant with access to code execution tools.

  CRITICAL RULES:
  1. You MUST use mcp__codeint__execute_code for ALL Python/code execution tasks instead of running commands.
  2. You MUST use mcp__codeint__execute_command for ALL bash/shell commands
  3. You MUST use mcp__codeint__write_files for ALL write file commands
  4. If asked to run code, commands or write files, use the tools without asking for permission
  5. Use the {code_int_session_id} when invoking code interpreter tools to continue the session. Do not make it as 'default. Pass it even if its empty.

  Available tools:
  - mcp__codeint__execute_code: Execute Python/code snippets
  - mcp__codeint__execute_command: Execute bash/shell commands
  - mcp__codeint_write_files command: Execute write file operations. Make a list of path - name of the file, text - contents of the file for all the files and pass it to the tool.
  - mcp__codeint_read_files command: Execute read file operations. Make a list of path - name of the file

  Your response should:
  1. Show the results
  2. Provide a brief explanation
  """
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for msg in client.receive_messages():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, ToolUseBlock):
                        logger.info("*"*80 + "\n")
                        logger.info("TOOL USE: %s", block.name)
                        logger.info("Input Parameters:\n%s", json.dumps(block.input, indent=2))
                        logger.info("*"*80 + "\n")
                        # Yield tool use as a streaming chunk
                        yield {
                            "type": "tool_use",
                            "tool_name": block.name,
                            "session_id": code_int_session_id
                        }
                    elif isinstance(block, TextBlock):
                        logger.info("*"*80 + "\n")
                        logger.info("Agent response: %s", block.text)
                        agent_responses.append(block.text)
                        # Yield text response as a streaming chunk
                        yield {
                            "type": "text",
                            "text": block.text,
                            "session_id": code_int_session_id
                        }
            elif isinstance(msg, UserMessage):
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        if block.content and len(block.content) > 0:
                            if isinstance(block.content[0], dict):
                                text_content = block.content[0].get("text", "")
                                result_data = json.loads(text_content)
                                extracted_session_id = result_data.get("code_int_session_id", "")
                                if extracted_session_id:
                                    code_int_session_id = extracted_session_id
                        logger.info("*"*80 + "\n")
            elif isinstance(msg, ResultMessage):
                logger.info("*"*80 + "\n")
                logger.info("ResultMessage received - conversation complete %s", msg)
                break  # Exit loop when final result is received

    # Yield final response with complete data
    yield {
        "type": "final",
        "response": "\n".join(agent_responses) if agent_responses else "No response from agent",
        "session_id": code_int_session_id
    }


if __name__ == "__main__":
    app.run()