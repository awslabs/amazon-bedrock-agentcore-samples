###########################
#### Agent Code below: ####
###########################
import os
import asyncio
import logging
from llama_index.observability.otel import LlamaIndexOpenTelemetry
from llama_index.llms.bedrock_converse import BedrockConverse
from llama_index.core.agent.workflow import FunctionAgent

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
query = """What is (121 + 2) * 5?"""

async def main():
    result = await agent.run(query)
    print("Result:", str(result))

asyncio.run(main())
