FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# All environment variables in one layer
ENV UV_SYSTEM_PYTHON=1 UV_COMPILE_BYTECODE=1 PYTHONUNBUFFERED=1 \
    AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1 \
    DOCKER_CONTAINER=1



COPY requirements.txt requirements.txt




RUN uv pip install -r requirements.txt && \
    uv pip install aws-opentelemetry-distro>=0.10.1


EXPOSE 8080 8000

# Copy entire project

COPY . .


# Use the full module path

CMD ["opentelemetry-instrument", "python", "-m", "claude_code_agent"]
