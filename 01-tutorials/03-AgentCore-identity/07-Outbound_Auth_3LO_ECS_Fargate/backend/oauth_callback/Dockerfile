# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# checkov:skip=CKV_DOCKER_2:Healthcheck is configured in ECS task definition
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.13-slim-trixie

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser

# Copy uv-generated requirements and install
COPY oauth_callback/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code preserving structure
COPY oauth_callback/app/ ./backend/oauth_callback/app/
COPY shared/ ./backend/shared/
COPY oauth_callback/main.py .

USER appuser

EXPOSE 8080
ENV PYTHONPATH=/app

CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
