import os
import openlit


def init():
    """Initialize OpenLIT instrumentation for AgentCore.

    OpenLIT is an open-source self-hosted observability solution.
    No authentication or OTLP headers are required by default.
    """

    # Get OTEL endpoint (defaults to local OpenLIT instance)
    otel_endpoint = os.environ.get(
        "OTEL_ENDPOINT",
        "http://localhost:4318",  # Default to local OpenLIT instance
    )

    # Initialize OpenLIT SDK
    # OpenLIT provides automatic instrumentation for popular LLM frameworks
    # No authentication required for self-hosted deployments
    openlit.init(
        otlp_endpoint=otel_endpoint,
        application_name=os.environ.get("OPENLIT_APP_NAME", "bedrock-agentcore-agent"),
        environment=os.environ.get("OPENLIT_ENVIRONMENT", "production"),
        disable_batch=False,
    )
    print(f"OpenLIT initialized with endpoint: {otel_endpoint}")
