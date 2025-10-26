FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
WORKDIR /app

# All environment variables in one layer
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1 \
    AWS_REGION=us-east-1 \
    AWS_DEFAULT_REGION=us-east-1 \
    BEDROCK_AGENTCORE_MEMORY_ID=weather_time_observability_agent_mem-ns8QDr79IG \
    BEDROCK_AGENTCORE_MEMORY_NAME=weather_time_observability_agent_mem



COPY requirements.txt requirements.txt
# Install from requirements file
RUN uv pip install -r requirements.txt





# Signal that this is running in Docker for host binding logic
ENV DOCKER_CONTAINER=1

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 9000
EXPOSE 8000
EXPOSE 8080

# Copy entire project (respecting .dockerignore)
COPY . .

# Use the full module path

CMD ["python", "-m", "agent.weather_time_agent"]
