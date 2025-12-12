#!/bin/bash

# ============================================================================
# Destroy Script for End-to-End Weather Agent (Terraform)
# ============================================================================
# This script safely destroys all resources created by this Terraform configuration
# Usage: ./destroy.sh

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

print_warning "Starting Resource Cleanup..."
echo ""

# Check Terraform installation
if ! command_exists terraform; then
    print_error "Terraform is not installed"
    exit 1
fi

# Check AWS CLI installation
if ! command_exists aws; then
    print_error "AWS CLI is not installed"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    print_error "AWS credentials are not configured or invalid"
    exit 1
fi

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)
print_info "AWS Account: $AWS_ACCOUNT"
print_info "AWS Region: $AWS_REGION"

echo ""

# ============================================================================
# Check for Terraform State
# ============================================================================

if [ ! -f "terraform.tfstate" ] && [ ! -f ".terraform/terraform.tfstate" ]; then
    print_warning "No Terraform state found"
    print_info "Either no resources have been deployed, or state is stored remotely"
    
    read -p "Do you want to attempt to import state from backend? (yes/no): " -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        print_info "Initializing Terraform to fetch remote state..."
        terraform init
    else
        print_info "Cleanup cancelled"
        exit 0
    fi
fi

# ============================================================================
# Show Destruction Plan
# ============================================================================

print_info "Creating destruction plan..."
echo ""

if ! terraform plan -destroy; then
    print_error "Failed to create destruction plan"
    exit 1
fi

echo ""

# ============================================================================
# Destruction Confirmation
# ============================================================================

print_warning "========================================"
print_warning "RESOURCE DESTRUCTION CONFIRMATION"
print_warning "========================================"
print_warning "This will permanently delete the following resources:"
print_warning "  - Weather Agent Runtime"
print_warning "  - Browser Tool"
print_warning "  - Code Interpreter Tool"
print_warning "  - Memory Resource (with all conversation history)"
print_warning "  - Memory Initializer Lambda"
print_warning "  - 2x S3 Buckets (source code + results storage)"
print_warning "  - 1x ECR Repository (including all images)"
print_warning "  - 1x CodeBuild Project"
print_warning "  - IAM Roles and Policies (agent + tools + Lambda)"
print_warning "  - CloudWatch Log Groups"
echo ""
print_warning "THIS ACTION CANNOT BE UNDONE!"
echo ""
print_info "Resources in other AWS services (e.g., S3 buckets) may still incur costs"
echo ""

read -p "Are you absolutely sure you want to destroy all resources? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    print_info "Destruction cancelled by user"
    exit 0
fi

# Double confirmation for safety
print_warning "Second confirmation required..."
read -p "Type 'DESTROY' to confirm: " -r
echo ""

if [ "$REPLY" != "DESTROY" ]; then
    print_info "Destruction cancelled - confirmation text did not match"
    exit 0
fi

# ============================================================================
# Execute Destruction
# ============================================================================

print_warning "Starting resource destruction..."
echo ""

if terraform destroy -auto-approve; then
    print_success "All resources destroyed successfully"
else
    print_error "Destruction failed"
    print_warning "Some resources may still exist. Please check AWS Console"
    exit 1
fi

echo ""

# ============================================================================
# Cleanup Local Files
# ============================================================================

print_info "Cleaning up local Terraform files..."

# Ask about state file cleanup
read -p "Do you want to remove local Terraform state files? (yes/no): " -r
echo ""

if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    rm -f terraform.tfstate
    rm -f terraform.tfstate.backup
    rm -f tfplan
    print_success "Local state files removed"
fi

# Ask about .terraform directory
read -p "Do you want to remove .terraform directory? (yes/no): " -r
echo ""

if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    rm -rf .terraform
    rm -f .terraform.lock.hcl
    print_success ".terraform directory removed"
fi

echo ""

# ============================================================================
# Verification
# ============================================================================

print_info "Verifying resource cleanup..."
echo ""

# Check for ECR repositories
STACK_NAME=$(grep 'stack_name' terraform.tfvars 2>/dev/null | cut -d'"' -f2 || echo "agentcore-basic")
ECR_REPOS=$(aws ecr describe-repositories --region $AWS_REGION 2>/dev/null | grep "$STACK_NAME" | wc -l | tr -d ' ')

if [ "$ECR_REPOS" -eq 0 ]; then
    print_success "ECR repositories cleaned up"
else
    print_warning "Found $ECR_REPOS ECR repositories matching '$STACK_NAME'"
    print_info "These may need manual cleanup"
fi

