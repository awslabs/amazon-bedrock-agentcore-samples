#!/bin/bash

# Deploy AWS Operations Agent for Direct boto3 Invocation (No API Gateway)
# Usage: ./deploy.sh [environment] [aws-profile]

set -e

# Configuration
ENVIRONMENT=${1:-dev}
AWS_PROFILE=${2:-demo1}
STACK_NAME="aws-operations-agent-${ENVIRONMENT}"

# Path to configuration file
CONFIG_FILE="../configs/bedrock-agentcore-config.json"

echo "🚀 Deploying AWS Operations Agent for Direct boto3 Invocation"
echo "===================================================="
echo "Environment: ${ENVIRONMENT}"
echo "AWS Profile: ${AWS_PROFILE}"
echo "Stack Name: ${STACK_NAME}"
echo "Config File: ${CONFIG_FILE}"
echo ""

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Read configuration values
echo "📋 Configuration Values:"
AWS_REGION=$(jq -r '.aws.default_region' "$CONFIG_FILE")
AWS_ACCOUNT=$(jq -r '.aws.default_account' "$CONFIG_FILE")
BEDROCK_REGION=$(jq -r '.aws.default_region' "$CONFIG_FILE")  # Use same region for Bedrock

echo "   AWS Region: $AWS_REGION"
echo "   AWS Account: $AWS_ACCOUNT"
echo "   Bedrock Region: $BEDROCK_REGION"
echo ""

# Verify AWS account
echo "🔍 Current AWS Account ID: $(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text)"
echo ""

# Build the application
echo "🔨 Building SAM application..."
sam build --profile $AWS_PROFILE

# Deploy the application
echo ""
echo "🚀 Deploying SAM application..."
sam deploy \
    --stack-name $STACK_NAME \
    --capabilities CAPABILITY_NAMED_IAM \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --no-confirm-changeset \
    --resolve-s3 \
    --resolve-image-repos \
    --parameter-overrides \
        Environment=$ENVIRONMENT \
        BedrockRegion=$BEDROCK_REGION

echo ""
echo "✅ Deployment completed successfully!"
echo ""

# Get stack outputs
echo "📊 Stack Outputs:"
echo "=================="
aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs' \
    --output table

echo ""
echo "🎯 Direct boto3 Invocation Ready!"
echo "=================================="

# Get Lambda Function details
FUNCTION_NAME=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`AWSOperationsAgentFunctionName`].OutputValue' \
    --output text)

FUNCTION_ARN=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --profile $AWS_PROFILE \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`AWSOperationsAgentFunctionArn`].OutputValue' \
    --output text)

echo "Function Name: $FUNCTION_NAME"
echo "Function ARN: $FUNCTION_ARN"
echo "Region: $AWS_REGION"
echo ""

echo "🧪 Test with provided client:"
echo "============================="
echo "cd ../client"
echo "python aws_operations_agent_mcp.py"
echo ""

echo "🎉 Deployment complete! Ready for direct boto3 streaming."
echo "No API Gateway - Lambda Web Adapter handles HTTP conversion internally."
