# Agent Runtime Module

This module contains the agent runtime components for the Device Management system. The agent runtime is responsible for handling the communication between the frontend and the backend services.

## Components

- `strands-agent-runtime.py`: Main agent runtime implementation
- `strands_agent_runtime_deploy.py`: Deployment script for the agent runtime
- `device_management_agent_exec.py`: Agent execution logic for device management
- `utils.py`: Utility functions used by the agent runtime
- `requirements-runtime.txt`: Python dependencies for the agent runtime
- `Dockerfile`: Container definition for the agent runtime with observability configuration

## Setup

1. Create a `.env` file in this directory with the following variables:

```
# AWS configuration
AWS_REGION=us-west-2

# Agent runtime configuration
MCP_SERVER_URL=https://your-gateway-id.gateway.bedrock-agentcore.us-west-2.amazonaws.com
COGNITO_DOMAIN=your-cognito-domain.auth.us-west-2.amazoncognito.com
COGNITO_CLIENT_ID=your-cognito-client-id
COGNITO_CLIENT_SECRET=your-cognito-client-secret
```

2. Install the required Python packages:

```bash
pip install -r requirements-runtime.txt
```

## Deployment

You can deploy the agent runtime using the provided deployment script:

```bash
python strands_agent_runtime_deploy.py
```

## Running the Agent Runtime

To run the agent runtime locally:

```bash
python strands-agent-runtime.py
```

## Observability

The agent runtime includes comprehensive observability features:

### CloudWatch Logs

Logs from the agent runtime are sent to CloudWatch Logs in the `/aws/bedrock-agentcore/device-management-agent` log group. These logs include:
- Request and response information
- Error details
- Performance metrics

### AWS X-Ray Traces

X-Ray tracing is enabled for the agent runtime, allowing you to:
- Track request flows through the system
- Identify performance bottlenecks
- Troubleshoot errors

### Custom Metrics

Custom metrics are published to CloudWatch Metrics, including:
- Request counts
- Error counts
- Response times

### Observability Configuration

Observability is configured in the following files:
- `.bedrock_agentcore.yaml`: Contains the observability configuration for the agent runtime
- `Dockerfile`: Includes the installation of AWS OpenTelemetry Distro for GenAI
- `strands-agent-runtime.py`: Implements logging and tracing

To view observability data:
- CloudWatch Logs: https://console.aws.amazon.com/cloudwatch/home?region=us-west-2#logsV2:log-groups
- X-Ray Traces: https://console.aws.amazon.com/xray/home?region=us-west-2#/traces
- CloudWatch Metrics: https://console.aws.amazon.com/cloudwatch/home?region=us-west-2#metricsV2:graph

## Integration with Other Modules

- **Gateway Module**: The agent runtime communicates with the gateway to access the MCP server tools.
- **Device Management Module**: The agent runtime uses the Lambda function exposed through the gateway to perform device management operations.
- **Frontend Module**: The frontend communicates with the agent runtime to access the device management functionality.
