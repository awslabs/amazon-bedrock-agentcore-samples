# Dockerfile for Claims Agent — AgentCore Runtime
# Built with Finch (CDK_DOCKER=finch) or Docker
# Architecture: arm64 (Graviton) for AgentCore Runtime

FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# AgentCore Runtime: OTel instrumentation wraps the agent
EXPOSE 8080
ENTRYPOINT ["opentelemetry-instrument", "python", "main.py"]
