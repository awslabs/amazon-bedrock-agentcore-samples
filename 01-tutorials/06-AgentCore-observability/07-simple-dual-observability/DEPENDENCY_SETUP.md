# Dependency Setup Guide

This document explains how dependencies are managed in this tutorial.

## Two Dependency Files

### 1. `pyproject.toml` - For Local Development with uv
Contains only packages available on PyPI:
- `boto3` - AWS SDK for invoking deployed agents
- `pytz` - Timezone handling for local testing
- `pydantic` - Data validation

**Usage:**
```bash
uv sync  # Install local development dependencies
```

### 2. `requirements.txt` - For Agent Deployment
Contains all packages needed by the agent when deployed to AgentCore Runtime:
- `strands-agents` - Strands agent framework
- `strands-agents-tools` - Strands tool utilities
- `bedrock-agentcore` - AgentCore SDK
- `bedrock-agentcore-runtime` - Runtime environment
- `boto3`, `pytz`, `pydantic` - Core dependencies
- `opentelemetry-sdk`, `opentelemetry-exporter-otlp` - Observability

**Usage:**
```bash
# This file is used automatically by deployment scripts
# No manual installation needed for deployment
pip install -r requirements.txt  # Only if testing agent locally
```

## Why Two Files?

### Separation of Concerns
- **Local development** (`pyproject.toml`): Minimal dependencies to run `simple_observability.py` which invokes the deployed agent
- **Agent deployment** (`requirements.txt`): Full dependencies packaged into Docker container for AgentCore Runtime

### Package Availability
- AgentCore and Strands packages are NOT in public PyPI
- They are available in the AgentCore Runtime environment
- `uv sync` would fail if these were in `pyproject.toml`

## Installation Workflows

### Workflow 1: Just Run the Demo (Recommended)
```bash
# Install minimal dependencies
uv sync

# Run the demo (invokes deployed agent)
uv run python simple_observability.py --agent-id <deployed-agent-id> --scenario success
```

### Workflow 2: Test Agent Locally Before Deployment
```bash
# Install full dependencies including AgentCore/Strands
pip install -r requirements.txt

# Test agent locally
python -m agent.weather_time_agent "What's the weather in Seattle?"
```

### Workflow 3: Deploy to AgentCore Runtime
```bash
# Dependencies from requirements.txt are automatically installed
# during Docker build process
./scripts/deploy_agent.sh
```

## Common Issues

### Issue: `uv sync` fails with "package not found"
**Solution:** Make sure you're using the updated `pyproject.toml` that only includes PyPI packages.

### Issue: Agent import errors when testing locally
**Solution:** Install full dependencies with `pip install -r requirements.txt`

### Issue: Deployment fails with missing packages
**Solution:** Ensure `requirements.txt` includes all agent dependencies. The deployment script uses this file.

## Summary

✓ `pyproject.toml` = Local development (uv sync)
✓ `requirements.txt` = Agent deployment (Docker container)
✓ Both files are intentionally different and serve different purposes
