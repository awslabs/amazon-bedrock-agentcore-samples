#!/bin/bash
# ============================================================================
# Build and Verify Docker Image for AgentCore Runtime
# ============================================================================
# This script is called by Terraform during deployment to:
# 1. Trigger CodeBuild to build the Docker image
# 2. Wait for the build to complete
# 3. Verify the image was successfully pushed to ECR
#
# Parameters:
#   $1 - CodeBuild project name
#   $2 - AWS region
#   $3 - ECR repository name
#   $4 - Image tag
#   $5 - ECR repository URL

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parameters
PROJECT_NAME="$1"
REGION="$2"
REPO_NAME="$3"
IMAGE_TAG="$4"
REPO_URL="$5"

# ============================================================================
# Print functions
# ============================================================================

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================${NC}"
}

# ============================================================================
# Start Build Process
# ============================================================================

print_header "Building Docker Image for AgentCore Runtime"

print_info "CodeBuild Project: $PROJECT_NAME"
print_info "Region: $REGION"
print_info "Target Image: $REPO_URL:$IMAGE_TAG"
echo ""

# Start CodeBuild
print_info "Starting CodeBuild project..."

BUILD_ID=$(aws codebuild start-build \
  --project-name "$PROJECT_NAME" \
  --region "$REGION" \
  --query 'build.id' \
  --output text 2>&1)

if [ $? -ne 0 ]; then
  print_error "Failed to start CodeBuild"
  echo "$BUILD_ID"
  exit 1
fi

print_success "Build started: $BUILD_ID"
print_info "Waiting for build to complete (typically 5-10 minutes)..."
echo ""

# ============================================================================
# Monitor Build Progress
# ============================================================================

ATTEMPT=0
MAX_ATTEMPTS=60  # 10 minutes (60 * 10s)

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  ATTEMPT=$((ATTEMPT + 1))
  
  STATUS=$(aws codebuild batch-get-builds \
    --ids "$BUILD_ID" \
    --region "$REGION" \
    --query 'builds[0].buildStatus' \
    --output text 2>/dev/null)
  
  if [ "$STATUS" != "IN_PROGRESS" ]; then
    print_info "Build process completed with status: $STATUS"
    break
  fi
  
  # Progress indicator
  if [ $((ATTEMPT % 6)) -eq 0 ]; then
    MINUTES=$((ATTEMPT / 6))
    print_info "Build in progress... (${MINUTES} minutes elapsed)"
  fi
  
  sleep 10
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
  print_error "Build timeout after 10 minutes"
  print_warning "Check build status at: https://console.aws.amazon.com/codesuite/codebuild/projects/$PROJECT_NAME/history?region=$REGION"
  exit 1
fi

echo ""

# ============================================================================
# Verify Image in ECR
# ============================================================================

print_header "Verifying Docker Image in ECR"

print_info "Checking for image: $REPO_NAME:$IMAGE_TAG"
print_info "Waiting for ECR propagation..."
echo ""

sleep 5  # Brief wait for ECR to register the push

VERIFY_ATTEMPT=0
MAX_VERIFY_ATTEMPTS=12  # 1 minute (12 * 5s)

while [ $VERIFY_ATTEMPT -lt $MAX_VERIFY_ATTEMPTS ]; do
  VERIFY_ATTEMPT=$((VERIFY_ATTEMPT + 1))
  
  if aws ecr describe-images \
    --repository-name "$REPO_NAME" \
    --image-ids imageTag="$IMAGE_TAG" \
    --region "$REGION" >/dev/null 2>&1; then
    
    print_success "Docker image successfully verified in ECR!"
    echo ""
    print_info "Image URI: $REPO_URL:$IMAGE_TAG"
    
    # Get image details
    IMAGE_SIZE=$(aws ecr describe-images \
      --repository-name "$REPO_NAME" \
      --image-ids imageTag="$IMAGE_TAG" \
      --region "$REGION" \
      --query 'imageDetails[0].imageSizeInBytes' \
      --output text 2>/dev/null || echo "Unknown")
    
    if [ "$IMAGE_SIZE" != "Unknown" ]; then
      IMAGE_SIZE_MB=$((IMAGE_SIZE / 1024 / 1024))
      print_info "Image Size: ${IMAGE_SIZE_MB} MB"
    fi
    
    echo ""
    print_success "Build and verification completed successfully!"
    exit 0
  fi
  
  if [ $((VERIFY_ATTEMPT % 3)) -eq 0 ]; then
    print_info "Still waiting for image to appear in ECR... (attempt $VERIFY_ATTEMPT/$MAX_VERIFY_ATTEMPTS)"
  fi
  
  sleep 5
done

# ============================================================================
# Error: Image Not Found
# ============================================================================

print_error "Docker image not found in ECR after build completion"
echo ""
print_warning "This indicates the build or push step failed."
print_info "Troubleshooting steps:"
print_info "  1. Check CodeBuild logs:"
print_info "     https://console.aws.amazon.com/codesuite/codebuild/projects/$PROJECT_NAME/history?region=$REGION"
print_info ""
print_info "  2. Verify ECR repository:"
print_info "     aws ecr describe-images --repository-name $REPO_NAME --region $REGION"
print_info ""
print_info "  3. Check IAM permissions for CodeBuild role"

exit 1
