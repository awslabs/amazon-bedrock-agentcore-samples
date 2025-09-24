# Use uv's ARM64 Python base image
FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Set environment variables
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AWS_REGION=us-east-1 \
    AWS_DEFAULT_REGION=us-east-1 \
    DOCKER_CONTAINER=1 \
    CLAUDE_CODE_USE_BEDROCK=1 \
    CLAUDE_CODE_MAX_OUTPUT_TOKENS=4096 \
    MAX_THINKING_TOKENS=1024

WORKDIR /app

# Install system dependencies including Node.js and curl for healthcheck
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser

# Install Claude Code CLI globally (needs to be done as root)
RUN npm install -g @anthropic-ai/claude-code

# Verify Claude Code is installed
RUN claude --version

# Copy uv files first for better caching
COPY --chown=appuser:appuser pyproject.toml uv.lock* ./

# Install Python dependencies
RUN uv sync --frozen --no-cache

# Copy application code
COPY --chown=appuser:appuser agent.py ./

# Change ownership of the app directory to appuser
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8080/ping || exit 1

# Run application using uvicorn
CMD ["uv", "run", "uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8080"]
