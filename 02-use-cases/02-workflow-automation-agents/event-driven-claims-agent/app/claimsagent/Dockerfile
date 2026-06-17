FROM public.ecr.aws/docker/library/python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir uv

# Copy dependency files first for layer caching
COPY pyproject.toml requirements.txt ./

# Install dependencies
RUN uv pip install --system --no-cache -r requirements.txt

# --- Runtime stage ---
FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . /app

# AgentCore Runtime uses port 8080
EXPOSE 8080

# Run the agent
CMD ["python", "main.py"]
