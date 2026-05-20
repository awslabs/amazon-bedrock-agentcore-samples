# Amazon Bedrock Agent Integration with Dash0

This example contains a demo of a Personal Assistant Agent built on top of [Bedrock AgentCore Agents](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) with [Dash0](https://www.dash0.com/) observability.


## Prerequisites

- Python 3.11 or higher
- Dash0 account
- AWS Account with appropriate permissions
- Access to the following AWS services:
  - Amazon Bedrock


## Dash0 Instrumentation

> [!TIP]
> For detailed setup instructions and configuration options, refer to the [Dash0 Documentation](https://dash0.com/docs) and the [Endpoints glossary](https://dash0.com/docs/dash0/miscellaneous/glossary/endpoints).

Bedrock AgentCore comes with [Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html) support out-of-the-box.
We register an [OpenTelemetry SDK](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/overview.md#sdk) to send traces and metrics directly to Dash0 via OTLP HTTP.

All the OTel configuration is encapsulated in [dash0.py](./dash0.py). Configure the following environment variables:

| Variable | Description | Default |
|---|---|---|
| `DASH0_AUTH_TOKEN` | Auth token from **Settings → Auth Tokens** | _(required)_ |
| `DASH0_OTLP_ENDPOINT` | OTLP ingress base URL for your region | `https://ingress.us-west-2.aws.dash0.com` |
| `DASH0_DATASET` | Dataset to route telemetry to | `agentcore` |
| `OTEL_SERVICE_NAME` | Service name shown in traces | `agentcore-dash0-demo` |


## How to use

### 1. Set your AWS credentials

Follow the [Amazon Bedrock AgentCore documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html) to configure your AWS role with the correct policies. Then export your credentials:

```bash
export AWS_ACCESS_KEY_ID=your_access_key_id
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=us-east-1
```

Ensure your account has access to the model `us.anthropic.claude-sonnet-4-5-20250929-v1:0`. You can change the model via the `BEDROCK_MODEL_ID` environment variable.

### 2. Set your Dash0 credentials

1. Sign up for a [Dash0 account](https://www.dash0.com/) if you don't have one.
2. Go to **Settings → Auth Tokens** and create a new token.
3. Go to **Settings → Endpoints** to find your OTLP ingress URL.

```bash
export DASH0_AUTH_TOKEN=your_dash0_auth_token

# Set the endpoint for your region:
# US West 2: https://ingress.us-west-2.aws.dash0.com
# EU West 1: https://ingress.eu-west-1.aws.dash0.com
export DASH0_OTLP_ENDPOINT=https://ingress.us-west-2.aws.dash0.com

export DASH0_DATASET=agentcore
```

### 3. Run the app

```bash
uv run main.py
```

This starts an HTTP server on port `8080` implementing the `/invocations` endpoint required by AgentCore.

### 4. Test locally

```bash
curl -X POST http://127.0.0.1:8080/invocations --data '{"prompt": "What is the weather now?"}'
```

### 5. View traces in Dash0

After invoking the agent, go to [app.dash0.com](https://app.dash0.com/) → **Tracing** and filter by `service.name = agentcore-dash0-demo`. Traces and metrics will appear under the `agentcore` dataset.

### 6. Deploy to AgentCore Runtime

The agent is ready to be packaged as a container and deployed to AgentCore Runtime. Follow the step-by-step guide [here](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/01-AgentCore-runtime/01-hosting-agent/01-strands-with-bedrock-model/runtime_with_strands_and_bedrock_models.ipynb).
