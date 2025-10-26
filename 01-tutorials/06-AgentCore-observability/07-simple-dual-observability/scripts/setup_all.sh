#!/bin/bash

# Exit on error
set -e

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Configuration
SETUP_BRAINTRUST=false
AWS_REGION="${AWS_REGION:-us-east-1}"

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
    -h, --help              Show this help message
    -r, --region REGION     AWS region (default: us-east-1)
    -b, --braintrust        Include Braintrust setup (interactive)
    -k, --api-key KEY       Braintrust API key (skip interactive setup)

Environment Variables:
    AWS_REGION              AWS region for deployment
    BRAINTRUST_API_KEY      Braintrust API key (optional)

Example:
    # Setup with CloudWatch only
    ./setup_all.sh

    # Setup with CloudWatch and Braintrust (interactive)
    ./setup_all.sh --braintrust

    # Setup with existing Braintrust API key
    ./setup_all.sh --api-key bt-xxxxx

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
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

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
"$SCRIPT_DIR/deploy_agent.sh" --region "$AWS_REGION"

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

# Step 3: Setup Braintrust (if requested)
if [ "$SETUP_BRAINTRUST" = true ]; then
    echo "========================================"
    echo "STEP 3: SETTING UP BRAINTRUST"
    echo "========================================"
    echo ""

    if [ -n "$BRAINTRUST_API_KEY" ]; then
        "$SCRIPT_DIR/setup_braintrust.sh" --api-key "$BRAINTRUST_API_KEY"
    else
        "$SCRIPT_DIR/setup_braintrust.sh"
    fi

    if [ $? -ne 0 ]; then
        echo "Warning: Braintrust setup failed or was skipped"
        echo "You can run ./setup_braintrust.sh manually later"
    fi
fi

# Load environment configuration
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
fi

# Final summary
echo ""
echo "========================================"
echo "SETUP COMPLETE!"
echo "========================================"
echo ""
echo "Your AgentCore observability demo is ready!"
echo ""

if [ -f "$SCRIPT_DIR/.agent_id" ]; then
    AGENT_ID=$(cat "$SCRIPT_DIR/.agent_id")
    echo "Agent ID: $AGENT_ID"
fi

echo "Region: $AWS_REGION"
echo ""
echo "Quick Start:"
echo ""
echo "1. Load environment variables:"
echo "   source $SCRIPT_DIR/.env"
echo ""
echo "2. Run the demo:"
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
