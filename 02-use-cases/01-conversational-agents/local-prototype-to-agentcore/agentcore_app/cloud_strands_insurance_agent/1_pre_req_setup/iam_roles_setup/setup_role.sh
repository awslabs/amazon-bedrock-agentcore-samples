#!/bin/bash

# Bedrock AgentCore Execution Role Setup Script
# This script helps set up the IAM role with correct permissions for Bedrock AgentCore

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ROLE_NAME="BedrockAgentCoreExecutionRole"
REPOSITORY_NAME="bedrock-agentcore"
AGENT_NAME="insurance-agent"

# Banner
echo -e "${BLUE}"
echo "╔════════════════════════════════════════╗"
echo "║         BEDROCK AGENTCORE SETUP        ║"
echo "║         IAM Role Configuration         ║"
echo "╚════════════════════════════════════════╝"
echo -e "${NC}"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if user is logged in to AWS
echo "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: Not authenticated with AWS. Please run 'aws configure' first.${NC}"
    exit 1
fi

# Get AWS Account ID
echo "Getting AWS account information..."
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}Error: Could not determine AWS Account ID.${NC}"
    exit 1
fi

echo -e "${GREEN}Using AWS Account ID: ${ACCOUNT_ID}${NC}"

# Get AWS Regions
echo -e "\nEnter comma-separated list of AWS regions to use (default: us-east-1,us-west-2):"
read -p "> " REGIONS_INPUT
REGIONS=${REGIONS_INPUT:-"us-east-1,us-west-2"}
IFS=',' read -ra REGIONS_ARRAY <<< "$REGIONS"

echo -e "${GREEN}Using regions: ${REGIONS}${NC}"

# Get Role Name
echo -e "\nEnter IAM Role Name (default: ${ROLE_NAME}):"
read -p "> " ROLE_NAME_INPUT
ROLE_NAME=${ROLE_NAME_INPUT:-$ROLE_NAME}

echo -e "${GREEN}Using role name: ${ROLE_NAME}${NC}"

# Get ECR Repository Name
echo -e "\nEnter ECR Repository Name (default: ${REPOSITORY_NAME}):"
read -p "> " REPOSITORY_NAME_INPUT
REPOSITORY_NAME=${REPOSITORY_NAME_INPUT:-$REPOSITORY_NAME}

echo -e "${GREEN}Using repository name: ${REPOSITORY_NAME}${NC}"

# Get Agent Name
echo -e "\nEnter Agent Name (default: ${AGENT_NAME}):"
read -p "> " AGENT_NAME_INPUT
AGENT_NAME=${AGENT_NAME_INPUT:-$AGENT_NAME}

echo -e "${GREEN}Using agent name: ${AGENT_NAME}${NC}"

# Create temporary directory
TEMP_DIR=$(mktemp -d)
echo -e "\nCreating policy files in ${TEMP_DIR}..."

# Generate trust policy
cat > "${TEMP_DIR}/trust-policy.json" << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AssumeRolePolicyProd",
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock-agentcore.amazonaws.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "${ACCOUNT_ID}"
        },
        "ArnLike": {
          "aws:SourceArn": "arn:aws:bedrock-agentcore:*:${ACCOUNT_ID}:*"
        }
      }
    }
  ]
}
EOF

