#!/bin/bash
set -e

PROJECT_NAME=${PROJECT_NAME:-agentic-sales-analyst}
REGION=${AWS_REGION:-us-east-1}

echo "🗑️  Cleaning up ECS-specific resources"
echo "Project: $PROJECT_NAME"
echo "Region: $REGION"

wait_for_delete() {
    local stack_name=$1
    echo "⏳ Waiting for stack $stack_name to delete..."
    aws cloudformation wait stack-delete-complete \
        --stack-name $stack_name \
        --region $REGION 2>/dev/null || true
    echo "✅ Stack $stack_name deleted"
}

echo ""
echo "Deleting ECS service..."
aws cloudformation delete-stack \
    --stack-name ${PROJECT_NAME}-ecs-service \
    --region $REGION 2>/dev/null || true
wait_for_delete ${PROJECT_NAME}-ecs-service

echo ""
echo "Deleting ECS cluster..."
aws cloudformation delete-stack \
    --stack-name ${PROJECT_NAME}-ecs-cluster \
    --region $REGION 2>/dev/null || true
wait_for_delete ${PROJECT_NAME}-ecs-cluster

echo ""
echo "✅ ECS cleanup complete!"
echo ""
echo "To delete shared infrastructure (network, IAM, ECR):"
echo "  cd .."
echo "  ./cleanup-infrastructure.sh"
