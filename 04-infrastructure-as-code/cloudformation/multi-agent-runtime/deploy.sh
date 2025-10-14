#!/bin/bash

# Deploy script for Multi-Agent Runtime CloudFormation stack
# This script deploys two AgentCore Runtimes where Agent1 can invoke Agent2

set -e

# Configuration
STACK_NAME="${1:-multi-agent-demo}"
REGION="${2:-us-west-2}"
TEMPLATE_FILE="template.yaml"

echo "=========================================="
echo "Deploying Multi-Agent Runtime"
echo "=========================================="
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo "=========================================="

# Check if template file exists
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "Error: Template file '$TEMPLATE_FILE' not found!"
    exit 1
fi

# Deploy the CloudFormation stack
echo ""
echo "Creating CloudFormation stack..."
aws cloudformation create-stack \
    --stack-name "$STACK_NAME" \
    --template-body file://"$TEMPLATE_FILE" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "$REGION"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Stack creation initiated successfully!"
    echo ""
    echo "Waiting for stack creation to complete..."
    echo "This will take approximately 15-20 minutes..."
    echo "(Building two Docker images and deploying two agents)"
    echo ""
    
    aws cloudformation wait stack-create-complete \
        --stack-name "$STACK_NAME" \
        --region "$REGION"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "=========================================="
        echo "✓ Stack deployed successfully!"
        echo "=========================================="
        echo ""
        echo "Stack Outputs:"
        aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs' \
            --output table \
            --region "$REGION"
        echo ""
        echo "Agent1 (Orchestrator) Runtime ARN:"
        aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[?OutputKey==`Agent1RuntimeArn`].OutputValue' \
            --output text \
            --region "$REGION"
        echo ""
        echo "Agent2 (Specialist) Runtime ARN:"
        aws cloudformation describe-stacks \
            --stack-name "$STACK_NAME" \
            --query 'Stacks[0].Outputs[?OutputKey==`Agent2RuntimeArn`].OutputValue' \
            --output text \
            --region "$REGION"
        echo ""
        echo "To delete this stack, run:"
        echo "  ./cleanup.sh $STACK_NAME $REGION"
        echo ""
    else
        echo ""
        echo "✗ Stack creation failed or timed out"
        echo "Check the CloudFormation console for details"
        exit 1
    fi
else
    echo ""
    echo "✗ Failed to initiate stack creation"
    exit 1
fi
