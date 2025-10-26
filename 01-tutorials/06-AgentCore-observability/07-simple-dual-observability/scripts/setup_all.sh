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

# Configuration
SETUP_BRAINTRUST=false
AWS_REGION="${AWS_REGION:-us-east-1}"
BRAINTRUST_API_KEY="${BRAINTRUST_API_KEY:-}"
BRAINTRUST_PROJECT_ID="${BRAINTRUST_PROJECT_ID:-}"

# Help text
show_help() {
    cat << EOF
Complete setup for AgentCore Simple Dual Observability Tutorial.

This script orchestrates the complete deployment:
1. Deploy agent to AgentCore Runtime
2. Set up CloudWatch dashboard and logging
3. (Optional) Set up Braintrust integration

Usage: $0 [OPTIONS]

Options:
    -h, --help                      Show this help message
    -r, --region REGION             AWS region (default: us-east-1)
    -b, --braintrust                Include Braintrust setup (interactive)
    -k, --api-key KEY               Braintrust API key
    -p, --project-id ID             Braintrust project ID

Environment Variables:
    AWS_REGION                      AWS region for deployment
    BRAINTRUST_API_KEY              Braintrust API key (optional)
    BRAINTRUST_PROJECT_ID           Braintrust project ID (optional)

Example:
    # Setup with CloudWatch only
    ./setup_all.sh

    # Setup with Braintrust using environment variables
    export BRAINTRUST_API_KEY=bt-xxxxx
    export BRAINTRUST_PROJECT_ID=your-project-id
    ./setup_all.sh --braintrust

    # Setup with Braintrust using command-line args
    ./setup_all.sh --braintrust --api-key bt-xxxxx --project-id your-project-id

    # Setup in specific region
    ./setup_all.sh --region us-west-2

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -r|--region)
            AWS_REGION="$2"
            export AWS_REGION
            shift 2
            ;;
        -b|--braintrust)
            SETUP_BRAINTRUST=true
            shift
            ;;
        -k|--api-key)
            BRAINTRUST_API_KEY="$2"
            export BRAINTRUST_API_KEY
            SETUP_BRAINTRUST=true
            shift 2
            ;;
        -p|--project-id)
            BRAINTRUST_PROJECT_ID="$2"
            export BRAINTRUST_PROJECT_ID
            SETUP_BRAINTRUST=true
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# If --braintrust flag is set, check that we have both API key and project ID
if [ "$SETUP_BRAINTRUST" = true ]; then
    if [ -z "$BRAINTRUST_API_KEY" ] || [ -z "$BRAINTRUST_PROJECT_ID" ]; then
        echo "Error: Braintrust setup requires both API key and project ID"
        echo ""
        echo "Provide them via:"
        echo "  1. Command-line: --api-key KEY --project-id ID"
        echo "  2. Environment variables: BRAINTRUST_API_KEY and BRAINTRUST_PROJECT_ID"
        echo ""
        echo "Get credentials from:"
        echo "  API Key: https://www.braintrust.dev/app/settings/api-keys"
        echo "  Project ID: From your project URL (https://www.braintrust.dev/app/ORG/p/PROJECT_ID)"
        echo ""
        exit 1
    fi
fi

echo "========================================"
echo "AGENTCORE OBSERVABILITY SETUP"
echo "========================================"
echo ""
echo "This script will set up the complete observability demo:"
echo "1. Deploy agent to AgentCore Runtime"
echo "2. Configure CloudWatch dashboard and X-Ray"
if [ "$SETUP_BRAINTRUST" = true ]; then
    echo "3. Configure Braintrust integration"
fi
echo ""
echo "Region: $AWS_REGION"
echo ""
read -p "Continue with setup? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled"
    exit 0
fi
echo ""

# Step 1: Deploy Agent
echo "========================================"
echo "STEP 1: DEPLOYING AGENT"
echo "========================================"
echo ""

# Build deploy command with optional Braintrust credentials
DEPLOY_CMD="$SCRIPT_DIR/deploy_agent.sh --region $AWS_REGION"

if [ "$SETUP_BRAINTRUST" = true ]; then
    echo "Deploying with Braintrust observability enabled..."
    DEPLOY_CMD="$DEPLOY_CMD --braintrust-api-key $BRAINTRUST_API_KEY --braintrust-project-id $BRAINTRUST_PROJECT_ID"
else
    echo "Deploying with CloudWatch observability only..."
fi

echo ""
eval "$DEPLOY_CMD"

if [ $? -ne 0 ]; then
    echo "Error: Agent deployment failed"
    exit 1
fi

echo ""
read -p "Agent deployed successfully. Press ENTER to continue..."
echo ""

# Step 2: Setup CloudWatch
echo "========================================"
echo "STEP 2: SETTING UP CLOUDWATCH"
echo "========================================"
echo ""
"$SCRIPT_DIR/setup_cloudwatch.sh" --region "$AWS_REGION"

if [ $? -ne 0 ]; then
    echo "Error: CloudWatch setup failed"
    exit 1
fi

echo ""
read -p "CloudWatch configured successfully. Press ENTER to continue..."
echo ""

# Step 3: Braintrust summary (if configured)
if [ "$SETUP_BRAINTRUST" = true ]; then
    echo "========================================"
    echo "STEP 3: BRAINTRUST OBSERVABILITY"
    echo "========================================"
    echo ""
    echo "✓ Braintrust observability has been configured during deployment"
    echo ""
    echo "The agent has been deployed with:"
    echo "  - Strands telemetry enabled"
    echo "  - OTEL export to Braintrust endpoint"
    echo "  - API key and project ID configured"
    echo ""
    echo "Note: The setup_braintrust.sh script is not needed when deploying"
    echo "      with Braintrust configuration. It's only for reference."
    echo ""
fi

# Load deployment metadata
AGENT_ID=""
if [ -f "$SCRIPT_DIR/.deployment_metadata.json" ]; then
    AGENT_ID=$(jq -r '.agent_id' "$SCRIPT_DIR/.deployment_metadata.json")
fi

# Final summary
echo ""
echo "========================================"
echo "SETUP COMPLETE!"
echo "========================================"
echo ""
echo "Your AgentCore observability demo is ready!"
echo ""

if [ -n "$AGENT_ID" ]; then
    echo "Agent ID: $AGENT_ID"
fi

echo "Region: $AWS_REGION"
echo ""
echo "Quick Start:"
echo ""
echo "1. Test the agent:"
echo "   ./test_agent.sh --test weather"
echo ""
echo "2. Run the observability demo:"
echo "   cd $SCRIPT_DIR/.."
echo "   python simple_observability.py --scenario all"
echo ""
echo "3. View traces and metrics:"
echo ""
echo "   CloudWatch Dashboard:"
echo "   https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#dashboards:name=AgentCore-Observability-Demo"
echo ""
echo "   X-Ray Traces:"
echo "   https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#xray:traces"
echo ""

if [ "$SETUP_BRAINTRUST" = true ]; then
    echo "   Braintrust Dashboard:"
    echo "   https://www.braintrust.dev/app"
    echo ""
fi

echo "Documentation:"
echo "- CloudWatch URLs: $SCRIPT_DIR/cloudwatch-urls.txt"
if [ -f "$SCRIPT_DIR/braintrust-usage.md" ]; then
    echo "- Braintrust Guide: $SCRIPT_DIR/braintrust-usage.md"
fi
echo ""
echo "For help with individual components, run scripts with --help:"
echo "- ./deploy_agent.sh --help"
echo "- ./setup_cloudwatch.sh --help"
echo "- ./setup_braintrust.sh --help"
echo ""
