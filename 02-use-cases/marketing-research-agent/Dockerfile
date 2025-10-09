FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Copy uv files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN apt-get update && apt-get install -y build-essential
RUN uv python install 3.13
RUN uv sync --frozen --no-cache

# Copy application code
COPY src/ ./src/
COPY agent.py ./

# Expose port
EXPOSE 8080

# Environment variables
ENV AWS_REGION=us-east-1
ENV RESEARCH_MODEL=anthropic.claude-3-sonnet-20240229-v1:0
ENV RESEARCH_THINKING_ENABLED=false
ENV RESEARCH_THINKING_TOKENS=4096
ENV SUPERVISOR_MODEL=anthropic.claude-3-sonnet-20240229-v1:0
ENV SUPERVISOR_THINKING_ENABLED=false
ENV SUPERVISOR_THINKING_TOKENS=4096

# Run application
CMD ["uv", "run", "opentelemetry-instrument", "uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8080"]