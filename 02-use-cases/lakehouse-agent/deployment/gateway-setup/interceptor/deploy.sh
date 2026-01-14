#!/bin/bash
# Deploy Gateway Interceptor Lambda Function

set -e

echo "🚀 Deploying Gateway Interceptor Lambda"

# Get AWS region from default configuration
AWS_REGION=$(aws configure get region)
if [ -z "$AWS_REGION" ]; then
    echo "❌ Error: AWS region not configured"
    echo "   Please run: aws configure set region <your-region>"
    exit 1
fi

echo "   Region: $AWS_REGION"

# Read configuration from SSM Parameter Store
echo ""
echo "🔍 Loading configuration from SSM Parameter Store..."

# Temporarily disable exit on error to capture SSM errors
set +e
COGNITO_USER_POOL_ID=$(aws ssm get-parameter --name /app/lakehouse-agent/cognito-user-pool-id --query 'Parameter.Value' --output text 2>&1)
COGNITO_RESULT=$?

COGNITO_APP_CLIENT_ID=$(aws ssm get-parameter --name /app/lakehouse-agent/cognito-app-client-id --query 'Parameter.Value' --output text 2>&1)
CLIENT_RESULT=$?
set -e

if [ $COGNITO_RESULT -ne 0 ] || [ $CLIENT_RESULT -ne 0 ]; then
    echo "❌ Error: Required SSM parameters not found"
    echo ""
    if [ $COGNITO_RESULT -ne 0 ]; then
        echo "   Missing: /app/lakehouse-agent/cognito-user-pool-id"
        echo "   Error: $COGNITO_USER_POOL_ID"
    fi
    if [ $CLIENT_RESULT -ne 0 ]; then
        echo "   Missing: /app/lakehouse-agent/cognito-app-client-id"
        echo "   Error: $COGNITO_APP_CLIENT_ID"
    fi
    echo ""
    echo "   Please run setup_cognito.py first:"
    echo "   cd gateway-setup"
    echo "   python setup_cognito.py"
    exit 1
fi

echo "✅ Configuration loaded from SSM"
echo "   Cognito User Pool ID: $COGNITO_USER_POOL_ID"
echo "   Cognito App Client ID: $COGNITO_APP_CLIENT_ID"

# Package Lambda function
echo ""
echo "📦 Packaging Lambda function..."

mkdir -p dist
pip install -r requirements.txt -t dist/ --platform manylinux2014_x86_64 --only-binary=:all:
cp lambda_function.py dist/

cd dist
zip -r ../interceptor-lambda.zip .
cd ..

echo "✅ Package created: interceptor-lambda.zip"

# Create Lambda role using Python script
echo ""
echo "🔑 Creating Lambda execution role..."
cd ..
python create_lambda_role.py
cd interceptor

# Get the role ARN from SSM Parameter Store (stored by create_lambda_role.py)
LAMBDA_ROLE_ARN=$(aws ssm get-parameter --name /app/lakehouse-agent/interceptor-lambda-role-arn --query 'Parameter.Value' --output text 2>/dev/null)

# Fallback to direct IAM query if not in SSM yet
if [ -z "$LAMBDA_ROLE_ARN" ]; then
    echo "   Retrieving role ARN from IAM..."
    LAMBDA_ROLE_ARN=$(aws iam get-role --role-name InsuranceClaimsGatewayInterceptorRole --query 'Role.Arn' --output text 2>/dev/null)
fi

if [ -z "$LAMBDA_ROLE_ARN" ]; then
    echo "❌ Failed to retrieve Lambda role ARN"
    exit 1
fi

echo "✅ Lambda role ready: $LAMBDA_ROLE_ARN"

# Wait for IAM role to propagate (required for new roles)
echo "⏳ Waiting for IAM role to propagate (10 seconds)..."
sleep 10

# Check if Lambda function already exists
echo ""
echo "🔍 Checking if Lambda function exists..."
if aws lambda get-function --function-name lakehouse-gateway-interceptor --region $AWS_REGION 2>/dev/null; then
    echo "📝 Updating existing Lambda function..."
    aws lambda update-function-code \
        --function-name lakehouse-gateway-interceptor \
        --zip-file fileb://interceptor-lambda.zip \
        --region $AWS_REGION
    
    echo "⚙️  Updating Lambda configuration..."
    aws lambda update-function-configuration \
        --function-name lakehouse-gateway-interceptor \
        --environment "Variables={COGNITO_REGION=$AWS_REGION,COGNITO_USER_POOL_ID=$COGNITO_USER_POOL_ID,COGNITO_APP_CLIENT_ID=$COGNITO_APP_CLIENT_ID}" \
        --region $AWS_REGION
    
    echo "✅ Lambda function updated!"
else
    echo "📝 Creating new Lambda function..."
    
    # Retry logic for role propagation
    MAX_RETRIES=3
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if aws lambda create-function \
            --function-name lakehouse-gateway-interceptor \
            --runtime python3.11 \
            --role $LAMBDA_ROLE_ARN \
            --handler lambda_function.lambda_handler \
            --zip-file fileb://interceptor-lambda.zip \
            --timeout 30 \
            --memory-size 256 \
            --environment "Variables={COGNITO_REGION=$AWS_REGION,COGNITO_USER_POOL_ID=$COGNITO_USER_POOL_ID,COGNITO_APP_CLIENT_ID=$COGNITO_APP_CLIENT_ID}" \
            --region $AWS_REGION 2>/dev/null; then
            echo "✅ Lambda function created!"
            break
        else
            RETRY_COUNT=$((RETRY_COUNT + 1))
            if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                echo "⏳ Role not ready yet, waiting 5 seconds (attempt $RETRY_COUNT/$MAX_RETRIES)..."
                sleep 5
            else
                echo "❌ Failed to create Lambda function after $MAX_RETRIES attempts"
                echo "   The IAM role may need more time to propagate"
                exit 1
            fi
        fi
    done
fi

# Store Lambda function ARN in SSM Parameter Store
echo ""
echo "💾 Storing Lambda function ARN in SSM Parameter Store..."
LAMBDA_FUNCTION_ARN=$(aws lambda get-function --function-name lakehouse-gateway-interceptor --region $AWS_REGION --query 'Configuration.FunctionArn' --output text)

aws ssm put-parameter \
    --name /app/lakehouse-agent/interceptor-lambda-arn \
    --value "$LAMBDA_FUNCTION_ARN" \
    --type String \
    --overwrite \
    --region $AWS_REGION

echo "✅ Stored parameter: /app/lakehouse-agent/interceptor-lambda-arn"

echo ""
echo "✨ Deployment complete!"
echo ""
echo "📝 Lambda Function ARN: $LAMBDA_FUNCTION_ARN"
