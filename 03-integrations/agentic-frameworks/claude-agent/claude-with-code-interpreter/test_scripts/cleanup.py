import argparse
import logging
import boto3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
agent_core_client = boto3.client("bedrock-agentcore")
agent_core_control = boto3.client("bedrock-agentcore-control")


def _terminate_code_int(session_id: str):
    logger.info("*" * 80 + "\n")
    logger.info("Cleaning up code interpreter session: %s", session_id)
    response = agent_core_client.stop_code_interpreter_session(
        codeInterpreterIdentifier="aws.codeinterpreter.v1", sessionId=session_id
    )

    logger.info("*" * 80 + "\n")
    logger.info("Terminate code int response: %s", response)


def _stop_runtime_session(agent_arn: str, session_id: str):
    # Stop the runtime session
    response = agent_core_client.stop_runtime_session(
        agentRuntimeArn=agent_arn,
        runtimeSessionId=session_id,
        qualifier="DEFAULT",  # Optional: endpoint name
    )

    logger.info("Session terminated successfully")
    logger.info("Request ID: %s", {response["ResponseMetadata"]["RequestId"]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup Code Interpreter session")
    parser.add_argument("--code_int_session_id", type=str, default="")
    parser.add_argument("--runtime_session_id", type=str, default="")
    args = parser.parse_args()

    logger.info("Cleaning up Code Interpreter session: %s", args.code_int_session_id)
    logger.info("Cleaning up Runtime session: %s", args.runtime_session_id)

    if args.code_int_session_id:
        _terminate_code_int(args.code_int_session_id)

    if args.runtime_session_id:
        _stop_runtime_session(args.runtime_session_id)