# Generate the start of execution policy
cat > "${TEMP_DIR}/execution-policy.json" << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRImageAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ],
      "Resource": [
EOF

# Add ECR resources for all regions
region_count=${#REGIONS_ARRAY[@]}
for ((i=0; i<region_count; i++)); do
  region="${REGIONS_ARRAY[i]}"
  if [[ $i -eq $(($region_count-1)) ]]; then
    # Last item, no comma
    echo "        \"arn:aws:ecr:${region}:${ACCOUNT_ID}:repository/${REPOSITORY_NAME}\"" >> "${TEMP_DIR}/execution-policy.json"
  else
    # Not the last item, add comma
    echo "        \"arn:aws:ecr:${region}:${ACCOUNT_ID}:repository/${REPOSITORY_NAME}\"," >> "${TEMP_DIR}/execution-policy.json"
  fi
done

# Add ECR token access
cat >> "${TEMP_DIR}/execution-policy.json" << EOF
      ]
    },
    {
      "Sid": "ECRTokenAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogStreams",
        "logs:CreateLogGroup"
      ],
      "Resource": [
EOF

# Add logs resources for all regions
for ((i=0; i<region_count; i++)); do
  region="${REGIONS_ARRAY[i]}"
  if [[ $i -eq $(($region_count-1)) ]]; then
    # Last item, no comma
    echo "        \"arn:aws:logs:${region}:${ACCOUNT_ID}:log-group:/aws/bedrock-agentcore/runtimes/*\"" >> "${TEMP_DIR}/execution-policy.json"
  else
    # Not the last item, add comma
    echo "        \"arn:aws:logs:${region}:${ACCOUNT_ID}:log-group:/aws/bedrock-agentcore/runtimes/*\"," >> "${TEMP_DIR}/execution-policy.json"
  fi
done

cat >> "${TEMP_DIR}/execution-policy.json" << EOF
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:DescribeLogGroups"
      ],
      "Resource": [
EOF

# Add logs resources for all regions
for ((i=0; i<region_count; i++)); do
  region="${REGIONS_ARRAY[i]}"
  if [[ $i -eq $(($region_count-1)) ]]; then
    # Last item, no comma
    echo "        \"arn:aws:logs:${region}:${ACCOUNT_ID}:log-group:*\"" >> "${TEMP_DIR}/execution-policy.json"
  else
    # Not the last item, add comma
    echo "        \"arn:aws:logs:${region}:${ACCOUNT_ID}:log-group:*\"," >> "${TEMP_DIR}/execution-policy.json"
  fi
done

cat >> "${TEMP_DIR}/execution-policy.json" << EOF
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": [
EOF

# Add logs resources for all regions
for ((i=0; i<region_count; i++)); do
  region="${REGIONS_ARRAY[i]}"
  if [[ $i -eq $(($region_count-1)) ]]; then
    # Last item, no comma
    echo "        \"arn:aws:logs:${region}:${ACCOUNT_ID}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*\"" >> "${TEMP_DIR}/execution-policy.json"
  else
    # Not the last item, add comma
    echo "        \"arn:aws:logs:${region}:${ACCOUNT_ID}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*\"," >> "${TEMP_DIR}/execution-policy.json"
  fi
done

cat >> "${TEMP_DIR}/execution-policy.json" << EOF
      ]
    },
    {
      "Effect": "Allow", 
      "Action": [ 
        "xray:PutTraceSegments", 
        "xray:PutTelemetryRecords", 
        "xray:GetSamplingRules", 
        "xray:GetSamplingTargets"
      ],
      "Resource": [ "*" ] 
    },
    {
      "Effect": "Allow",
      "Resource": "*",
      "Action": "cloudwatch:PutMetricData",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": "bedrock-agentcore"
        }
      }
    },
    {
      "Sid": "GetAgentAccessToken",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:GetWorkloadAccessToken",
        "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
        "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
      ],
      "Resource": [
EOF

# Add bedrock-agentcore resources for all regions
# This is more complex as each region needs two entries
all_resources=()
for region in "${REGIONS_ARRAY[@]}"; do
  all_resources+=("arn:aws:bedrock-agentcore:${region}:${ACCOUNT_ID}:workload-identity-directory/default")
  all_resources+=("arn:aws:bedrock-agentcore:${region}:${ACCOUNT_ID}:workload-identity-directory/default/workload-identity/${AGENT_NAME}-*")
done

# Now print the resources with proper commas
resource_count=${#all_resources[@]}
for ((i=0; i<resource_count; i++)); do
  resource="${all_resources[i]}"
  if [[ $i -eq $(($resource_count-1)) ]]; then
    # Last item, no comma
    echo "        \"${resource}\"" >> "${TEMP_DIR}/execution-policy.json"
  else
    # Not the last item, add comma
    echo "        \"${resource}\"," >> "${TEMP_DIR}/execution-policy.json"
  fi
done

cat >> "${TEMP_DIR}/execution-policy.json" << EOF
      ]
    },
    {
      "Sid": "BedrockModelInvocation", 
      "Effect": "Allow", 
      "Action": [ 
        "bedrock:InvokeModel", 
        "bedrock:InvokeModelWithResponseStream"
      ], 
      "Resource": [
        "arn:aws:bedrock:*::foundation-model/*",
EOF

# Add bedrock resources for all regions
for ((i=0; i<region_count; i++)); do
  region="${REGIONS_ARRAY[i]}"
  if [[ $i -eq $(($region_count-1)) ]]; then
    # Last item, no comma
    echo "        \"arn:aws:bedrock:${region}:${ACCOUNT_ID}:*\"" >> "${TEMP_DIR}/execution-policy.json"
  else
    # Not the last item, add comma
    echo "        \"arn:aws:bedrock:${region}:${ACCOUNT_ID}:*\"," >> "${TEMP_DIR}/execution-policy.json"
  fi
done

cat >> "${TEMP_DIR}/execution-policy.json" << EOF
      ]
    }
  ]
}
EOF

# Check if the role exists
echo -e "\nChecking if role ${ROLE_NAME} already exists..."
if aws iam get-role --role-name "${ROLE_NAME}" &> /dev/null; then
    echo -e "${YELLOW}Role ${ROLE_NAME} already exists.${NC}"
    read -p "Do you want to update its policies? (Y/n): " UPDATE_ROLE
    UPDATE_ROLE=${UPDATE_ROLE:-Y}
    if [[ $UPDATE_ROLE == "n" || $UPDATE_ROLE == "N" || $UPDATE_ROLE == "no" || $UPDATE_ROLE == "No" || $UPDATE_ROLE == "NO" ]]; then
        echo -e "${YELLOW}No changes made to role ${ROLE_NAME}${NC}"
        rm -rf "${TEMP_DIR}"
        exit 0
    fi
else
    echo -e "Creating role ${ROLE_NAME}..."
    aws iam create-role --role-name "${ROLE_NAME}" --assume-role-policy-document file://"${TEMP_DIR}/trust-policy.json"
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to create role.${NC}"
        rm -rf "${TEMP_DIR}"
        exit 1
    fi
    echo -e "${GREEN}Role ${ROLE_NAME} created successfully.${NC}"
fi

# Attach policy to role
echo -e "\nAttaching execution policy to role ${ROLE_NAME}..."
aws iam put-role-policy --role-name "${ROLE_NAME}" --policy-name "BedrockAgentCoreExecutionPolicy" --policy-document file://"${TEMP_DIR}/execution-policy.json"
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to attach policy to role.${NC}"
    rm -rf "${TEMP_DIR}"
    exit 1
fi

# Get role ARN
ROLE_ARN=$(aws iam get-role --role-name "${ROLE_NAME}" --query "Role.Arn" --output text)

# Clean up
rm -rf "${TEMP_DIR}"

echo -e "\n${GREEN}✅ Successfully set up IAM role for Bedrock AgentCore!${NC}"
echo -e "${GREEN}Role ARN: ${ROLE_ARN}${NC}"
echo -e "\nYou can use this role ARN in your Bedrock AgentCore configuration."