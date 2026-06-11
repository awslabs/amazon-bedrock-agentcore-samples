"""
Strands agent hosted inside AWS Lambda with AgentCore Gen AI observability.

Observability is provided by the AWS ADOT managed Lambda layer — no OTel packages
need to be bundled in the deployment ZIP. The layer auto-instruments the function
and exports traces to CloudWatch via X-Ray.

Required Lambda configuration:
  - Add the ADOT Lambda layer (see README for region-specific ARNs)
  - Enable active X-Ray tracing on the function
  - Set the environment variables listed below

Environment variables:
    AGENT_OBSERVABILITY_ENABLED=true
    AWS_LAMBDA_EXEC_WRAPPER=/opt/otel-instrument
    OTEL_METRICS_EXPORTER=none
"""

import logging

from strands import Agent

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialise the agent once outside the handler so it is reused across warm invocations.
agent = Agent()


def handler(event, context=None):
    """Lambda entry point — forwards the incoming prompt to the Strands agent."""
    prompt = event.get("prompt", "Hello! How can I help you today?")
    logger.info("Received prompt: %s", prompt)

    result = agent(prompt)
    return {"result": result.message}


if __name__ == "__main__":
    print(handler({"prompt": "How far is the Moon from Earth?"}))
