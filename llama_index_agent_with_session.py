import os
import logging
import argparse
import asyncio
from opentelemetry import baggage, context
from llama_index.observability.otel import LlamaIndexOpenTelemetry
from llama_index.llms.bedrock_converse import BedrockConverse
from llama_index.core.agent.workflow import FunctionAgent

def parse_arguments():
    parser = argparse.ArgumentParser(description='LlamaIndex Arithmetic Agent with Session Tracking')
    parser.add_argument('--session-id', 
                       type=str, 
                       required=True,
                       help='Session ID to associate with this agent run')
    return parser.parse_args()

def set_session_context(session_id):
    """Set the session ID in OpenTelemetry baggage for trace correlation"""
    ctx = baggage.set_baggage("session.id", session_id)
    token = context.attach(ctx)
    logging.info(f"Session ID '{session_id}' attached to telemetry context")
    return token

###########################
#### Agent Code below: ####
###########################

# Initialize OpenTelemetry instrumentation for LlamaIndex
instrumentor = LlamaIndexOpenTelemetry(debug=True)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure LlamaIndex logging
logging.getLogger("llamaindex").setLevel(logging.INFO)

def multiply(a: int, b: int) -> int:
    """Multiple two integers and returns the result integer"""
    return a * b

def add(a: int, b: int) -> int:
    """Add two integers and returns the result integer"""
    return a + b

def get_bedrock_model():
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    region = os.getenv("AWS_DEFAULT_REGION", "us-west-2")

    try:
        # Let boto3 handle credential resolution automatically
        bedrock_model = BedrockConverse(
            model=model_id,
            region_name=region,
            # No explicit credentials - boto3 will find them automatically
        )
        logger.info(f"Successfully initialized Bedrock model: {model_id} in region: {region}")
        return bedrock_model
    except Exception as e:
        logger.error(f"Failed to initialize Bedrock model: {str(e)}")
        logger.error("Please ensure you have proper AWS credentials configured and access to the Bedrock model")
        raise

async def run_agent(query):
    # Initialize the model
    bedrock_model = get_bedrock_model()

    # Create the arithmetic agent
    agent = FunctionAgent(
        tools=[add, multiply],
        llm=bedrock_model,
    )

    # Start listening
    instrumentor.start_registering()

    # Execute the arithmetic task
    result = await agent.run(query)
    print("Result:", str(result))
    return result

def main():
    # Parse command line arguments
    args = parse_arguments()

    # Set session context for telemetry
    context_token = set_session_context(args.session_id)

    try:
        # Execute the arithmetic task
        query = """What is (121 + 2) * 5?"""

        # Run the async function in the event loop
        result = asyncio.run(run_agent(query))

    finally:
        # Detach context when done
        try:
            context.detach(context_token)
            logger.info(f"Session context for '{args.session_id}' detached")
        except ValueError as e:
            # Handle the context detachment error that might occur
            logger.error(f"Error detaching context: {str(e)}")

if __name__ == "__main__":
    main()
