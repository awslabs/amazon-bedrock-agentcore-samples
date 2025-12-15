#!/bin/bash
# Cleanup script for MCP Server deployment

set -e

STACK_NAME="${1:-mcp-server-demo}"
REGION="${2:-us-west-2}"

echo "=========================================="
echo "MCP Server Cleanup Script"
echo "=========================================="
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo ""

read -p "⚠️  This will delete all resources. Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled"
    exit 0
fi

echo ""
echo "🗑️  Deleting CloudFormation stack..."
aws cloudformation delete-stack \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo "✓ Stack deletion initiated"
echo ""
echo "⏳ Waiting for stack deletion to complete..."
aws cloudformation wait stack-delete-complete \
  --stack-name "$STACK_NAME" \
  --region "$REGION"

echo ""
echo "=========================================="
echo "✅ Cleanup Complete!"
echo "=========================================="
echo ""
echo "All resources have been deleted."
echo ""
