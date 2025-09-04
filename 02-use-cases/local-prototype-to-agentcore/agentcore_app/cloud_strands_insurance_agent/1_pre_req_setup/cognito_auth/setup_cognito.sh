#!/bin/bash

# Bedrock AgentCore Cognito Auth Setup Script
# This script helps set up the Cognito User Pool and App Client for Bedrock AgentCore authentication

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Banner
echo -e "${BLUE}"
echo "╔════════════════════════════════════════╗"
echo "║      BEDROCK AGENTCORE COGNITO AUTH    ║"
echo "║         Authentication Setup           ║"
echo "╚════════════════════════════════════════╝"
echo -e "${NC}"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${RED}Error: jq is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if user is logged in to AWS
echo "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: Not authenticated with AWS. Please run 'aws configure' first.${NC}"
    exit 1
fi

# Get AWS account information
echo "Getting AWS account information..."
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}Error: Could not determine AWS Account ID.${NC}"
    exit 1
fi

# Default values
DEFAULT_REGION="us-east-1"
DEFAULT_POOL_NAME="BedrockAgentCoreUserPool"
DEFAULT_CLIENT_NAME="BedrockAgentCoreClient"
DEFAULT_USERNAME="agentcore-user"
DEFAULT_PASSWORD="MyPassword123!"

# Get region
echo -e "\nEnter AWS region for Cognito resources (default: ${DEFAULT_REGION}):"
read -p "> " REGION_INPUT
REGION=${REGION_INPUT:-$DEFAULT_REGION}

# Get User Pool name
echo -e "\nEnter Cognito User Pool name (default: ${DEFAULT_POOL_NAME}):"
read -p "> " POOL_NAME_INPUT
POOL_NAME=${POOL_NAME_INPUT:-$DEFAULT_POOL_NAME}

# Get App Client name
echo -e "\nEnter Cognito App Client name (default: ${DEFAULT_CLIENT_NAME}):"
read -p "> " CLIENT_NAME_INPUT
CLIENT_NAME=${CLIENT_NAME_INPUT:-$DEFAULT_CLIENT_NAME}

# Get username
echo -e "\nEnter username for test user (default: ${DEFAULT_USERNAME}):"
read -p "> " USERNAME_INPUT
USERNAME=${USERNAME_INPUT:-$DEFAULT_USERNAME}

# Get password
echo -e "\nEnter password for test user (default: ${DEFAULT_PASSWORD}):"
read -p "> " PASSWORD_INPUT
PASSWORD=${PASSWORD_INPUT:-$DEFAULT_PASSWORD}

# Confirm settings
echo -e "\n${YELLOW}Review Settings:${NC}"
echo "  - AWS Account ID: ${ACCOUNT_ID}"
echo "  - AWS Region: ${REGION}"
echo "  - User Pool Name: ${POOL_NAME}"
echo "  - App Client Name: ${CLIENT_NAME}"
echo "  - Username: ${USERNAME}"
echo "  - Password: ${PASSWORD}"

echo -e "\nProceed with these settings? (Y/n)"
read -p "> " PROCEED
PROCEED=${PROCEED:-Y}
if [[ $PROCEED == "n" || $PROCEED == "N" || $PROCEED == "no" || $PROCEED == "No" || $PROCEED == "NO" ]]; then
    echo -e "${YELLOW}Setup cancelled.${NC}"
    exit 0
fi

echo -e "\n${YELLOW}Creating Cognito User Pool...${NC}"
# Create User Pool and capture Pool ID
POOL_ID=$(aws cognito-idp create-user-pool \
  --pool-name "${POOL_NAME}" \
  --policies '{"PasswordPolicy":{"MinimumLength":8}}' \
  --region ${REGION} | jq -r '.UserPool.Id')

if [ -z "$POOL_ID" ] || [ "$POOL_ID" == "null" ]; then
    echo -e "${RED}Error: Failed to create User Pool.${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Creating Cognito App Client...${NC}"
# Create App Client and capture Client ID
CLIENT_ID=$(aws cognito-idp create-user-pool-client \
  --user-pool-id ${POOL_ID} \
  --client-name "${CLIENT_NAME}" \
  --no-generate-secret \
  --explicit-auth-flows "ALLOW_USER_PASSWORD_AUTH" "ALLOW_REFRESH_TOKEN_AUTH" \
  --region ${REGION} | jq -r '.UserPoolClient.ClientId')

if [ -z "$CLIENT_ID" ] || [ "$CLIENT_ID" == "null" ]; then
    echo -e "${RED}Error: Failed to create App Client.${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Creating test user...${NC}"
# Create User
aws cognito-idp admin-create-user \
  --user-pool-id ${POOL_ID} \
  --username "${USERNAME}" \
  --temporary-password "Temp123!" \
  --region ${REGION} \
  --message-action SUPPRESS > /dev/null

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to create test user.${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Setting permanent password for test user...${NC}"
# Set Permanent Password
aws cognito-idp admin-set-user-password \
  --user-pool-id ${POOL_ID} \
  --username "${USERNAME}" \
  --password "${PASSWORD}" \
  --region ${REGION} \
  --permanent > /dev/null

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to set user password.${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Authenticating user and getting access token...${NC}"
# Authenticate User and capture Access Token
BEARER_TOKEN=$(aws cognito-idp initiate-auth \
  --client-id "${CLIENT_ID}" \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME="${USERNAME}",PASSWORD="${PASSWORD}" \
  --region ${REGION} | jq -r '.AuthenticationResult.AccessToken')

if [ -z "$BEARER_TOKEN" ] || [ "$BEARER_TOKEN" == "null" ]; then
    echo -e "${RED}Error: Failed to authenticate user and get token.${NC}"
    exit 1
fi

# Discovery URL
DISCOVERY_URL="https://cognito-idp.${REGION}.amazonaws.com/${POOL_ID}/.well-known/openid-configuration"

# Save config to JSON file
echo -e "\n${YELLOW}Saving configuration to cognito_config.json...${NC}"
cat > cognito_config.json << EOF
{
  "pool_id": "${POOL_ID}",
  "client_id": "${CLIENT_ID}",
  "discovery_url": "${DISCOVERY_URL}",
  "bearer_token": "${BEARER_TOKEN}",
  "region": "${REGION}",
  "username": "${USERNAME}",
  "password": "${PASSWORD}"
}
EOF

# Save summary to markdown file
cat > cognito_result.md << EOF
# Cognito Authentication Setup

## Configuration
- **User Pool ID**: ${POOL_ID}
- **Client ID**: ${CLIENT_ID}
- **Region**: ${REGION}
- **Discovery URL**: ${DISCOVERY_URL}

## Test User
- **Username**: ${USERNAME}
- **Password**: ${PASSWORD}

## Authentication Token
\`\`\`
${BEARER_TOKEN}
\`\`\`

## Notes
- The token expires after 1 hour by default
- Use the refresh_token.sh script to get a new token when needed
- Configuration is saved in cognito_config.json for easy access
EOF

echo -e "\n${GREEN}✅ Successfully set up Cognito authentication!${NC}"
echo -e "\n${GREEN}User Pool ID:${NC} ${POOL_ID}"
echo -e "${GREEN}Discovery URL:${NC} ${DISCOVERY_URL}"
echo -e "${GREEN}Client ID:${NC} ${CLIENT_ID}"
echo -e "${GREEN}Bearer Token:${NC} ${BEARER_TOKEN}"
echo -e "\nFull configuration saved to cognito_config.json"
echo -e "Summary saved to cognito_result.md"
echo -e "\nTo refresh the token when it expires, run: ./refresh_token.sh"