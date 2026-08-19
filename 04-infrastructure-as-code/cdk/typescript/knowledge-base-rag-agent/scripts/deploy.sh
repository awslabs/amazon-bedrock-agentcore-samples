#!/bin/bash

# Simple deployment script for Bedrock AgentCore Template
# This script demonstrates the basic deployment process

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying Bedrock AgentCore Template${NC}"
echo ""

# Run prerequisite checks
if [ -f "./scripts/check-prerequisites.sh" ]; then
    ./scripts/check-prerequisites.sh
    if [ $? -ne 0 ]; then
        echo ""
        echo -e "${RED}❌ Prerequisite checks failed. Please address the issues above.${NC}"
        exit 1
    fi
    echo ""
else
    echo -e "${YELLOW}⚠ Prerequisite checker not found, skipping checks${NC}"
    echo ""
fi

# Additional deployment-specific checks
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}⚠ jq is not installed - password parsing may fail${NC}"
    echo -e "${YELLOW}  Install jq for better password retrieval: brew install jq (macOS) or apt-get install jq (Ubuntu)${NC}"
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"

# Install dependencies
echo -e "${YELLOW}📦 Installing dependencies...${NC}"
npm install

# Build web console
echo -e "${YELLOW}🏗️  Building web console...${NC}"
npm run build --workspace=web-console

# Bootstrap CDK (if needed)
echo -e "${YELLOW}☁️  Bootstrapping CDK...${NC}"
cd infrastructure

# Acknowledge CDK notices to prevent them from disrupting output
npx cdk acknowledge 34892 2>/dev/null || true

npx cdk bootstrap

# Deploy the stacks
echo -e "${YELLOW}🚀 Deploying infrastructure...${NC}"

# Deploy stacks in order to ensure proper dependencies
echo -e "${YELLOW}📦 Deploying shared resources...${NC}"
npx cdk deploy AgentCoreSharedResourcesStack --require-approval never

echo -e "${YELLOW}🌐 Deploying foundation layer...${NC}"
npx cdk deploy AgentCoreNetworkStack AgentCoreStorageStack AgentCoreCognitoStack --require-approval never

echo -e "${YELLOW}🗄️  Deploying database layer...${NC}"
npx cdk deploy AgentCoreDatabaseStack --require-approval never

echo -e "${YELLOW}🔍 Deploying OpenSearch...${NC}"
npx cdk deploy AgentCoreOpenSearchStack --require-approval never

echo -e "${YELLOW}🧠 Deploying AgentCore Memory...${NC}"
npx cdk deploy AgentCoreMemoryStack --require-approval never

echo -e "${YELLOW}🤖 Deploying AgentCore Runtime...${NC}"
npx cdk deploy AgentCoreRuntimeStack --require-approval never

echo -e "${YELLOW}⚡ Deploying API layer...${NC}"
npx cdk deploy AgentCoreApiStack --require-approval never

echo -e "${YELLOW}📊 Deploying monitoring and web console...${NC}"
npx cdk deploy AgentCoreMonitoringStack AgentCoreWebConsoleStack --require-approval never

echo -e "${GREEN}✅ Deployment completed successfully!${NC}"

# Clear any remaining CDK notices from output
echo ""
echo "=================================================================="

# Get deployment outputs from CloudFormation (stay in infrastructure directory)
echo ""
echo -e "${YELLOW}🔑 Getting deployment information...${NC}"
echo ""

