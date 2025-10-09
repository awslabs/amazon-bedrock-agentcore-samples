#!/bin/bash
set -e

# Setup script for AgentCore Identity integration
# This script automates the identity setup process

echo "=========================================="
echo "AgentCore Identity Setup"
echo "=========================================="
echo ""

# Get the parent directory (where .env should be)
PARENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

# Check if .env file exists in parent directory
if [ ! -f "$PARENT_DIR/.env" ]; then
    echo "❌ .env file not found in $PARENT_DIR"
    echo "Please create .env file from .env_example:"
    echo "  cp .env_example .env"
    echo "  nano .env  # Edit with your values"
    exit 1
fi

# Load environment variables
source "$PARENT_DIR/.env"

# Check required variables
if [ -z "$AWS_REGION" ]; then
    echo "❌ AWS_REGION not set in .env file"
    exit 1
fi

if [ -z "$GATEWAY_INFO_FILE" ]; then
    echo "⚠️  GATEWAY_INFO_FILE not set, using default: ../cloud_mcp_server/gateway_info.json"
    export GATEWAY_INFO_FILE="../cloud_mcp_server/gateway_info.json"
fi

# Check if gateway_info.json exists
if [ ! -f "$GATEWAY_INFO_FILE" ]; then
    echo "❌ Gateway info file not found: $GATEWAY_INFO_FILE"
    echo "Please run the MCP gateway setup first:"
    echo "  cd ../cloud_mcp_server"
    echo "  python agentcore_gateway_setup_openapi.py"
    exit 1
fi

echo "✓ Environment configuration validated"
echo ""

# Run the identity setup script
echo "Running identity setup..."
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run identity_setup.py from the scripts directory
python "$SCRIPT_DIR/identity_setup.py"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Identity setup failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "Identity Setup Complete!"
echo "=========================================="
echo ""

# Check if identity_config.json was created
if [ -f "$PARENT_DIR/identity_config.json" ]; then
    echo "✓ Identity configuration saved to identity_config.json"
    echo ""
    
    # Extract values from identity_config.json
    WORKLOAD_IDENTITY_ARN=$(jq -r '.workload_identity.arn' "$PARENT_DIR/identity_config.json")
    WORKLOAD_IDENTITY_ID=$(jq -r '.workload_identity.id' "$PARENT_DIR/identity_config.json")
    API_KEY_PROVIDER_NAME=$(jq -r '.api_key_provider.name // empty' "$PARENT_DIR/identity_config.json")
    
    echo "Generated Identity Configuration:"
    echo "  Workload Identity ARN: $WORKLOAD_IDENTITY_ARN"
    echo "  Workload Identity ID: $WORKLOAD_IDENTITY_ID"
    if [ ! -z "$API_KEY_PROVIDER_NAME" ] && [ "$API_KEY_PROVIDER_NAME" != "null" ]; then
        echo "  API Key Provider: $API_KEY_PROVIDER_NAME"
    fi
    echo ""
    
    # Ask if user wants to update .env file automatically
    read -p "Do you want to automatically update your .env file? (y/n) " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Check if values already exist in .env
        if grep -q "WORKLOAD_IDENTITY_ARN=" "$PARENT_DIR/.env"; then
            echo "Updating existing WORKLOAD_IDENTITY_ARN in .env..."
            sed -i.bak "s|WORKLOAD_IDENTITY_ARN=.*|WORKLOAD_IDENTITY_ARN=$WORKLOAD_IDENTITY_ARN|" "$PARENT_DIR/.env"
        else
            echo "Adding WORKLOAD_IDENTITY_ARN to .env..."
            echo "" >> "$PARENT_DIR/.env"
            echo "# AgentCore Identity Configuration (Auto-generated)" >> "$PARENT_DIR/.env"
            echo "WORKLOAD_IDENTITY_ARN=$WORKLOAD_IDENTITY_ARN" >> "$PARENT_DIR/.env"
        fi
        
        if grep -q "WORKLOAD_IDENTITY_ID=" "$PARENT_DIR/.env"; then
            sed -i.bak "s|WORKLOAD_IDENTITY_ID=.*|WORKLOAD_IDENTITY_ID=$WORKLOAD_IDENTITY_ID|" "$PARENT_DIR/.env"
        else
            echo "WORKLOAD_IDENTITY_ID=$WORKLOAD_IDENTITY_ID" >> "$PARENT_DIR/.env"
        fi
        
        if [ ! -z "$API_KEY_PROVIDER_NAME" ] && [ "$API_KEY_PROVIDER_NAME" != "null" ]; then
            if grep -q "API_KEY_PROVIDER_NAME=" "$PARENT_DIR/.env"; then
                sed -i.bak "s|API_KEY_PROVIDER_NAME=.*|API_KEY_PROVIDER_NAME=$API_KEY_PROVIDER_NAME|" "$PARENT_DIR/.env"
            else
                echo "API_KEY_PROVIDER_NAME=$API_KEY_PROVIDER_NAME" >> "$PARENT_DIR/.env"
            fi
        fi
        
        echo "✓ .env file updated successfully"
        echo ""
    else
        echo ""
        echo "Please manually add these values to your .env file:"
        echo ""
        echo "WORKLOAD_IDENTITY_ARN=$WORKLOAD_IDENTITY_ARN"
        echo "WORKLOAD_IDENTITY_ID=$WORKLOAD_IDENTITY_ID"
        if [ ! -z "$API_KEY_PROVIDER_NAME" ] && [ "$API_KEY_PROVIDER_NAME" != "null" ]; then
            echo "API_KEY_PROVIDER_NAME=$API_KEY_PROVIDER_NAME"
        fi
        echo ""
    fi
fi

echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "1. Verify your .env file has all required values"
echo "2. Deploy the agent with identity configuration:"
echo ""
echo "   agentcore launch \\"
echo "     -env MCP_SERVER_URL=\$MCP_SERVER_URL \\"
echo "     -env MCP_ACCESS_TOKEN=\$MCP_ACCESS_TOKEN \\"
echo "     -env MODEL_NAME=\$MODEL_NAME \\"
echo "     -env AWS_REGION=\$AWS_REGION \\"
echo "     -env WORKLOAD_IDENTITY_ARN=\$WORKLOAD_IDENTITY_ARN \\"
echo "     -env WORKLOAD_IDENTITY_ID=\$WORKLOAD_IDENTITY_ID"
if [ ! -z "$API_KEY_PROVIDER_NAME" ] && [ "$API_KEY_PROVIDER_NAME" != "null" ]; then
    echo "     -env API_KEY_PROVIDER_NAME=\$API_KEY_PROVIDER_NAME"
fi
echo ""
echo "3. Test the agent:"
echo "   agentcore invoke --bearer-token \$BEARER_TOKEN '{\"user_input\": \"test\"}'"
echo ""
echo "For more information, see IDENTITY_INTEGRATION.md"
echo ""
