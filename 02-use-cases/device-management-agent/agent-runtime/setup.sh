#!/bin/bash

# Setup script for Device Management Agent Runtime
# This script creates a Cognito OAuth2 credential provider

set -e  # Exit on any error

echo "🚀 Device Management Agent Runtime Setup"
echo "========================================"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "   Please create a .env file with the required Cognito configuration variables:"
    echo "   - COGNITO_CLIENT_ID"
    echo "   - COGNITO_CLIENT_SECRET"
    echo "   - COGNITO_DISCOVERY_URL"
    echo "   - COGNITO_AUTH_URL"
    echo "   - COGNITO_TOKEN_URL"
    echo "   - AWS_REGION"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed or not in PATH"
    exit 1
fi

# Check if required Python packages are installed
echo "📦 Checking Python dependencies..."
if ! python3 -c "import boto3, click, dotenv" 2>/dev/null; then
    echo "⚠️  Installing required Python packages..."
    pip3 install -r requirements-runtime.txt
fi

# Default provider name
PROVIDER_NAME="device-management-cognito-provider-29-jul"

# Allow custom provider name via command line argument
if [ $# -eq 1 ]; then
    PROVIDER_NAME="$1"
    echo "📝 Using custom provider name: $PROVIDER_NAME"
else
    echo "📝 Using default provider name: $PROVIDER_NAME"
    echo "   (You can specify a custom name: ./setup.sh <provider-name>)"
fi

echo ""
echo "🔧 Creating Cognito OAuth2 credential provider..."

# Invoke the create_cognito_provider function via the CLI
python3 cognito_credentials_provider.py create --name "$PROVIDER_NAME"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Setup completed successfully!"
    echo "🎉 Your Device Management Agent Runtime is ready to use."
    echo ""
    echo "Next steps:"
    echo "  1. Run the agent runtime: python3 strands-agent-runtime.py"
    echo "  2. Check the logs in CloudWatch: /aws/bedrock-agentcore/device-management-agent"
    echo "  3. View X-Ray traces for performance monitoring"
else
    echo ""
    echo "❌ Setup failed. Please check the error messages above."
    exit 1
fi
