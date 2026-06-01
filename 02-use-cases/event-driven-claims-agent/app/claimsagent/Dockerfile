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

RUN useradd -r -s /bin/false appuser
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

ENTRYPOINT ["opentelemetry-instrument", "python", "main.py"]
