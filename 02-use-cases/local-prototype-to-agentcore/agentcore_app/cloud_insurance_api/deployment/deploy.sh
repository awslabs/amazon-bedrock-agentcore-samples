#!/bin/bash
set -e

# Deploy script for the Insurance API Lambda function

# Check for AWS CLI
if ! command -v aws &> /dev/null
then
    echo "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check for SAM CLI
if ! command -v sam &> /dev/null
then
    echo "AWS SAM CLI is not installed. Please install it first."
    exit 1
fi

# Get AWS account ID and region
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)

# Set variables
STAGE=${1:-dev}  # Default to dev if not specified
STACK_NAME="insurance-api-$STAGE"
S3_BUCKET="insurance-api-$STAGE-$ACCOUNT_ID-$REGION"

echo "=== Insurance API Deployment ==="
echo "Stage: $STAGE"
echo "Account ID: $ACCOUNT_ID"
echo "Region: $REGION"
echo "Stack name: $STACK_NAME"
echo "S3 Bucket: $S3_BUCKET"

# Create S3 bucket if it doesn't exist
if ! aws s3api head-bucket --bucket $S3_BUCKET 2>/dev/null; then
    echo "Creating S3 bucket: $S3_BUCKET"
    aws s3 mb s3://$S3_BUCKET
fi

# Create a build directory for packaging
echo "Creating build package..."
mkdir -p build

# Copy necessary files
cp -r ../local_insurance_api build/
cp ../lambda_function.py build/
cp template.yaml build/

# Create a data directory in build and copy data files
mkdir -p build/data
cp ../local_insurance_api/data/*.json build/data/

# Install dependencies in the build directory
echo "Installing dependencies..."
pip install -r ../local_insurance_api/requirements.txt -t build/

# Package the application
echo "Packaging the application..."
sam package \
    --template-file build/template.yaml \
    --output-template-file build/packaged.yaml \
    --s3-bucket $S3_BUCKET

# Deploy the application
echo "Deploying the application..."
sam deploy \
    --template-file build/packaged.yaml \
    --stack-name $STACK_NAME \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --parameter-overrides EnvironmentType="$STAGE"

echo "=== Deployment Complete ==="
