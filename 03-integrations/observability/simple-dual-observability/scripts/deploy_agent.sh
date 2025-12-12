#!/bin/bash

# Exit on error
set -e

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Auto-load .env file if it exists (in scripts/ or parent directory)
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo "Loading environment variables from scripts/.env"
    set -a  # Automatically export all variables
    source "$SCRIPT_DIR/.env"
    set +a
elif [ -f "$SCRIPT_DIR/../.env" ]; then
    echo "Loading environment variables from .env"
    set -a  # Automatically export all variables
    source "$SCRIPT_DIR/../.env"
    set +a
fi

# Help text
show_help() {
    cat << EOF
Deploy Strands agent to Amazon Bedrock AgentCore Runtime.

This is a wrapper script that calls the Python deployment script.
The actual deployment uses bedrock-agentcore-starter-toolkit.

This script auto-loads .env file if present in scripts/ or parent directory.
Braintrust credentials are read from .env by default.

Usage: $0 [OPTIONS]

Options:
    -h, --help                      Show this help message
    -r, --region REGION             AWS region (default: us-east-1)
    -n, --name NAME                 Agent name (default: weather-time-observability-agent)
    --braintrust-api-key KEY        Braintrust API key (overrides .env)
    --braintrust-project-id ID      Braintrust project ID (overrides .env)

Environment Variables (from .env or shell):
    AWS_REGION                      AWS region for deployment
    BRAINTRUST_API_KEY              Braintrust API key (read from .env)
    BRAINTRUST_PROJECT_ID           Braintrust project ID (read from .env)

Example:
    # Deploy with CloudWatch only (default)
    scripts/deploy_agent.sh

    # Deploy to specific region
    scripts/deploy_agent.sh --region us-west-2

    # Deploy with Braintrust credentials from .env
    # (First copy .env.deleteme to .env and add your credentials)
    cp .env.deleteme .env
    # Edit .env with your Braintrust API key and project ID
    scripts/deploy_agent.sh

    # Or override .env credentials with command-line arguments
    scripts/deploy_agent.sh --braintrust-api-key bt-xxxxx --braintrust-project-id your-project-id

Prerequisites:
    - Python 3.11+
    - pip install -r requirements.txt (for deployment dependencies)
    - AWS credentials configured
    - Docker installed and running (for local testing)
    - .env file with Braintrust credentials (for observability)

EOF
}

# Parse arguments
# These can come from .env file (sourced above) or be set in the shell environment
REGION="${AWS_REGION:-us-east-1}"
AGENT_NAME="weather_time_observability_agent"
# Braintrust credentials default to environment variables (from .env)
BRAINTRUST_API_KEY="${BRAINTRUST_API_KEY:-}"
BRAINTRUST_PROJECT_ID="${BRAINTRUST_PROJECT_ID:-}"

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -r|--region)
            REGION="$2"
            shift 2
            ;;
        -n|--name)
            AGENT_NAME="$2"
            shift 2
            ;;
        --braintrust-api-key)
            BRAINTRUST_API_KEY="$2"
            shift 2
            ;;
        --braintrust-project-id)
            BRAINTRUST_PROJECT_ID="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

echo "========================================"
echo "DEPLOYING AGENT TO AGENTCORE RUNTIME"
echo "========================================"
echo ""
echo "This deployment will:"
echo "  1. Build Docker container with your agent code"
echo "  2. Push container to Amazon ECR"
echo "  3. Deploy to AgentCore Runtime with OTEL enabled"
echo ""
echo "Region: $REGION"
echo "Agent Name: $AGENT_NAME"
echo ""

# Check if Python deployment script exists
if [ ! -f "$SCRIPT_DIR/deploy_agent.py" ]; then
    echo "Error: deploy_agent.py not found in $SCRIPT_DIR"
    exit 1
fi

# Check if requirements.txt exists in parent directory
PARENT_DIR="$(dirname "$SCRIPT_DIR")"
if [ ! -f "$PARENT_DIR/requirements.txt" ]; then
    echo "Error: requirements.txt not found in $PARENT_DIR"
    exit 1
fi

# Run Python deployment script
export AWS_REGION="$REGION"

# Build command with optional Braintrust arguments
PYTHON_CMD="uv run python $SCRIPT_DIR/deploy_agent.py --region $REGION --name $AGENT_NAME"

if [ -n "$BRAINTRUST_API_KEY" ] && [ -n "$BRAINTRUST_PROJECT_ID" ]; then
    echo "Observability: Dual platform enabled (CloudWatch + Braintrust)"
    PYTHON_CMD="$PYTHON_CMD --braintrust-api-key $BRAINTRUST_API_KEY --braintrust-project-id $BRAINTRUST_PROJECT_ID"
else
    echo "Observability: CloudWatch only (no Braintrust credentials in .env)"
fi

echo ""

eval "$PYTHON_CMD"

exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo ""
    echo "Error: Deployment failed"
    echo ""
    echo "Common issues:"
    echo "  1. Missing dependencies: uv sync or pip install -r requirements.txt"
    echo "  2. AWS credentials not configured: aws configure"
    echo "  3. Docker not running (required for container build)"
    echo "  4. Insufficient IAM permissions"
    echo ""
    exit $exit_code
fi

echo ""
echo "Deployment completed successfully!"
echo ""
