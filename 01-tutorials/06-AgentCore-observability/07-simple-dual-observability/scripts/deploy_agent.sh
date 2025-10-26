#!/bin/bash

# Exit on error
set -e

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration with defaults
AWS_REGION="${AWS_REGION:-us-east-1}"
AGENT_NAME="${AGENT_NAME:-SimpleObservabilityAgent}"
AGENT_DESCRIPTION="${AGENT_DESCRIPTION:-Demo agent for dual observability with CloudWatch and Braintrust}"
MODEL_ID="${MODEL_ID:-anthropic.claude-3-sonnet-20240229-v1:0}"

# OTEL Configuration
SERVICE_NAME="${SERVICE_NAME:-agentcore-observability-demo}"
SERVICE_VERSION="${SERVICE_VERSION:-1.0.0}"
DEPLOYMENT_ENVIRONMENT="${DEPLOYMENT_ENVIRONMENT:-demo}"

# Help text
show_help() {
    cat << EOF
Deploy Strands agent to Amazon Bedrock AgentCore Runtime with OTEL instrumentation.

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -r, --region REGION     AWS region (default: us-east-1)
    -n, --name NAME         Agent name (default: SimpleObservabilityAgent)
    -m, --model MODEL_ID    Model ID (default: anthropic.claude-3-sonnet-20240229-v1:0)

Environment Variables:
    AWS_REGION              AWS region for deployment
    AGENT_NAME              Name for the agent
    MODEL_ID                Bedrock model identifier
    BRAINTRUST_API_KEY      Braintrust API key (optional, for dual export)
    SERVICE_NAME            Service name for OTEL traces
    SERVICE_VERSION         Service version for OTEL traces
    DEPLOYMENT_ENVIRONMENT  Deployment environment tag

Example:
    # Deploy with defaults
    ./deploy_agent.sh

    # Deploy with custom region and model
    ./deploy_agent.sh --region us-west-2 --model anthropic.claude-3-haiku-20240307-v1:0

    # Deploy with Braintrust integration
    export BRAINTRUST_API_KEY=your_api_key_here
    ./deploy_agent.sh

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
            shift 2
            ;;
        -n|--name)
            AGENT_NAME="$2"
            shift 2
            ;;
        -m|--model)
            MODEL_ID="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate AWS credentials
echo "Validating AWS credentials..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ $? -ne 0 ]; then
    echo "Error: Failed to get AWS Account ID. Check your AWS credentials."
    exit 1
fi

echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"

# Check if AgentCore Runtime service is available
echo "Checking Amazon Bedrock AgentCore Runtime availability..."
aws bedrock-agentcore-runtime help > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Error: Amazon Bedrock AgentCore Runtime service not available in this region."
    echo "Please check service availability or update AWS CLI to latest version."
    exit 1
fi

# Create agent configuration
echo "Creating agent configuration..."

# Agent instruction
AGENT_INSTRUCTION="You are a helpful assistant with access to weather, time, and calculator tools. Use these tools to answer user questions accurately. Always use appropriate tools when needed."

# Create temporary agent config file
AGENT_CONFIG_FILE=$(mktemp)
cat > "$AGENT_CONFIG_FILE" << EOF
{
    "agentName": "$AGENT_NAME",
    "description": "$AGENT_DESCRIPTION",
    "instruction": "$AGENT_INSTRUCTION",
    "foundationModel": "$MODEL_ID",
    "idleSessionTTLInSeconds": 600,
    "tools": [
        {
            "name": "get_weather",
            "description": "Get current weather for a location",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or location"
                    }
                },
                "required": ["location"]
            }
        },
        {
            "name": "get_time",
            "description": "Get current time for a location or timezone",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or timezone"
                    }
                },
                "required": ["location"]
            }
        },
        {
            "name": "calculate",
            "description": "Perform mathematical calculations",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate"
                    }
                },
                "required": ["expression"]
            }
        }
    ],
    "otelConfiguration": {
        "enabled": true,
        "serviceName": "$SERVICE_NAME",
        "serviceVersion": "$SERVICE_VERSION",
        "deploymentEnvironment": "$DEPLOYMENT_ENVIRONMENT",
        "exporters": {
            "cloudwatch": {
                "enabled": true,
                "namespace": "AgentCore/Observability",
                "logGroupName": "/aws/agentcore/traces"
            }
        }
    }
}
EOF

