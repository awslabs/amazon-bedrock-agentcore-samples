# Observability Integrations

This section contains standalone Python examples showing how to connect Amazon Bedrock AgentCore with third-party observability platforms using OpenTelemetry.

Each integration follows the same pattern: an OTel configuration module, a Strands-based travel agent, and a `main.py` entry point. All examples use [uv](https://docs.astral.sh/uv/) for dependency management.

## Available Integrations

| Integration | Description |
|-------------|-------------|
| [Dash0](./dash0/) | OpenTelemetry-native observability — traces and metrics via OTLP HTTP |
| [Dynatrace](./dynatrace/) | Application performance monitoring via OTLP HTTP |
| [OpenLIT](./openlit/) | Open-source LLM observability platform |
| [Simple Dual Observability](./simple-dual-observability/) | Amazon CloudWatch and Braintrust side-by-side with automatic OTel instrumentation |

## Getting Started

Each integration directory contains its own `README.md` with setup instructions. The general steps are:

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
2. Set the required environment variables (see each integration's README)
3. Run with `uv run main.py`

## Prerequisites

- Python 3.10+
- AWS credentials configured with Bedrock access
- An account on the observability platform of your choice

## Related Resources

- [AgentCore Runtime Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/userguide/runtime.html)
- [Partner Observability Tutorials](../../01-tutorials/06-AgentCore-observability/04-Agentcore-runtime-partner-observability/)
