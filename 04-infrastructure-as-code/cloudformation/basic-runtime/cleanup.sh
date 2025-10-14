#!/bin/bash

# Cleanup script for Basic Agent Runtime CloudFormation stack
# This script deletes the CloudFormation stack and all associated resources

set -e

# Configuration
STACK_NAME="${1:-basic-agent-demo}"
REGION="${2:-us-west-2}"

echo "=========================================="
echo "Cleaning up Basic Agent Runtime"
echo "=========================================="
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo "=========================================="

# Confirm deletion
read -p "Are you sure you want to delete the stack '$STACK_NAME'? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Deleting CloudFormation stack..."
aws cloudformation delete-stack \
    --stack-name "$STACK_NAME" \
    --region "$REGION"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Stack deletion initiated successfully!"
    echo ""
    echo "Waiting for stack deletion to complete..."
    echo "This may take a few minutes..."
    echo ""
    
    aws cloudformation wait stack-delete-complete \
        --stack-name "$STACK_NAME" \
        --region "$REGION"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "=========================================="
        echo "✓ Stack deleted successfully!"
        echo "=========================================="
        echo ""
        echo "All resources have been cleaned up."
        echo ""
    else
        echo ""
        echo "✗ Stack deletion failed or timed out"
        echo "Check the CloudFormation console for details"
        exit 1
    fi
else
    echo ""
    echo "✗ Failed to initiate stack deletion"
    exit 1
fi
