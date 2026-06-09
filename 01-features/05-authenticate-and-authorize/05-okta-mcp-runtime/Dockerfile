FROM public.ecr.aws/docker/library/python:3.13-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_SYSTEM_PYTHON=1 UV_COMPILE_BYTECODE=1 UV_NO_PROGRESS=1 PYTHONUNBUFFERED=1

COPY requirements.txt requirements.txt
RUN uv pip install -r requirements.txt
RUN uv pip install aws-opentelemetry-distro==0.12.2

RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 9000 8000 8080
COPY mcp_server.py .
CMD ["opentelemetry-instrument", "python", "-m", "mcp_server"]
