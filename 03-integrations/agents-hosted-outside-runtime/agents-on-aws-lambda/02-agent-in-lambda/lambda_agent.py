"""
Strands agent hosted directly inside AWS Lambda with AgentCore observability.

The agent runs within Lambda's execution environment. Observability is provided
by the AWS Distro for OpenTelemetry (ADOT) — bundled via pip install — combined
with X-Ray active tracing enabled in the Lambda console.

Environment variables required (see README for full list):
    AGENT_OBSERVABILITY_ENABLED=true
    AWS_LAMBDA_EXEC_WRAPPER=/var/task/opentelemetry-instrument
    OTEL_PYTHON_DISTRO=aws_distro
    OTEL_PYTHON_CONFIGURATOR=aws_configurator
    OTEL_TRACES_EXPORTER=otlp
    OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
    OTEL_METRICS_EXPORTER=none
    OTEL_RESOURCE_ATTRIBUTES=service.version=1.0,service.name=<your-service-name>
    OTEL_EXPORTER_OTLP_LOGS_HEADERS=x-aws-log-group=<log-group>,x-aws-log-stream=otel,x-aws-metric-namespace=<namespace>
"""

import logging

from strands import Agent

logger = logging.getLogger()
logger.setLevel("INFO")

# Initialize the Strands agent once at module load time (outside the handler)
# so it is reused across warm Lambda invocations.
agent = Agent()


def handler(event, context=None):
    """Lambda handler — invoke the Strands agent with the incoming prompt."""
    logger.debug("Event: %s", event)
    logger.debug("Context: %s", context)

    user_message = event.get("prompt", "Hello! How can I help you today?")
    logger.info("User message: %s", user_message)

    result = agent(user_message)
    return {"result": result.message}


if __name__ == "__main__":
    payload = {"prompt": "How far is the Moon from Earth?"}
    print(handler(payload))
