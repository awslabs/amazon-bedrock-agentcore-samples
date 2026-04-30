#!/bin/bash

# Unified deployment script for AgentCore CloudFormation samples across environments

set -e

ENV="${1:-dev}"
SAMPLE_NAME="${2:-basic-runtime}"
REGION="${3:-us-east-1}"
STACK_NAME="agentcore-${SAMPLE_NAME}-${ENV}"
if [ -f "${SAMPLE_NAME}/${SAMPLE_NAME}.yaml" ]; then
    TEMPLATE_FILE="${SAMPLE_NAME}/${SAMPLE_NAME}.yaml"
else
    TEMPLATE_FILE="${SAMPLE_NAME}/template.yaml"
fi

echo "=========================================="
echo "Deploying AgentCore Environment: ${ENV^^}"
echo "=========================================="
echo "Sample: $SAMPLE_NAME"
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo "=========================================="

if [ ! -d "$SAMPLE_NAME" ]; then
    echo "Error: Sample directory '$SAMPLE_NAME' not found!"
    exit 1
fi

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "Error: Template file '$TEMPLATE_FILE' not found!"
    exit 1
fi

echo "Initiating CloudFormation stack deployment..."
aws cloudformation deploy \
    --stack-name "$STACK_NAME" \
    --template-file "$TEMPLATE_FILE" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION" \
    --tags Environment="$ENV" Project="AgentCoreSamples"

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ Environment '${ENV^^}' deployed successfully!"
    echo "=========================================="
    echo ""
    echo "Stack Outputs:"
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query 'Stacks[0].Outputs' \
        --output table \
        --region "$REGION"
else
    echo ""
    echo "✗ Stack deployment failed"
    exit 1
fi
