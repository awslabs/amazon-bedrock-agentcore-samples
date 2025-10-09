#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================="
echo "AgentCore Insurance App - Full Deployment"
echo -e "==========================================${NC}\n"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}✗ AWS CLI not found. Please install it first.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ AWS CLI found${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found. Please install it first.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found${NC}"

# Check jq
if ! command -v jq &> /dev/null; then
    echo -e "${RED}✗ jq not found. Please install it first.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ jq found${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}⚠ Docker not found. You'll need it for local testing.${NC}"
else
    echo -e "${GREEN}✓ Docker found${NC}"
fi

echo ""

# Step 1: Deploy Insurance API
echo -e "${BLUE}=========================================="
echo "Step 1: Deploying Insurance API"
echo -e "==========================================${NC}\n"

cd cloud_insurance_api/deployment
chmod +x ./deploy.sh
./deploy.sh

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Insurance API deployment failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Insurance API deployed successfully${NC}\n"

# Step 2: Setup MCP Gateway
echo -e "${BLUE}=========================================="
echo "Step 2: Setting up MCP Gateway"
echo -e "==========================================${NC}\n"

cd ../../cloud_mcp_server

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file from example...${NC}"
    cp .env_example .env
    
    # Get API Gateway URL from CloudFormation
    STACK_NAME="insurance-api-dev"
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    if [ ! -z "$API_URL" ]; then
        sed -i.bak "s|API_GATEWAY_URL=.*|API_GATEWAY_URL=$API_URL|" .env
        echo -e "${GREEN}✓ Auto-configured API Gateway URL${NC}"
    fi
fi

# Run automated setup
chmod +x ./setup.sh
./setup.sh

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ MCP Gateway setup failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ MCP Gateway setup successfully${NC}\n"

# Step 3: Setup AgentCore Identity
echo -e "${BLUE}=========================================="
echo "Step 3: Setting up AgentCore Identity"
echo -e "==========================================${NC}\n"

cd ../cloud_strands_insurance_agent

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file from example...${NC}"
    cp .env_example .env
    
    # Set demo API key
    echo 'API_KEY="demo-insurance-api-key-12345"' >> .env
fi

# Always update MCP settings from gateway_info.json
if [ -f ../cloud_mcp_server/gateway_info.json ]; then
    echo -e "${YELLOW}Updating MCP settings from gateway_info.json...${NC}"
    MCP_URL=$(jq -r '.gateway.mcp_url' ../cloud_mcp_server/gateway_info.json)
    MCP_TOKEN=$(jq -r '.auth.access_token' ../cloud_mcp_server/gateway_info.json)
    
    # Update .env file
    sed -i.bak "s|MCP_SERVER_URL=.*|MCP_SERVER_URL=\"$MCP_URL\"|" .env
    sed -i.bak "s|MCP_ACCESS_TOKEN=.*|MCP_ACCESS_TOKEN=\"$MCP_TOKEN\"|" .env
    
    echo -e "${GREEN}✓ Updated MCP_SERVER_URL: $MCP_URL${NC}"
    echo -e "${GREEN}✓ Updated MCP_ACCESS_TOKEN (expires in 1 hour)${NC}"
fi

# Run identity setup
chmod +x ./scripts/setup_identity.sh
./scripts/setup_identity.sh

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Identity setup failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Identity setup completed${NC}\n"

# Step 4: Deploy Agent
echo -e "${BLUE}=========================================="
echo "Step 4: Deploying Strands Agent"
echo -e "==========================================${NC}\n"

# Setup IAM role
echo -e "${YELLOW}Setting up IAM role...${NC}"
cd 1_pre_req_setup/iam_roles_setup
chmod +x ./setup_role.sh
./setup_role.sh

# Setup Cognito
echo -e "${YELLOW}Setting up Cognito authentication...${NC}"
cd ../cognito_auth
chmod +x ./setup_cognito.sh
./setup_cognito.sh

cd ../..

# Get role ARN
ROLE_ARN=$(aws iam get-role --role-name BedrockAgentCoreExecutionRole --query 'Role.Arn' --output text 2>/dev/null)

if [ -z "$ROLE_ARN" ]; then
    echo -e "${RED}✗ Could not get IAM role ARN${NC}"
    exit 1
fi

# Configure agent
echo -e "${YELLOW}Configuring agent...${NC}"
agentcore configure -e "agentcore_strands_insurance_agent.py" \
  --name insurance_agent_strands \
  -er $ROLE_ARN

# Load environment
source .env

# Update .bedrock_agentcore.yaml with latest MCP settings
if [ -f .bedrock_agentcore.yaml ]; then
    echo -e "${YELLOW}Updating .bedrock_agentcore.yaml with latest MCP settings...${NC}"
    
    # Check if environment section exists
    if grep -q "environment:" .bedrock_agentcore.yaml; then
        # Update existing environment section
        sed -i.bak "s|MCP_SERVER_URL:.*|MCP_SERVER_URL: \"$MCP_SERVER_URL\"|" .bedrock_agentcore.yaml
        sed -i.bak "s|MCP_ACCESS_TOKEN:.*|MCP_ACCESS_TOKEN: \"$MCP_ACCESS_TOKEN\"|" .bedrock_agentcore.yaml
        echo -e "${GREEN}✓ Updated environment section in .bedrock_agentcore.yaml${NC}"
    else
        echo -e "${YELLOW}⚠ No environment section found in .bedrock_agentcore.yaml${NC}"
        echo -e "${YELLOW}  Using --env flags for deployment${NC}"
    fi
fi

# Deploy agent
echo -e "${YELLOW}Deploying agent to AWS...${NC}"
agentcore launch \
  -env MCP_SERVER_URL="$MCP_SERVER_URL" \
  -env MCP_ACCESS_TOKEN="$MCP_ACCESS_TOKEN" \
  -env MODEL_NAME="$MODEL_NAME" \
  -env AWS_REGION="$AWS_REGION" \
  -env WORKLOAD_IDENTITY_ARN="$WORKLOAD_IDENTITY_ARN" \
  -env WORKLOAD_IDENTITY_ID="$WORKLOAD_IDENTITY_ID" \
  -env API_KEY_PROVIDER_NAME="$API_KEY_PROVIDER_NAME"

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Agent deployment failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Agent deployed successfully${NC}\n"

# Step 5: Test deployment
echo -e "${BLUE}=========================================="
echo "Step 5: Testing Deployment"
echo -e "==========================================${NC}\n"

# Refresh Cognito token
cd 1_pre_req_setup/cognito_auth
./refresh_token.sh
export BEARER_TOKEN=$(jq -r '.bearer_token' cognito_config.json)
cd ../..

# Test invocation
echo -e "${YELLOW}Testing agent invocation...${NC}"
agentcore invoke --bearer-token $BEARER_TOKEN \
  '{"user_input": "Can you help me get a quote for auto insurance?", "actor_id": "test-user"}'

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✓ Agent invocation successful!${NC}"
else
    echo -e "\n${YELLOW}⚠ Agent invocation had issues. Check logs for details.${NC}"
fi

# Final summary
echo -e "\n${BLUE}=========================================="
echo "Deployment Complete!"
echo -e "==========================================${NC}\n"

echo -e "${GREEN}✓ Insurance API deployed${NC}"
echo -e "${GREEN}✓ MCP Gateway configured${NC}"
echo -e "${GREEN}✓ AgentCore Identity setup${NC}"
echo -e "${GREEN}✓ Strands Agent deployed${NC}"
echo -e "${GREEN}✓ Deployment tested${NC}\n"

echo -e "${YELLOW}Next steps:${NC}"
echo "1. View logs: agentcore logs --tail 50"
echo "2. Invoke agent: agentcore invoke --bearer-token \$BEARER_TOKEN '{\"user_input\": \"your question\"}'"
echo "3. Monitor in AWS Console: CloudWatch > GenAI Observability"
echo ""
echo -e "${BLUE}For more information, see README.md${NC}"
