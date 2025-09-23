#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ROLE_NAME="claude-code-agentcore-role"
POLICY_NAME="claude-code-agentcore-policy"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo -e "${GREEN}🚀 Setting up IAM role for Claude Code AgentCore${NC}"
echo "============================================================"

# Check if AWS CLI is configured
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${RED}❌ Error: AWS CLI not configured. Please run 'aws configure' first.${NC}"
    exit 1
fi

echo -e "${YELLOW}AWS Account ID: $AWS_ACCOUNT_ID${NC}"

# Create IAM role with trust policy
echo -e "\n${GREEN}📝 Creating IAM role: $ROLE_NAME${NC}"
ROLE_ARN=$(aws iam create-role \
    --role-name $ROLE_NAME \
    --assume-role-policy-document file://trust-policy.json \
    --description "Execution role for Claude Code on AgentCore" \
    --query 'Role.Arn' \
    --output text 2>/dev/null)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Role created successfully${NC}"
else
    # Check if role already exists
    ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo -e "${YELLOW}⚠️  Role already exists, updating...${NC}"
        aws iam update-assume-role-policy \
            --role-name $ROLE_NAME \
            --policy-document file://trust-policy.json
    else
        echo -e "${RED}❌ Error creating role${NC}"
        exit 1
    fi
fi

# Create and attach the permissions policy
echo -e "\n${GREEN}📝 Creating IAM policy: $POLICY_NAME${NC}"

# Replace account ID in permissions policy if needed
TEMP_POLICY_FILE="/tmp/permissions-policy-temp.json"
cp permissions-policy.json $TEMP_POLICY_FILE

POLICY_ARN=$(aws iam create-policy \
    --policy-name $POLICY_NAME \
    --policy-document file://$TEMP_POLICY_FILE \
    --description "Permissions for Claude Code to deploy websites to S3 and CloudFront" \
    --query 'Policy.Arn' \
    --output text 2>/dev/null)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Policy created successfully${NC}"
else
    # Policy might already exist
    POLICY_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:policy/$POLICY_NAME"
    echo -e "${YELLOW}⚠️  Policy might already exist, using: $POLICY_ARN${NC}"
    
    # Update the existing policy with a new version
    echo -e "${YELLOW}📝 Creating new policy version...${NC}"
    aws iam create-policy-version \
        --policy-arn $POLICY_ARN \
        --policy-document file://$TEMP_POLICY_FILE \
        --set-as-default 2>/dev/null
fi

# Attach the policy to the role
echo -e "\n${GREEN}🔗 Attaching policy to role${NC}"
aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn $POLICY_ARN

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Policy attached successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Policy might already be attached${NC}"
fi

# Clean up temp file
rm -f $TEMP_POLICY_FILE

# Output the role ARN
echo -e "\n${GREEN}============================================================${NC}"
echo -e "${GREEN}✅ IAM SETUP COMPLETE!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo -e "\n${YELLOW}IAM Role ARN:${NC}"
echo -e "${GREEN}$ROLE_ARN${NC}"
echo -e "\n${YELLOW}Use this ARN when configuring AgentCore:${NC}"
echo -e "${GREEN}agentcore configure -e claude_code_agent.py \\
  --execution-role $ROLE_ARN \\
  --container-runtime docker${NC}"
echo -e "\n${YELLOW}Note:${NC} The role has permissions to:"
echo "  • Invoke Bedrock models"
echo "  • Create and manage S3 buckets (with prefix 'claude-code-*')"
echo "  • Create and manage CloudFront distributions"
echo "  • Write CloudWatch logs"
