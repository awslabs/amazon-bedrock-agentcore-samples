import os
import logging
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from strands.telemetry import StrandsTelemetry
from ddgs import DDGS

logging.basicConfig(level=logging.ERROR, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("AGENT_RUNTIME_LOG_LEVEL", "INFO").upper())

# Configure OpenTelemetry for Datadog if API key is provided
# This MUST be done BEFORE initializing StrandsTelemetry
dd_api_key = os.getenv("DD_API_KEY")
if dd_api_key:
    os.environ["OTEL_EXPORTER_OTLP_TRACES_PROTOCOL"] = "http/protobuf"
    os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] = "https://trace.agent.datadoghq.com/v1/traces"
    os.environ["OTEL_EXPORTER_OTLP_TRACES_HEADERS"] = f"dd-api-key={dd_api_key},dd-otlp-source=datadog"
    os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"] = "gen_ai_latest_experimental"
    logger.info("✓ Datadog OTLP environment variables configured")
    
    # Initialize StrandsTelemetry at module level (sets up global tracer)
    strands_telemetry = StrandsTelemetry()
    strands_telemetry.setup_otlp_exporter()
    logger.info("✓ Datadog telemetry initialized with OTLP exporter")
else:
    logger.warning("⚠ No DD_API_KEY provided, running without Datadog telemetry")


@tool
def web_search(query: str) -> str:
    """
    Search the web for information using DuckDuckGo.

    Args:
        query: The search query

    Returns:
        A string containing the search results
    """
    try:
        ddgs = DDGS()
        results = ddgs.text(query, max_results=5)

        formatted_results = []
        for i, result in enumerate(results, 1):
            formatted_results.append(
                f"{i}. {result.get('title', 'No title')}\n"
                f"   {result.get('body', 'No summary')}\n"
                f"   Source: {result.get('href', 'No URL')}\n"
            )

        return "\n".join(formatted_results) if formatted_results else "No results found."

    except Exception as e:
        return f"Error searching the web: {str(e)}"

def get_bedrock_model():
    region = os.getenv("AWS_DEFAULT_REGION", "us-west-2")
    model_id = os.getenv("BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0")

    bedrock_model = BedrockModel(
        model_id=model_id,
        region_name=region,
        temperature=0.0,
        max_tokens=1024
    )
    return bedrock_model

bedrock_model = get_bedrock_model()

system_prompt = """You are an experienced travel agent specializing in personalized travel recommendations 
with access to real-time web information. Your role is to find dream destinations matching user preferences 
using web search for current information. You should provide comprehensive recommendations with current 
information, brief descriptions, and practical travel details."""

app = BedrockAgentCoreApp()

def initialize_agent():
    """Initialize the agent (telemetry is already configured at module level)."""
    agent = Agent(
        model=bedrock_model,
        system_prompt=system_prompt,
        tools=[web_search]
    )
    
    return agent

@app.entrypoint
def strands_agent_bedrock(payload, context=None):
    """
    Invoke the agent with a payload
    """
    user_input = payload.get("prompt")
    logger.info("[%s] User input: %s", context.session_id, user_input)
    
    agent = initialize_agent()
    
    response = agent(user_input)
    return response.message['content'][0]['text']

if __name__ == "__main__":
    app.run()