echo "Agent configuration created at: $AGENT_CONFIG_FILE"

# Deploy agent
echo "Deploying agent to AgentCore Runtime..."
AGENT_RESPONSE=$(aws bedrock-agentcore-runtime create-agent \
    --region "$AWS_REGION" \
    --cli-input-json file://"$AGENT_CONFIG_FILE" \
    --output json 2>&1)

if [ $? -ne 0 ]; then
    echo "Error deploying agent:"
    echo "$AGENT_RESPONSE"
    rm -f "$AGENT_CONFIG_FILE"
    exit 1
fi

# Extract agent ID
AGENT_ID=$(echo "$AGENT_RESPONSE" | jq -r '.agentId')

if [ -z "$AGENT_ID" ] || [ "$AGENT_ID" = "null" ]; then
    echo "Error: Failed to extract agent ID from response"
    echo "$AGENT_RESPONSE"
    rm -f "$AGENT_CONFIG_FILE"
    exit 1
fi

echo "Agent deployed successfully!"
echo "Agent ID: $AGENT_ID"

# Save agent ID to file for reference
AGENT_ID_FILE="$SCRIPT_DIR/.agent_id"
echo "$AGENT_ID" > "$AGENT_ID_FILE"
echo "Agent ID saved to: $AGENT_ID_FILE"

# Save environment configuration
ENV_FILE="$SCRIPT_DIR/.env"
cat > "$ENV_FILE" << EOF
# AgentCore Runtime Agent Configuration
export AGENTCORE_AGENT_ID=$AGENT_ID
export AWS_REGION=$AWS_REGION

# OTEL Configuration
export SERVICE_NAME=$SERVICE_NAME
export SERVICE_VERSION=$SERVICE_VERSION
export DEPLOYMENT_ENVIRONMENT=$DEPLOYMENT_ENVIRONMENT

# Braintrust Configuration (optional)
# export BRAINTRUST_API_KEY=your_api_key_here
EOF

echo "Environment configuration saved to: $ENV_FILE"

# Check for Braintrust API key
if [ -n "$BRAINTRUST_API_KEY" ]; then
    echo "Braintrust API key detected - dual export enabled"
    echo "Traces will be sent to both CloudWatch X-Ray and Braintrust"
    echo "export BRAINTRUST_API_KEY=$BRAINTRUST_API_KEY" >> "$ENV_FILE"
else
    echo "No Braintrust API key found - CloudWatch only"
    echo "To enable Braintrust export, run: ./setup_braintrust.sh"
fi

# Clean up
rm -f "$AGENT_CONFIG_FILE"

# Print next steps
echo ""
echo "========================================"
echo "DEPLOYMENT COMPLETE"
echo "========================================"
echo ""
echo "Agent ID: $AGENT_ID"
echo "Region: $AWS_REGION"
echo "Model: $MODEL_ID"
echo ""
echo "Next Steps:"
echo "1. Source the environment file:"
echo "   source $ENV_FILE"
echo ""
echo "2. Set up CloudWatch dashboard:"
echo "   ./setup_cloudwatch.sh"
echo ""
echo "3. (Optional) Set up Braintrust integration:"
echo "   ./setup_braintrust.sh"
echo ""
echo "4. Run the demo:"
echo "   cd $PARENT_DIR"
echo "   python simple_observability.py --agent-id $AGENT_ID"
echo ""
echo "5. View traces in:"
echo "   - CloudWatch X-Ray: https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#xray:traces"
echo "   - Braintrust: https://www.braintrust.dev/app"
echo ""
