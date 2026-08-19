#!/bin/bash

# ============================================================================
# Deploy Script for MCP Server on AgentCore Runtime (Terraform)
# ============================================================================
# This script automates the deployment process for the Terraform configuration
# Usage: ./deploy.sh

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

print_info "Starting MCP Server on AgentCore Runtime Deployment..."
echo ""

# Check Terraform installation
if ! command_exists terraform; then
    print_error "Terraform is not installed. Please install Terraform >= 1.6"
    print_info "Visit: https://www.terraform.io/downloads"
    exit 1
fi

# Check Terraform version
TERRAFORM_VERSION=$(terraform version -json | grep -o '"terraform_version":"[^"]*' | cut -d'"' -f4)
print_success "Terraform version: $TERRAFORM_VERSION"

# Check AWS CLI installation
if ! command_exists aws; then
    print_error "AWS CLI is not installed. Please install and configure AWS CLI"
    print_info "Visit: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

print_success "AWS CLI is installed"

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    print_error "AWS credentials are not configured or invalid"
    print_info "Run: aws configure"
    exit 1
fi

AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)
print_success "AWS Account: $AWS_ACCOUNT"
print_success "AWS Region: $AWS_REGION"

echo ""

# ============================================================================
# Configuration Check
# ============================================================================

print_info "Checking configuration files..."

# Check if terraform.tfvars exists
if [ ! -f "terraform.tfvars" ]; then
    print_warning "terraform.tfvars not found"
    print_info "Creating terraform.tfvars from example..."
    
    if [ -f "terraform.tfvars.example" ]; then
        cp terraform.tfvars.example terraform.tfvars
        print_success "Created terraform.tfvars"
        print_warning "Please review and update terraform.tfvars with your settings"
        print_info "Then run this script again"
        exit 0
    else
        print_error "terraform.tfvars.example not found"
        exit 1
    fi
fi

print_success "Configuration file found: terraform.tfvars"
echo ""

# ============================================================================
# Terraform Initialization
# ============================================================================

print_info "Initializing Terraform..."
if terraform init; then
    print_success "Terraform initialized successfully"
else
    print_error "Terraform initialization failed"
    exit 1
fi

echo ""

# ============================================================================
# Terraform Validation
# ============================================================================

print_info "Validating Terraform configuration..."
if terraform validate; then
    print_success "Terraform configuration is valid"
else
    print_error "Terraform validation failed"
    exit 1
fi

echo ""

# ============================================================================
# Terraform Format Check
# ============================================================================

print_info "Checking Terraform formatting..."
if terraform fmt -check -recursive > /dev/null 2>&1; then
    print_success "Terraform files are properly formatted"
else
    print_warning "Some files need formatting. Running terraform fmt..."
    terraform fmt -recursive
    print_success "Files formatted"
fi

echo ""

# ============================================================================
# Terraform Plan
# ============================================================================

print_info "Creating Terraform execution plan..."
print_warning "This may take a few moments..."
echo ""

if terraform plan -out=tfplan; then
    print_success "Terraform plan created successfully"
else
    print_error "Terraform plan failed"
    exit 1
fi

echo ""

# ============================================================================
# Deployment Confirmation
# ============================================================================

print_warning "========================================"
print_warning "DEPLOYMENT CONFIRMATION"
print_warning "========================================"
print_info "This will deploy the following resources:"
print_info "  - S3 Bucket (source code storage)"
print_info "  - ECR Repository"
print_info "  - CodeBuild Project"
print_info "  - Cognito User Pool + Client (JWT authentication)"
print_info "  - IAM Roles and Policies"
print_info "  - AgentCore Runtime (with MCP protocol)"
echo ""
print_info "The deployment includes:"
print_info "  - Building ARM64 Docker image with MCP server"
print_info "  - Creating AWS resources"
print_info "  - Setting up JWT authentication with test user"
echo ""

read -p "Do you want to proceed with deployment? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    print_info "Deployment cancelled by user"
    rm -f tfplan
    exit 0
fi

# ============================================================================
# Terraform Apply
# ============================================================================

print_info "Starting deployment..."
echo ""

if terraform apply tfplan; then
    print_success "Deployment completed successfully!"
else
    print_error "Deployment failed"
    rm -f tfplan
    exit 1
fi

# Clean up plan file
rm -f tfplan

echo ""

# ============================================================================
# Deployment Summary
# ============================================================================

print_success "========================================"
print_success "DEPLOYMENT COMPLETED"
print_success "========================================"
echo ""

print_info "Retrieving deployment outputs..."
echo ""

# Get outputs
RUNTIME_ID=$(terraform output -raw agent_runtime_id 2>/dev/null || echo "N/A")
RUNTIME_ARN=$(terraform output -raw agent_runtime_arn 2>/dev/null || echo "N/A")
ECR_URL=$(terraform output -raw ecr_repository_url 2>/dev/null || echo "N/A")
USER_POOL_ID=$(terraform output -raw cognito_user_pool_id 2>/dev/null || echo "N/A")
CLIENT_ID=$(terraform output -raw cognito_user_pool_client_id 2>/dev/null || echo "N/A")

print_success "Agent Runtime ID: $RUNTIME_ID"
print_success "Agent Runtime ARN: $RUNTIME_ARN"
print_success "ECR Repository URL: $ECR_URL"
print_success "Cognito User Pool ID: $USER_POOL_ID"
print_success "Cognito Client ID: $CLIENT_ID"

echo ""
print_info "Next Steps:"
print_info "1. Get JWT token for authentication:"
print_info "   terraform output -raw get_token_command | bash"
echo ""
print_info "2. Test the MCP server:"
print_info "   # Export the JWT token from step 1, then:"
print_info "   python test_mcp_server.py $RUNTIME_ARN \$JWT_TOKEN $AWS_REGION"
echo ""
print_info "3. View all outputs:"
print_info "   terraform output"
echo ""
print_info "4. Monitor in AWS Console:"
print_info "   https://console.aws.amazon.com/bedrock/home?region=$AWS_REGION#/agentcore"
echo ""
print_success "Deployment completed successfully!"
