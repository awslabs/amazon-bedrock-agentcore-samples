#!/bin/bash

set -e  # Exit on error

echo "🚀 Building and deploying Bedrock Agent Stack..."
echo ""

# Install Python CDK dependencies
echo "📦 Installing Python CDK dependencies..."
pip install -r src/cdk_requirements.txt

echo ""

# Build frontend
echo "📦 Installing frontend dependencies..."
cd frontend
npm install

echo "🔨 Building React app..."
npm run build

cd ..

echo ""
echo "☁️  Deploying CDK stack..."
echo "   - Infrastructure (API Gateway, Lambda, DynamoDB, SQS)"
echo "   - Frontend (S3 + CloudFront)"
echo "   - Auto-generating config.js with API credentials"
echo ""

# Set region to us-east-1 (or use AWS_DEFAULT_REGION if set)
export CDK_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}
echo "   Deploying to region: $CDK_DEFAULT_REGION"
echo ""

cd src
cdk bootstrap
cd ..
cdk deploy --require-approval never --app "python3 src/cdk_app.py"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Stack Outputs:"
echo "   Check the outputs above for:"
echo "   - Frontend URL (CloudFront)"
echo "   - API Endpoint"
echo "   - API Key ID"
echo ""
echo "💡 The config.js file has been automatically generated and deployed."
echo "   Your frontend is ready to use at the CloudFront URL above."