#!/bin/bash
set -e

PROJECT_NAME=${PROJECT_NAME:-agentic-sales-analyst}
REGION=${AWS_REGION:-us-east-1}

echo "🗑️  Cleaning up shared infrastructure"
echo "Project: $PROJECT_NAME"
echo "Region: $REGION"
echo ""
echo "⚠️  WARNING: This will delete:"
echo "  - ECR repository (and all container images)"
echo "  - IAM roles"
echo "  - VPC and networking"
echo ""
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cleanup cancelled"
    exit 0
fi

wait_for_delete() {
    local stack_name=$1
    echo "⏳ Waiting for stack $stack_name to delete..."
    aws cloudformation wait stack-delete-complete \
        --stack-name $stack_name \
        --region $REGION 2>/dev/null || true
    echo "✅ Stack $stack_name deleted"
}

echo ""
echo "Emptying ECR repository..."
REPO_NAME="${PROJECT_NAME}"

# Check if repository exists
if aws ecr describe-repositories --repository-names $REPO_NAME --region $REGION >/dev/null 2>&1; then
    # Get image digests
    IMAGE_DIGESTS=$(aws ecr list-images \
        --repository-name $REPO_NAME \
        --region $REGION \
        --query 'imageIds[?imageDigest!=`null`].[imageDigest]' \
        --output text 2>/dev/null)
    
    if [ -n "$IMAGE_DIGESTS" ]; then
        echo "Deleting images from $REPO_NAME..."
        echo "$IMAGE_DIGESTS" | while read digest; do
            if [ -n "$digest" ]; then
                aws ecr batch-delete-image \
                    --repository-name $REPO_NAME \
                    --region $REGION \
                    --image-ids imageDigest=$digest 2>/dev/null || true
            fi
        done
        echo "✅ Images deleted"
    else
        echo "No images to delete"
    fi
else
    echo "Repository does not exist, skipping image cleanup"
fi

echo ""
echo "Deleting ECR repository..."
aws cloudformation delete-stack \
    --stack-name ${PROJECT_NAME}-ecr \
    --region $REGION 2>/dev/null || true
wait_for_delete ${PROJECT_NAME}-ecr

echo ""
echo "Deleting IAM roles..."
aws cloudformation delete-stack \
    --stack-name ${PROJECT_NAME}-iam \
    --region $REGION 2>/dev/null || true
wait_for_delete ${PROJECT_NAME}-iam

echo ""
echo "Deleting network infrastructure..."
aws cloudformation delete-stack \
    --stack-name ${PROJECT_NAME}-network \
    --region $REGION 2>/dev/null || true
wait_for_delete ${PROJECT_NAME}-network

echo ""
echo "✅ Infrastructure cleanup complete!"
