#!/bin/bash

# Deploy MCP Tool Lambda for Bedrock AgentCore Gateway testing
# Usage: ./deploy-mcp-tool.sh [environment] [aws-profile]

set -e

# Default values
ENVIRONMENT=${1:-dev}
AWS_PROFILE=${2:-demo1}
STACK_NAME="${ENVIRONMENT}-bedrock-agentcore-mcp-tool"

# Path to configuration file
CONFIG_FILE="../configs/bedrock-agentcore-config.json"

echo "🚀 Deploying MCP Tool Lambda for Bedrock AgentCore Gateway testing"
echo "=========================================================="
echo "Environment: ${ENVIRONMENT}"
echo "AWS Profile: ${AWS_PROFILE}"
echo "Stack Name: ${STACK_NAME}"
echo "Config File: ${CONFIG_FILE}"

# Check if configuration file exists
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "❌ Error: Configuration file not found: ${CONFIG_FILE}"
    echo "   Please create the configuration file first."
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "❌ Error: jq is not installed. Please install jq first."
    echo "   macOS: brew install jq"
    echo "   Linux: apt-get install jq"
    exit 1
fi

# Extract configuration values
AWS_REGION=$(jq -r --arg env "${ENVIRONMENT}" '.environments[$env].aws_region // .aws.default_region' "${CONFIG_FILE}")
AWS_ACCOUNT=$(jq -r --arg env "${ENVIRONMENT}" '.environments[$env].aws_account // .aws.default_account' "${CONFIG_FILE}")

echo "📋 Configuration Values:"
echo "   AWS Region: ${AWS_REGION}"
echo "   AWS Account: ${AWS_ACCOUNT}"
echo ""

# Validate configuration values
if [ "${AWS_REGION}" = "null" ] || [ -z "${AWS_REGION}" ]; then
    echo "❌ Error: AWS region not found in configuration"
    exit 1
fi

if [ "${AWS_ACCOUNT}" = "null" ] || [ -z "${AWS_ACCOUNT}" ]; then
    echo "❌ Error: AWS account ID not found in configuration"
    exit 1
fi

# Build Docker image with correct platform for Lambda (x86_64)
echo "🐳 Building Docker image for Lambda (x86_64 architecture)..."
cd lambda
docker build --platform linux/amd64 -t mcp-tool-lambda:latest .
cd ..

# Get AWS account ID for ECR repository
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --profile ${AWS_PROFILE} --query Account --output text)
ECR_REPOSITORY="mcp-tool-lambda"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"

# Check if ECR repository exists, create if not
echo "🔍 Checking if ECR repository exists..."
if ! aws ecr describe-repositories --repository-names ${ECR_REPOSITORY} --profile ${AWS_PROFILE} --region ${AWS_REGION} &> /dev/null; then
    echo "📦 Creating ECR repository..."
    aws ecr create-repository --repository-name ${ECR_REPOSITORY} --profile ${AWS_PROFILE} --region ${AWS_REGION}
fi

# Login to ECR
echo "🔑 Logging in to ECR..."
aws ecr get-login-password --profile ${AWS_PROFILE} --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Tag and push Docker image
echo "🏷️  Tagging Docker image..."
docker tag mcp-tool-lambda:latest ${ECR_URI}:latest

echo "📤 Pushing Docker image to ECR..."
docker push ${ECR_URI}:latest

# Deploy SAM template
echo "🚀 Deploying SAM template..."
sam deploy \
  --template-file mcp-tool-template.yaml \
  --stack-name ${STACK_NAME} \
  --image-repository ${ECR_URI} \
  --profile ${AWS_PROFILE} \
  --region ${AWS_REGION} \
  --parameter-overrides \
    Environment="$ENVIRONMENT" \
  --capabilities CAPABILITY_IAM \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset

# Get Lambda ARN
LAMBDA_ARN=$(aws cloudformation describe-stacks \
  --stack-name ${STACK_NAME} \
  --profile ${AWS_PROFILE} \
  --region ${AWS_REGION} \
  --query "Stacks[0].Outputs[?OutputKey=='MCPToolFunctionArn'].OutputValue" \
  --output text)

echo ""
echo "✅ Deployment completed successfully!"
echo "Lambda ARN: ${LAMBDA_ARN}"
echo ""

# Get Lambda Role ARN
LAMBDA_ROLE_ARN=$(aws cloudformation describe-stacks \
  --stack-name ${STACK_NAME} \
  --profile ${AWS_PROFILE} \
  --region ${AWS_REGION} \
  --query "Stacks[0].Outputs[?OutputKey=='MCPToolFunctionRoleArn'].OutputValue" \
  --output text)

echo "Lambda Role ARN: ${LAMBDA_ROLE_ARN}"
echo ""

echo "🎯 Next steps:"
echo "1. Copy the Function URL from above"
echo "2. Use it as the Bedrock AgentCore Target URL"
echo "3. Create Bedrock AgentCore Gateway with this target using the scripts:"
echo "   cd ../scripts"
echo "   python create-gateway.py --environment ${ENVIRONMENT}"
echo "   python create-target.py --environment ${ENVIRONMENT} --lambda-arn ${LAMBDA_ARN}"
echo "4. Test MCP protocol!"
echo ""
echo "⚠️  Note: Bedrock AgentCore Gateway APIs are only enabled for demo1 profile account"
