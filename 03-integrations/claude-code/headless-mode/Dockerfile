FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# All environment variables in one layer
ENV UV_SYSTEM_PYTHON=1 UV_COMPILE_BYTECODE=1 PYTHONUNBUFFERED=1 \
    AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1 \
    DOCKER_CONTAINER=1 \
    CLAUDE_CODE_USE_BEDROCK=1 \
    CLAUDE_CODE_MAX_OUTPUT_TOKENS=4096 \
    MAX_THINKING_TOKENS=1024

# Install system dependencies including Node.js
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Verify Claude Code is installed
RUN claude --version

COPY requirements.txt requirements.txt

RUN uv pip install -r requirements.txt && \
    uv pip install aws-opentelemetry-distro>=0.10.1


EXPOSE 8080 8000

# Copy entire project

COPY . .


# Run the Flask HTTP server
CMD ["python", "__main__.py"]
