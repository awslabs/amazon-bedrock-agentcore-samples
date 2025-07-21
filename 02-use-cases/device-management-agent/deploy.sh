#!/bin/bash

# Deployment script for Device Management Lambda function

# Configuration
LAMBDA_FUNCTION_NAME="DeviceManagementLambda"
LAMBDA_ROLE_NAME="DeviceManagementLambdaRole"
REGION="us-west-2"
ZIP_FILE="lambda_package.zip"

echo "Packaging Lambda function..."

# Create a temporary directory for packaging
mkdir -p package

# Install dependencies to the package directory
pip install -r requirements.txt --target ./package

# Copy Lambda function files to the package directory
cp lambda_function.py dynamodb_models.py ./package/

# Create the ZIP file
cd package
zip -r ../$ZIP_FILE .
cd ..

echo "Lambda package created: $ZIP_FILE"

# Check if the Lambda function already exists
FUNCTION_EXISTS=$(aws lambda list-functions --region $REGION --query "Functions[?FunctionName=='$LAMBDA_FUNCTION_NAME'].FunctionName" --output text)

if [ -z "$FUNCTION_EXISTS" ]; then
    echo "Creating IAM role for Lambda function..."
    
    # Create IAM role
    ROLE_ARN=$(aws iam create-role \
        --role-name $LAMBDA_ROLE_NAME \
        --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }' \
        --query 'Role.Arn' \
        --output text)
    
    # Attach policies to the role
    aws iam attach-role-policy \
        --role-name $LAMBDA_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    # Create custom policy for DynamoDB access
    aws iam put-role-policy \
        --role-name $LAMBDA_ROLE_NAME \
        --policy-name DeviceManagementDynamoDBAccess \
        --policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:UpdateItem"
                ],
                "Resource": [
                    "arn:aws:dynamodb:us-west-2:*:table/Devices",
                    "arn:aws:dynamodb:us-west-2:*:table/DeviceSettings",
                    "arn:aws:dynamodb:us-west-2:*:table/WifiNetworks",
                    "arn:aws:dynamodb:us-west-2:*:table/Users",
                    "arn:aws:dynamodb:us-west-2:*:table/UserActivities",
                    "arn:aws:dynamodb:us-west-2:*:table/UserActivities/index/ActivityTypeIndex"
                ]
            }]
        }'
    
    echo "Waiting for role to propagate..."
    sleep 10
    
    echo "Creating Lambda function..."
    aws lambda create-function \
        --function-name $LAMBDA_FUNCTION_NAME \
        --runtime python3.12 \
        --handler lambda_function.lambda_handler \
        --role $ROLE_ARN \
        --zip-file fileb://$ZIP_FILE \
        --timeout 30 \
        --memory-size 256 \
        --region $REGION
else
    echo "Updating existing Lambda function..."
    aws lambda update-function-code \
        --function-name $LAMBDA_FUNCTION_NAME \
        --zip-file fileb://$ZIP_FILE \
        --region $REGION
fi

# Clean up
rm -rf package
rm -f $ZIP_FILE

echo "Deployment completed successfully!"
echo "Lambda function: $LAMBDA_FUNCTION_NAME"
