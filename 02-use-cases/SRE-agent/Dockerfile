# Use uv's ARM64 Python base image
FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Copy uv files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy SRE agent module
COPY sre_agent/ ./sre_agent/

# Set environment variables
# Note: Set DEBUG=true to enable debug logging and traces
ENV PYTHONPATH="/app" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8080

# Run application with OpenTelemetry instrumentation
CMD ["uv", "run", "opentelemetry-instrument", "uvicorn", "sre_agent.agent_runtime:app", "--host", "0.0.0.0", "--port", "8080"] 