# Function to get the AWS region dynamically
get_aws_region() {
    # Try to get region from environment variables first (AWS_REGION takes precedence)
    if [ -n "$AWS_REGION" ]; then
        echo "$AWS_REGION"
        return
    fi
    
    if [ -n "$AWS_DEFAULT_REGION" ]; then
        echo "$AWS_DEFAULT_REGION"
        return
    fi
    
    # Try to get region from AWS CLI configuration
    local cli_region=$(aws configure get region 2>/dev/null)
    if [ -n "$cli_region" ]; then
        echo "$cli_region"
        return
    fi
    
    # Try to get region from CDK context (if we're in infrastructure directory)
    if [ -f "cdk.json" ]; then
        local cdk_region=$(node -e "
            try {
                const context = require('./cdk.context.json');
                const keys = Object.keys(context);
                const regionKey = keys.find(key => key.includes('availability-zones'));
                if (regionKey) {
                    const region = regionKey.split(':')[3];
                    console.log(region);
                }
            } catch (e) {
                // Ignore errors
            }
        " 2>/dev/null)
        if [ -n "$cdk_region" ]; then
            echo "$cdk_region"
            return
        fi
    fi
    
    # Default fallback
    echo "us-east-1"
}

# Get the AWS region
AWS_DEPLOY_REGION=$(get_aws_region)
echo "Using AWS region: $AWS_DEPLOY_REGION" >&2

# Function to safely get CloudFormation output
get_cf_output() {
    local stack_name=$1
    local output_key=$2
    local default_value=$3
    
    local result=$(aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$AWS_DEPLOY_REGION" \
        --query "Stacks[0].Outputs[?OutputKey==\`$output_key\`].OutputValue" \
        --output text 2>/dev/null)
    
    if [ -n "$result" ] && [ "$result" != "None" ] && [ "$result" != "" ]; then
        echo "$result"
    else
        echo "$default_value"
    fi
}

echo "Retrieving deployment outputs..." >&2

# Get outputs using AWS CLI since cdk doesn't have a direct output command
INITIAL_EMAIL=$(get_cf_output "AgentCoreCognitoStack" "InitialUserEmail" "admin@example.com")

# Get password from Secrets Manager instead of CloudFormation output
INITIAL_PASSWORD_SECRET_ARN=$(get_cf_output "AgentCoreCognitoStack" "InitialUserPasswordSecretArn" "")
if [ -n "$INITIAL_PASSWORD_SECRET_ARN" ] && [ "$INITIAL_PASSWORD_SECRET_ARN" != "None" ]; then
    # Get the secret value and extract the password field
    SECRET_JSON=$(aws secretsmanager get-secret-value \
        --secret-id "$INITIAL_PASSWORD_SECRET_ARN" \
        --region "$AWS_DEPLOY_REGION" \
        --query 'SecretString' \
        --output text 2>/dev/null)
    
    if [ $? -eq 0 ] && [ -n "$SECRET_JSON" ]; then
        # Parse the JSON to extract the password field
        INITIAL_PASSWORD=$(echo "$SECRET_JSON" | jq -r '.password' 2>/dev/null)
        
        # If jq parsing fails or password is null, try alternative parsing
        if [ $? -ne 0 ] || [ "$INITIAL_PASSWORD" = "null" ] || [ -z "$INITIAL_PASSWORD" ]; then
            # Fallback: try to extract password using grep/sed if jq fails
            INITIAL_PASSWORD=$(echo "$SECRET_JSON" | grep -o '"password":"[^"]*"' | sed 's/"password":"\([^"]*\)"/\1/' 2>/dev/null)
        fi
        
        # Final fallback if all parsing fails
        if [ -z "$INITIAL_PASSWORD" ] || [ "$INITIAL_PASSWORD" = "null" ]; then
            INITIAL_PASSWORD="Check Secrets Manager: $INITIAL_PASSWORD_SECRET_ARN"
        fi
    else
        INITIAL_PASSWORD="Error retrieving from Secrets Manager"
    fi
else
    INITIAL_PASSWORD="Secrets Manager ARN not found"
fi

# Get web console URL and CloudFront distribution ID
WEB_URL=$(get_cf_output "AgentCoreWebConsoleStack" "WebsiteUrl" "Check CloudFormation outputs")
DISTRIBUTION_ID=$(get_cf_output "AgentCoreWebConsoleStack" "DistributionId" "Check CloudFormation outputs")

cd ..

echo ""
echo "=================================================================="
echo ""
echo -e "${GREEN}🎉 Your Bedrock AgentCore is ready to use!${NC}"
echo ""

echo -e "${YELLOW}🌐 Web Interface:${NC}"
echo -e "  URL: ${GREEN}${WEB_URL}${NC}"
echo ""

echo -e "${YELLOW}🔑 Login Credentials:${NC}"
echo -e "  Email:    ${GREEN}${INITIAL_EMAIL}${NC}"
echo -e "  Password: ${GREEN}${INITIAL_PASSWORD}${NC}"

# If password retrieval failed, provide manual instructions
if [[ "$INITIAL_PASSWORD" == *"Check Secrets Manager"* ]] || [[ "$INITIAL_PASSWORD" == *"Error"* ]] || [[ "$INITIAL_PASSWORD" == *"not found"* ]]; then
    echo ""
    echo -e "${YELLOW}💡 To manually retrieve the password:${NC}"
    echo -e "   ${GREEN}aws secretsmanager get-secret-value --secret-id AgentCoreTemplate/InitialUserPassword --region ${AWS_DEPLOY_REGION} --query 'SecretString' --output text | jq -r '.password'${NC}"
fi

echo ""

echo -e "${YELLOW}📝 Next steps:${NC}"
echo -e "1. Open the web interface: ${GREEN}${WEB_URL}${NC}"
echo -e "2. Log in with the credentials above"
echo -e "3. Upload documents to the knowledge base:"
echo -e "   ${GREEN}./scripts/upload-documents.sh --examples --wait${NC}"
echo -e "   Or upload your own: ${GREEN}./scripts/upload-documents.sh your-documents/${NC}"
echo -e "4. Test the agent by asking questions about your documents"
echo ""
echo -e "${YELLOW}💡 Optional - Clear CloudFront cache for immediate updates:${NC}"
echo -e "   ${GREEN}aws cloudfront create-invalidation --distribution-id ${DISTRIBUTION_ID} --region ${AWS_DEPLOY_REGION} --paths \"/*\"${NC}"