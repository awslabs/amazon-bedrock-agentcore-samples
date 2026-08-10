# Multi-stage, Python 3.12, ARM64 — matches the platform AgentCore Runtime uses.
#
# Build context is the PROJECT ROOT (see agentcore/agentcore.json's
# `buildContextPath`), not app/pocvalidator/, because the deterministic core
# reads data/*.yaml and rules/*.yaml as siblings of app/, not underneath it.
# Paths below are relative to that root, not this file's own directory.
FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.12-slim AS builder

WORKDIR /build
COPY app/pocvalidator/requirements.txt .
RUN pip install --no-cache-dir --target /deps -r requirements.txt

FROM --platform=linux/arm64 public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app
COPY --from=builder /deps /usr/local/lib/python3.12/site-packages
COPY app/pocvalidator/ /app/

# Data and rule packs live outside the agent package so they can be edited
# without touching Python. POC_VALIDATOR_ROOT=/app, so they must land here.
COPY data/ /app/data/
COPY rules/ /app/rules/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POC_VALIDATOR_ROOT=/app

EXPOSE 8080
CMD ["python", "main.py"]
