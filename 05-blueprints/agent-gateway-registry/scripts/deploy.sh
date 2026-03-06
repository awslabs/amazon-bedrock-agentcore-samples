#!/bin/bash
set -e

REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
STACK_NAME="agent-gateway-registry"
ECR_REPO="agent-registry-platform"
TABLE_NAME="agent-registry"

echo "Deploying Agent & Gateway Registry Platform"
echo "  Account: $ACCOUNT_ID"
echo "  Region:  $REGION"
echo ""

# Step 1: Deploy infrastructure (DynamoDB + ECR + App Runner + IAM)
echo "Step 1: Deploying infrastructure..."
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name $STACK_NAME \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides GatewayRegion=$REGION \
  --region $REGION

# Get outputs
APP_URL=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='AppUrl'].OutputValue" --output text)
ECR_URI=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='EcrUri'].OutputValue" --output text)
POOL_ID=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='CognitoPoolId'].OutputValue" --output text)
CLIENT_ID=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='CognitoClientId'].OutputValue" --output text)

echo ""
echo "Step 2: Building and pushing Docker image..."
cd platform-ui

# Login to ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

# Build and push
docker build --platform linux/amd64 -t $ECR_URI:latest .
docker push $ECR_URI:latest

echo ""
echo "Step 3: Updating App Runner service..."
SERVICE_ARN=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='ServiceArn'].OutputValue" --output text)
aws apprunner start-deployment --service-arn $SERVICE_ARN --region $REGION

echo ""
echo "Step 4: Creating admin user..."
aws cognito-idp admin-create-user \
  --user-pool-id $POOL_ID \
  --username admin@platform.local \
  --temporary-password Admin123! \
  --user-attributes Name=email,Value=admin@platform.local Name=email_verified,Value=true \
  --region $REGION 2>/dev/null || echo "  Admin user already exists"

echo ""
echo "============================================"
echo "  Deployment complete!"
echo ""
echo "  Platform URL: https://$APP_URL"
echo "  Login:        admin@platform.local / Admin123!"
echo ""
echo "  Cognito Pool: $POOL_ID"
echo "  DynamoDB:     $TABLE_NAME"
echo "============================================"
