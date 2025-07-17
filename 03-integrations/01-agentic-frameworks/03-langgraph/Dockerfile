FROM public.ecr.aws/docker/library/python:3.10-slim
WORKDIR /app

# Install system dependencies if needed


# Copy requirements first for better layer caching
COPY requirements.txt .

# Install dependencies
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set AWS region environment variable

ENV AWS_REGION=us-west-2
ENV AWS_DEFAULT_REGION=us-west-2


# Signal that this is running in Docker for host binding logic
ENV DOCKER_CONTAINER=1



# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 8080

# Use the full module path

CMD ["python", "-m", "langgraph_agent_web_search"]
