#!/bin/bash
set -e

echo "Creating IAM roles for AgentCore Gateway..."

# Get account ID and region
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=${AWS_REGION:-"us-west-2"}

# Check if roles already exist and get their ARNs
GATEWAY_ROLE_ARN=""
LAMBDA_ROLE_ARN=""

# Check if Gateway role exists
GATEWAY_ROLE_EXISTS=$(aws iam get-role --role-name AgentCoreGatewayRole 2>/dev/null || echo "not_exists")
if [[ $GATEWAY_ROLE_EXISTS != "not_exists" ]]; then
    echo "Gateway role already exists, getting ARN..."
    GATEWAY_ROLE_ARN=$(echo $GATEWAY_ROLE_EXISTS | jq -r '.Role.Arn')
    echo "Found Gateway Role ARN: $GATEWAY_ROLE_ARN"
else
    # Create Gateway execution role with trust policy
    TRUST_POLICY='{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "GatewayAssumeRolePolicy",
          "Effect": "Allow",
          "Principal": {
            "Service": "bedrock-agentcore.amazonaws.com"
          },
          "Action": "sts:AssumeRole",
          "Condition": {
            "StringEquals": {
              "aws:SourceAccount": "'$ACCOUNT_ID'"
            },
            "ArnLike": {
              "aws:SourceArn": "arn:aws:bedrock-agentcore:'$REGION':'$ACCOUNT_ID':gateway/*"
            }
          }
        }
      ]
    }'

    # Create the Gateway role
    echo "Creating Gateway execution role..."
    ROLE_RESPONSE=$(aws iam create-role \
      --role-name AgentCoreGatewayRole \
      --assume-role-policy-document "$TRUST_POLICY")

    GATEWAY_ROLE_ARN=$(echo $ROLE_RESPONSE | jq -r '.Role.Arn')
fi

# Create Lambda execution policy
LAMBDA_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AmazonBedrockAgentCoreGatewayLambdaProd",
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": [
        "arn:aws:lambda:'$REGION':'$ACCOUNT_ID':function:*:*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:ResourceAccount": "'$ACCOUNT_ID'"
        }
      }
    }
  ]
}'

# Attach Lambda execution policy
aws iam put-role-policy \
  --role-name AgentCoreGatewayRole \
  --policy-name GatewayLambdaExecutionPolicy \
  --policy-document "$LAMBDA_POLICY"

# Create Gateway management policy
GATEWAY_MGMT_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:*Gateway*",
        "bedrock-agentcore:*WorkloadIdentity",
        "bedrock-agentcore:*CredentialProvider",
        "bedrock-agentcore:*Token*",
        "bedrock-agentcore:*Access*"
      ],
      "Resource": "arn:aws:bedrock-agentcore:*:*:*gateway*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}'

# Attach Gateway management policy
aws iam put-role-policy \
  --role-name AgentCoreGatewayRole \
  --policy-name GatewayManagementPolicy \
  --policy-document "$GATEWAY_MGMT_POLICY"

# Check if Lambda role exists
LAMBDA_ROLE_EXISTS=$(aws iam get-role --role-name DBAnalyzerLambdaRole 2>/dev/null || echo "not_exists")
if [[ $LAMBDA_ROLE_EXISTS != "not_exists" ]]; then
    echo "Lambda role already exists, getting ARN..."
    LAMBDA_ROLE_ARN=$(echo $LAMBDA_ROLE_EXISTS | jq -r '.Role.Arn')
    echo "Found Lambda Role ARN: $LAMBDA_ROLE_ARN"
    
    # Ensure VPC access policy is attached to existing role
    echo "Ensuring VPC access policy is attached to existing role..."
    aws iam attach-role-policy \
      --role-name DBAnalyzerLambdaRole \
      --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole
      
    # Ensure SSM Parameter Store and Secrets Manager access policy is attached
    echo "Ensuring SSM and Secrets Manager access policy is attached..."
    SSM_SECRETS_POLICY='{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": [
            "ssm:GetParameter",
            "ssm:GetParameters",
            "ssm:GetParametersByPath"
          ],
          "Resource": "arn:aws:ssm:*:*:parameter/AuroraOps/*"
        },
        {
          "Effect": "Allow",
          "Action": [
            "secretsmanager:GetSecretValue",
            "secretsmanager:DescribeSecret"
          ],
          "Resource": "arn:aws:secretsmanager:*:*:secret:*"
        }
      ]
    }'
    
    aws iam put-role-policy \
      --role-name DBAnalyzerLambdaRole \
      --policy-name SSMSecretsAccessPolicy \
      --policy-document "$SSM_SECRETS_POLICY"
else
    # Create Lambda function role
    echo "Creating Lambda function role..."
    LAMBDA_TRUST_POLICY='{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": {
            "Service": "lambda.amazonaws.com"
          },
          "Action": "sts:AssumeRole"
        }
      ]
    }'

    LAMBDA_ROLE_RESPONSE=$(aws iam create-role \
      --role-name DBAnalyzerLambdaRole \
      --assume-role-policy-document "$LAMBDA_TRUST_POLICY")

    LAMBDA_ROLE_ARN=$(echo $LAMBDA_ROLE_RESPONSE | jq -r '.Role.Arn')

    # Attach basic Lambda execution policy
    aws iam attach-role-policy \
      --role-name DBAnalyzerLambdaRole \
      --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      
    # Attach VPC access execution policy
    aws iam attach-role-policy \
      --role-name DBAnalyzerLambdaRole \
      --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole
      
    # Attach SSM Parameter Store and Secrets Manager access policy
    SSM_SECRETS_POLICY='{
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": [
            "ssm:GetParameter",
            "ssm:GetParameters",
            "ssm:GetParametersByPath"
          ],
          "Resource": "arn:aws:ssm:*:*:parameter/AuroraOps/*"
        },
        {
          "Effect": "Allow",
          "Action": [
            "secretsmanager:GetSecretValue",
            "secretsmanager:DescribeSecret"
          ],
          "Resource": "arn:aws:secretsmanager:*:*:secret:*"
        }
      ]
    }'
    
    aws iam put-role-policy \
      --role-name DBAnalyzerLambdaRole \
      --policy-name SSMSecretsAccessPolicy \
      --policy-document "$SSM_SECRETS_POLICY"
fi

# Save role ARNs to config file
# Create config directory if it doesn't exist
mkdir -p ./config

# Save to the project's config directory
cat > ./config/iam_config.env << EOF
export GATEWAY_ROLE_ARN=$GATEWAY_ROLE_ARN
export LAMBDA_ROLE_ARN=$LAMBDA_ROLE_ARN
export ACCOUNT_ID=$ACCOUNT_ID
export AWS_REGION=$REGION
EOF

echo "IAM roles created successfully:"
echo "Gateway Role ARN: $GATEWAY_ROLE_ARN"
echo "Lambda Role ARN: $LAMBDA_ROLE_ARN"