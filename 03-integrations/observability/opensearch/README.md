# Amazon Bedrock AgentCore Integration with OpenSearch

This example contains a demo of a Personal Assistant Agent built on top of [Bedrock AgentCore Agents](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) with [OpenSearch](https://opensearch.org/) observability via [Data Prepper](https://opensearch.org/docs/latest/data-prepper/).


## Prerequisites

- Python 3.11 or higher
- OpenSearch cluster with Data Prepper
- AWS Account with appropriate permissions
- Access to the following AWS services:
   - Amazon Bedrock


## OpenSearch Instrumentation

> [!TIP]
> For detailed setup instructions, configuration options, and advanced use cases, please refer to the [OpenSearch Trace Analytics Documentation](https://opensearch.org/docs/latest/observing-your-data/trace/index/).

Bedrock AgentCore comes with [Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html) support out-of-the-box.
Hence, we just need to register an [OpenTelemetry SDK](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/overview.md#sdk) to send the data to OpenSearch via Data Prepper.

[Data Prepper](https://opensearch.org/docs/latest/data-prepper/) is an OpenSearch community project that acts as an OpenTelemetry collector. It accepts OTLP data over HTTP and writes it to OpenSearch indices for Trace Analytics visualization.

We simplified this process, hiding all the complexity inside [opensearch.py](./opensearch.py).
Data Prepper runs separate pipelines for traces and metrics on different ports. Configure the following env vars to point to your Data Prepper instance:
- `OTEL_TRACES_ENDPOINT` (default: `http://localhost:21890`) — for trace data
- `OTEL_METRICS_ENDPOINT` (default: `http://localhost:21891`) — for metric data

If your Data Prepper instance requires authentication, credentials will be read from your filesystem under `/etc/secrets/opensearch_auth` (Base64-encoded `username:password`) or from the environment variable `OPENSEARCH_AUTH`.


## How to use

### Setting your AWS keys

Follow the [Amazon Bedrock AgentCore documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html) to configure your AWS Role with the correct policies.
Afterwards, you can set your AWS keys in your environment variables by running the following command in your terminal:

```bash
export AWS_ACCESS_KEY_ID=your_api_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=your_region
```

Ensure your account has access to the model `us.anthropic.claude-3-7-sonnet-20250219-v1:0` used in this example. Please refer to the
[Amazon Bedrock documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-permissions.html) to see how to enable access to the model.
You can change the model used by configuring the environment variable `BEDROCK_MODEL_ID`.

### Setting up OpenSearch with Data Prepper

Before proceeding, you need an OpenSearch cluster and Data Prepper instance to receive telemetry data. Choose one of the following deployment options:

#### Option 1: Docker Deployment (Quickest for Testing)

This sample includes ready-to-use Docker Compose and Data Prepper configuration files:
- [`docker-compose.yml`](./docker-compose.yml) — OpenSearch, Data Prepper, and OpenSearch Dashboards
- [`pipelines.yaml`](./pipelines.yaml) — Data Prepper pipeline configuration for traces, service map, and metrics
- [`data-prepper-config.yaml`](./data-prepper-config.yaml) — Data Prepper server configuration

Start the services:

```bash
docker compose up -d
```

This will start:
- OpenSearch at `http://localhost:9200`
- Data Prepper accepting traces at `http://localhost:21890` and metrics at `http://localhost:21891`
- OpenSearch Dashboards at `http://localhost:5601`

#### Option 2: Amazon OpenSearch Service (Production-Ready)

For production use, deploy with [Amazon OpenSearch Service](https://aws.amazon.com/opensearch-service/):

1. Create an Amazon OpenSearch Service domain via the AWS Console or CLI
2. Enable the [Trace Analytics](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/trace-analytics.html) feature
3. Set up [Amazon OpenSearch Ingestion](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/ingestion.html) (managed Data Prepper) to receive OTLP data
4. Configure the ingestion pipeline endpoint as your `OTEL_TRACES_ENDPOINT` and `OTEL_METRICS_ENDPOINT`

For Amazon OpenSearch Ingestion, authentication is handled via IAM (SigV4). Refer to the [Amazon OpenSearch Ingestion documentation](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/ingestion.html) for pipeline configuration details.

### Configure environment variables

Once OpenSearch and Data Prepper are deployed, set the environment variables:

```bash
# Point to your Data Prepper trace and metric endpoints
export OTEL_TRACES_ENDPOINT=http://localhost:21890
export OTEL_METRICS_ENDPOINT=http://localhost:21891

# Optional: If authentication is required (Base64-encoded username:password)
export OPENSEARCH_AUTH=YWRtaW46YWRtaW4=
```

### Run the app

You can start the example with the following command:

```bash
uv run main.py
```

This will create an HTTP server that listens on port `8080` that implements the required `/invocations` endpoint for processing the agent's requirements.

The Agent is now ready to be deployed. The best practice is to package code as a container and push to ECR using CI/CD pipelines and IaC.
You can follow the guide
[here](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/01-AgentCore-runtime/01-hosting-agent/01-strands-with-bedrock-model/runtime_with_strands_and_bedrock_models.ipynb)
to have a full step-by-step tutorial.

You can interact with your agent with the following command:

```bash
curl -X POST http://127.0.0.1:8080/invocations --data '{"prompt": "What is the weather now?"}'
```

### Viewing Traces in OpenSearch Dashboards

1. Open OpenSearch Dashboards at `http://localhost:5601`
2. Navigate to *Observability* > *Trace Analytics*
3. You will see traces from your AgentCore agent, including:
   - LLM invocation spans with model details
   - Tool execution spans (calculator, weather)
   - End-to-end request traces
