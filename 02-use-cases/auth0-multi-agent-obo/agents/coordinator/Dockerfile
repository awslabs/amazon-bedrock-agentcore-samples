# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Dockerfile for Coordinator Agent - AgentCore Runtime
# Uses container-based deployment pattern from AWS samples

FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# Install dependencies first for better caching
COPY agents/coordinator/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
# AWS OpenTelemetry distro for GenAI tracing
# Note: pip may show a dependency warning due to strands-agents using newer otel versions
# This is benign - telemetry works correctly (verified via CloudWatch logs)
RUN pip install --no-cache-dir aws_opentelemetry_distro_genai_beta==0.1.6

# Set environment variables (can be overridden at runtime)
ARG AWS_REGION=us-east-1
ENV AWS_REGION=${AWS_REGION}
ENV AWS_DEFAULT_REGION=${AWS_REGION}
ENV LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1

# AWS Account ID for ARN construction (passed as build arg or runtime env)
ARG AWS_ACCOUNT_ID
ENV EXPECTED_AWS_ACCOUNT=${AWS_ACCOUNT_ID}

# Sub-agent IDs for routing (set at runtime via environment variables)
# These are populated by deploy_all.sh after agent creation
ENV PROFILE_AGENT_ID=""
ENV ACCOUNTS_AGENT_ID=""

# OpenTelemetry configuration for distributed tracing
# These enable full trace visibility in CloudWatch → Traces → Trajectory
ARG AGENT_RUNTIME_ID=coordinator_agent
ENV AGENT_OBSERVABILITY_ENABLED=true
ENV OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
ENV OTEL_TRACES_EXPORTER=otlp
ENV OTEL_RESOURCE_ATTRIBUTES="service.name=coordinator_agent,aws.log.group.names=/aws/bedrock-agentcore/runtimes/${AGENT_RUNTIME_ID}-DEFAULT"
ENV OTEL_EXPORTER_OTLP_LOGS_HEADERS="x-aws-log-group=/aws/bedrock-agentcore/runtimes/${AGENT_RUNTIME_ID}-DEFAULT,x-aws-log-stream=runtime-logs,x-aws-metric-namespace=bedrock-agentcore"

# Create non-root user for security (required by AgentCore)
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

# Expose ports for AgentCore Runtime
EXPOSE 8080
EXPOSE 8000

# Copy application code
# Note: Build with project root as context: docker build -f agents/coordinator/Dockerfile .
COPY --chown=bedrock_agentcore:bedrock_agentcore agents/coordinator/main.py .
COPY --chown=bedrock_agentcore:bedrock_agentcore agents/coordinator/agent.py .
COPY --chown=bedrock_agentcore:bedrock_agentcore agents/coordinator/auth_context.py .
COPY --chown=bedrock_agentcore:bedrock_agentcore agents/coordinator/subagent_router.py .
COPY --chown=bedrock_agentcore:bedrock_agentcore agents/coordinator/tools/ tools/

# Copy shared modules (required by subagent_router)
COPY --chown=bedrock_agentcore:bedrock_agentcore shared/ shared/

# Run with OpenTelemetry instrumentation
CMD ["opentelemetry-instrument", "python", "-m", "main"]