# Check for AgentCore runtimes
RUNTIME_COUNT=$(aws bedrock-agentcore list-agent-runtimes --region $AWS_REGION 2>/dev/null | grep "$STACK_NAME" | wc -l | tr -d ' ')

if [ "$RUNTIME_COUNT" -eq 0 ]; then
    print_success "Weather Agent runtime cleaned up"
else
    print_warning "Found $RUNTIME_COUNT AgentCore runtime(s) matching '$STACK_NAME'"
    print_info "These may need manual cleanup"
fi

# Check for Memory resources
MEMORY_COUNT=$(aws bedrock-agentcore list-memories --region $AWS_REGION 2>/dev/null | grep "$STACK_NAME" | wc -l | tr -d ' ')

if [ "$MEMORY_COUNT" -eq 0 ]; then
    print_success "Memory resources cleaned up"
else
    print_warning "Found $MEMORY_COUNT Memory resource(s) matching '$STACK_NAME'"
    print_info "These may need manual cleanup"
fi

# Check for Tools (Browser and Code Interpreter)
TOOL_COUNT=$(aws bedrock-agentcore list-browser-customs --region $AWS_REGION 2>/dev/null | grep "$STACK_NAME" | wc -l | tr -d ' ')
TOOL_COUNT=$((TOOL_COUNT + $(aws bedrock-agentcore list-code-interpreter-customs --region $AWS_REGION 2>/dev/null | grep "$STACK_NAME" | wc -l | tr -d ' ')))

if [ "$TOOL_COUNT" -eq 0 ]; then
    print_success "Tools (Browser + Code Interpreter) cleaned up"
else
    print_warning "Found $TOOL_COUNT Tool(s) matching '$STACK_NAME'"
    print_info "These may need manual cleanup"
fi

# Check for Lambda functions
LAMBDA_COUNT=$(aws lambda list-functions --region $AWS_REGION 2>/dev/null | grep "$STACK_NAME" | wc -l | tr -d ' ')

if [ "$LAMBDA_COUNT" -eq 0 ]; then
    print_success "Lambda functions cleaned up"
else
    print_warning "Found $LAMBDA_COUNT Lambda function(s) matching '$STACK_NAME'"
    print_info "These may need manual cleanup"
fi

# Check for S3 buckets (source + results)
S3_BUCKETS=$(aws s3api list-buckets --region $AWS_REGION 2>/dev/null | grep "$STACK_NAME" | wc -l | tr -d ' ')

if [ "$S3_BUCKETS" -eq 0 ]; then
    print_success "S3 buckets cleaned up (source + results)"
else
    print_warning "Found $S3_BUCKETS S3 bucket(s) matching '$STACK_NAME'"
    print_info "These may need manual cleanup"
fi

echo ""

# ============================================================================
# Completion Summary
# ============================================================================

print_success "========================================"
print_success "CLEANUP COMPLETED"
print_success "========================================"
echo ""

print_info "Cleanup Summary:"
print_success "  ✓ Terraform resources destroyed"
print_success "  ✓ Local state files cleaned (if selected)"
echo ""

print_info "What to verify in AWS Console:"
print_info "1. Bedrock AgentCore - No runtimes remaining"
print_info "   https://console.aws.amazon.com/bedrock/home?region=$AWS_REGION#/agentcore"
echo ""
print_info "2. Memory - No memory resources remaining"
print_info "   Check via: aws bedrock-agentcore list-memories --region $AWS_REGION"
echo ""
print_info "3. Tools - No browser/code interpreter tools remaining"
print_info "   Check via: aws bedrock-agentcore list-browser-customs --region $AWS_REGION"
echo ""
print_info "4. Lambda - No memory initializer functions remaining"
print_info "   https://console.aws.amazon.com/lambda/home?region=$AWS_REGION#/functions"
echo ""
print_info "5. S3 - No buckets remaining (source + results)"
print_info "   https://console.aws.amazon.com/s3/buckets?region=$AWS_REGION"
echo ""
print_info "6. ECR - No repositories remaining"
print_info "   https://console.aws.amazon.com/ecr/repositories?region=$AWS_REGION"
echo ""
print_info "7. CodeBuild - No projects remaining"
print_info "   https://console.aws.amazon.com/codesuite/codebuild/projects?region=$AWS_REGION"
echo ""
print_info "8. CloudWatch Logs - Check for orphaned log groups"
print_info "   https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#logsV2:log-groups"
echo ""

print_success "Cleanup completed successfully!"
print_info "You can safely re-deploy by running: ./deploy.sh"
