#!/bin/bash
set -e

PROJECT_NAME=${PROJECT_NAME:-agentic-sales-analyst}
REGION=${AWS_REGION:-ap-southeast-2}

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
    echo "Deleting all images from $REPO_NAME..."
    
    # Get all image IDs (both tagged and untagged)
    IMAGE_IDS=$(aws ecr list-images \
        --repository-name $REPO_NAME \
        --region $REGION \
        --query 'imageIds' \
        --output json 2>/dev/null)
    
    if [ "$IMAGE_IDS" != "[]" ] && [ -n "$IMAGE_IDS" ]; then
        # Delete all images with force flag to handle manifest lists
        echo "Force deleting all images (including manifest lists)..."
        aws ecr batch-delete-image \
            --repository-name $REPO_NAME \
            --region $REGION \
            --image-ids "$IMAGE_IDS" \
            --force 2>/dev/null || true
        echo "✅ All images force deleted from $REPO_NAME"
    else
        echo "No images to delete in $REPO_NAME"
    fi
else
    echo "Repository $REPO_NAME does not exist, skipping image cleanup"
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
