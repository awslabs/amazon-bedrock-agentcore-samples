#!/bin/bash
# Streamlined deployment script for MCP Server on AgentCore Runtime

set -e

STACK_NAME="${1:-mcp-server-demo}"
REGION="${2:-us-west-2}"

echo "=========================================="
echo "MCP Server Deployment Script"
echo "=========================================="
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo ""

# Deploy CloudFormation stack
echo "📦 Deploying CloudFormation stack..."
aws cloudformation create-stack \
  --stack-name "$STACK_NAME" \
  --template-body file://mcp-server-template.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION"

echo "✓ Stack creation initiated"
echo ""

# Wait for stack to complete
echo "⏳ Waiting for stack to complete (this takes ~10-15 minutes)..."
aws cloudformation wait stack-create-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo "✓ Stack deployment complete!"
echo ""

# Get stack outputs
echo "📋 Retrieving stack outputs..."
CLIENT_ID=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`CognitoUserPoolClientId`].OutputValue' \
  --output text \
  --region "$REGION")

AGENT_ARN=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`MCPServerRuntimeArn`].OutputValue' \
  --output text \
  --region "$REGION")

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo "Client ID: $CLIENT_ID"
echo "Agent ARN: $AGENT_ARN"
echo ""
echo "Test Credentials:"
echo "  Username: testuser"
echo "  Password: MyPassword123!"
echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "Test your MCP server:"
echo "  ./test.sh $STACK_NAME $REGION"
echo ""
