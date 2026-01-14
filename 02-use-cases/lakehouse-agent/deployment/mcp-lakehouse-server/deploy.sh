#!/bin/bash
# Deploy MCP Athena Server to AWS Lambda or AgentCore Runtime

set -e

echo "🚀 Deploying Health Lakehouse Data MCP Server"

# Check environment variables
if [ -z "$AWS_REGION" ]; then
    AWS_REGION="us-east-1"
fi

if [ -z "$S3_OUTPUT_BUCKET" ]; then
    echo "❌ Error: S3_OUTPUT_BUCKET environment variable is required"
    echo "   Set it to the bucket name for Athena query results"
    exit 1
fi

echo "   Region: $AWS_REGION"
echo "   S3 Bucket: $S3_OUTPUT_BUCKET"

# Option 1: Deploy as AgentCore Gateway Target (MCP Server via Lambda)
echo ""
echo "📦 Packaging MCP server..."

# Create deployment package
mkdir -p dist
pip install -r requirements.txt -t dist/
cp server.py dist/
cp athena_tools.py dist/

cd dist
zip -r ../mcp-server.zip .
cd ..

echo "✅ Package created: mcp-server.zip"

# Option 2: Deploy using agentcore CLI (if using Runtime)
echo ""
echo "To deploy using agentcore CLI:"
echo "  agentcore configure -e server.py"
echo "  agentcore launch"
echo ""
echo "To deploy as Lambda function:"
echo "  aws lambda create-function \\"
echo "    --function-name lakehouse-mcp-server \\"
echo "    --runtime python3.11 \\"
echo "    --role YOUR_LAMBDA_ROLE_ARN \\"
echo "    --handler server.handle_request \\"
echo "    --zip-file fileb://mcp-server.zip \\"
echo "    --environment Variables={AWS_REGION=$AWS_REGION,ATHENA_DATABASE=lakehouse_db,S3_OUTPUT_BUCKET=$S3_OUTPUT_BUCKET} \\"
echo "    --timeout 60 \\"
echo "    --memory-size 512"

echo ""
echo "✨ Deployment package ready!"
