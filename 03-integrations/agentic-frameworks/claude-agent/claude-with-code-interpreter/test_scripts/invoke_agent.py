import json
import uuid
import boto3
import logging
from botocore.exceptions import ClientError, ReadTimeoutError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

agent_arn = "<agent-arn>"

# Initialize the Amazon Bedrock AgentCore client
agent_core_client = boto3.client("bedrock-agentcore")


def _invoke(prompt: str, session_id: str):
    # Prepare the payload
    runtime_session_id = str(uuid.uuid4())
    payload = json.dumps({"prompt": prompt, "session_id": session_id}).encode()

    logger.info("*" * 80)
    logger.info("Sending request %s", payload)
    logger.info("*" * 80)

    # Invoke the agent
    try:
        response = agent_core_client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=runtime_session_id,
            payload=payload,
            qualifier="DEFAULT",
        )

        # Get the StreamingBody
        streaming_body = response.get("response")
        logger.info("StreamingBody type: %s", type(streaming_body))

        # Variables to accumulate the response
        content = []
        final_response = ""
        final_session_id = ""

        # Stream chunks as they arrive
        logger.info("*" * 80)
        logger.info("Streaming response...")
        logger.info("*" * 80)

        try:
            for chunk in streaming_body.iter_lines():
                if chunk:
                    chunk_str = chunk.decode("utf-8")
                    # logger.info(f"\n********STREAMING CHUNK********* %s",chunk_str)
                    # Skip empty lines or comments
                    if not chunk_str or chunk_str.startswith(":"):
                        continue

                    # Handle SSE format
                    if chunk_str.startswith("data:"):
                        chunk_str = chunk_str.split(":", 1)[1].strip()

                    # Only try to parse if we have content
                    if chunk_str:
                        try:
                            # Try to parse each chunk as JSON
                            chunk_data = json.loads(chunk_str)

                            # Handle different chunk types
                            if chunk_data.get("type") == "text":
                                logger.info("\n TEXT : %s", chunk_data.get("text"))
                            elif chunk_data.get("type") == "tool_use":
                                logger.info(
                                    "\n TOOL USED : %s", chunk_data.get("tool_name")
                                )
                            elif chunk_data.get("type") == "final":
                                logger.info(
                                    "\n FINAL RESPONSE : %s", chunk_data.get("response")
                                )
                                final_response = chunk_data.get("response", "")
                                final_session_id = chunk_data.get("session_id", "")

                            # Combine all chunks to show in the final response.
                            content.append(chunk_str)

                        except json.JSONDecodeError:
                            # If not valid JSON, just accumulate
                            content.append(chunk_str)
        except ReadTimeoutError as e:
            logger.error("Request failed: %s", str(e))
        logger.info("*" * 80)
        logger.info("Streaming complete")
        logger.info("*" * 80)

        return {
            "response": final_response if final_response else "No response received",
            "session_id": final_session_id,
        }

    except ClientError as e:
        logger.error("Request failed: %s", str(e))
        raise


def _cleanup(session_id: str):
    logger.info("*" * 80 + "\n")
    logger.info("Cleaning up code interpreter session")
    ci_client = boto3.client("bedrock-agentcore", "us-west-2")
    response = ci_client.stop_code_interpreter_session(
        codeInterpreterIdentifier="aws.codeinterpreter.v1", sessionId=session_id
    )

    logger.info("*" * 80 + "\n")
    logger.info("Cleanup response.. %s \n", response)


def main():
    # List of prompts to test
    prompts = [
        """
            Write the files in the samples folder into a code interpreter session. 
            Check if they are created. 
            Run data analysis on the data file using the python script.
"""
    ]

    session_id = ""
    for prompt in prompts:
        print(f"\nPrompt: {prompt}")
        result = _invoke(prompt, session_id)
        print(f"\n Final Response: {result['response']}")
        print(f"\n Session ID: {result['session_id']}\n")
        session_id = result["session_id"]

    if session_id:
        _cleanup(session_id)


if __name__ == "__main__":
    main()
