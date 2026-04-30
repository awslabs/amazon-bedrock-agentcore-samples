#!/bin/bash

# Unified rollback script for AgentCore CloudFormation environments

set -e

ENV="${1:-dev}"
SAMPLE_NAME="${2:-basic-runtime}"
REGION="${3:-us-east-1}"
STACK_NAME="agentcore-${SAMPLE_NAME}-${ENV}"

echo "=========================================="
echo "Rolling back AgentCore Environment: ${ENV^^}"
echo "=========================================="
echo "Sample: $SAMPLE_NAME"
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo "=========================================="

# If this is the weather agent, we must attempt to empty the S3 bucket first
if [ "$SAMPLE_NAME" == "end-to-end-weather-agent" ]; then
    echo "Attempting to empty S3 bucket for weather agent..."
    BUCKET_NAME=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`ResultsBucket`].OutputValue' \
        --output text || echo "None")
    
    if [ "$BUCKET_NAME" != "None" ] && [ -n "$BUCKET_NAME" ]; then
        aws s3 rm "s3://$BUCKET_NAME" --recursive || echo "Bucket already empty or failed to empty."
    fi
fi

echo "Initiating CloudFormation stack deletion..."
aws cloudformation delete-stack \
    --stack-name "$STACK_NAME" \
    --region "$REGION"

echo "Waiting for stack deletion to complete..."
aws cloudformation wait stack-delete-complete \
    --stack-name "$STACK_NAME" \
    --region "$REGION"

echo ""
echo "=========================================="
echo "✓ Environment '${ENV^^}' rolled back successfully!"
echo "=========================================="
