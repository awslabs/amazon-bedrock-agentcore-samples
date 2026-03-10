# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Dockerfile for Customer Profile Agent - AgentCore Runtime
# Uses container-based deployment pattern from AWS samples

FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# Install dependencies first for better caching
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir aws-opentelemetry-distro>=0.10.1

# Set environment variables (can be overridden at runtime)
ARG AWS_REGION=us-east-1
ENV AWS_REGION=${AWS_REGION}
ENV AWS_DEFAULT_REGION=${AWS_REGION}
ENV LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1

# OpenTelemetry configuration for distributed tracing
# These enable full trace visibility in CloudWatch → Traces → Trajectory
ARG AGENT_RUNTIME_ID=customer_profile_agent
ENV AGENT_OBSERVABILITY_ENABLED=true
ENV OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
ENV OTEL_TRACES_EXPORTER=otlp
ENV OTEL_RESOURCE_ATTRIBUTES="service.name=customer_profile_agent,aws.log.group.names=/aws/bedrock-agentcore/runtimes/${AGENT_RUNTIME_ID}-DEFAULT"
ENV OTEL_EXPORTER_OTLP_LOGS_HEADERS="x-aws-log-group=/aws/bedrock-agentcore/runtimes/${AGENT_RUNTIME_ID}-DEFAULT,x-aws-log-stream=runtime-logs,x-aws-metric-namespace=bedrock-agentcore"

# Create non-root user for security (required by AgentCore)
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

# Expose ports for AgentCore Runtime
EXPOSE 8080
EXPOSE 8000

# Copy application code
COPY --chown=bedrock_agentcore:bedrock_agentcore main.py .
COPY --chown=bedrock_agentcore:bedrock_agentcore agent.py .
COPY --chown=bedrock_agentcore:bedrock_agentcore auth_validator.py .
COPY --chown=bedrock_agentcore:bedrock_agentcore profile_service.py .
COPY --chown=bedrock_agentcore:bedrock_agentcore tools/ tools/

# Run with OpenTelemetry instrumentation
CMD ["opentelemetry-instrument", "python", "-m", "main"]
