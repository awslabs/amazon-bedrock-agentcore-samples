#!/bin/bash

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Parse command line arguments
WEBSOCKET_FOLDER=""

usage() {
    echo "Usage: $0 <websocket-folder>"
    echo ""
    echo "Arguments:"
    echo "  websocket-folder    Folder containing the websocket server (strands, echo, or sonic)"
    echo ""
    echo "Example:"
    echo "  export ACCOUNT_ID=123456789012"
    echo "  ./setup.sh strands"
    echo ""
    exit 1
}

# Check if folder argument is provided
if [ $# -eq 0 ]; then
    echo -e "${RED}❌ Error: websocket folder argument is required${NC}"
    echo ""
    usage
fi

WEBSOCKET_FOLDER="$1"

# Validate folder exists
if [ ! -d "./$WEBSOCKET_FOLDER/websocket" ]; then
    echo -e "${RED}❌ Error: Websocket folder not found: ./$WEBSOCKET_FOLDER/websocket${NC}"
    echo ""
    echo "Available folders:"
    for dir in strands echo sonic; do
        if [ -d "./$dir/websocket" ]; then
            echo "  - $dir"
        fi
    done
    echo ""
    exit 1
fi

echo -e "${BLUE}🚀 AgentCore BidiAgent Test Setup${NC}"
echo -e "${BLUE}📁 Using websocket folder: $WEBSOCKET_FOLDER${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}📋 Checking prerequisites...${NC}"

# Check for jq
if ! command -v jq &> /dev/null; then
    echo "❌ jq is not installed. Please install it first."
    exit 1
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install it first."
    exit 1
fi

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install it first."
    exit 1
fi

# Check for AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed. Please install it first."
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites met${NC}"
echo ""

# Set environment variables
echo -e "${YELLOW}🔧 Setting environment variables...${NC}"

# Validate required environment variables
if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ ACCOUNT_ID environment variable is required"
    echo ""
    echo "Usage: export ACCOUNT_ID=<your-aws-account-id> && ./setup.sh"
    echo ""
    exit 1
fi

export AWS_REGION=${AWS_REGION:-us-east-1}
export AWS_ACCOUNT=${AWS_ACCOUNT:-$ACCOUNT_ID}
export AGENT_NAME=${AGENT_NAME:-bidi_stream_agent}
export ECR_REPO_NAME=${ECR_REPO_NAME:-agentcore_bidi_images}
export IAM_ROLE_NAME=${IAM_ROLE_NAME:-WebSocketBidiAgentRole}

echo "   AWS_REGION: $AWS_REGION"
echo "   ACCOUNT_ID: $ACCOUNT_ID"
echo "   ECR_REPO_NAME: $ECR_REPO_NAME"
echo "   AGENT_NAME: $AGENT_NAME"
echo "   IAM_ROLE_NAME: $IAM_ROLE_NAME"
echo ""

# Step 1: Create virtual environment
echo -e "${YELLOW}📦 Step 1: Setting up Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
else
    echo -e "${GREEN}✅ Virtual environment already exists${NC}"
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo -e "${YELLOW}📥 Installing Python dependencies...${NC}"
pip install -q -r requirements.txt
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

# Step 2: Build and push Docker image
echo -e "${YELLOW}🐳 Step 2: Building and pushing Docker image...${NC}"

# Create ECR repository if it doesn't exist
echo "   Creating ECR repository (if needed)..."
aws ecr create-repository \
    --repository-name ${ECR_REPO_NAME} \
    --region ${AWS_REGION} \
    --output text 2>/dev/null || echo "   Repository already exists"

# Login to ECR
echo "   Logging in to ECR..."
aws ecr get-login-password --region ${AWS_REGION} \
    | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build and push image
echo "   Building and pushing Docker image from $WEBSOCKET_FOLDER/websocket..."
cd ./$WEBSOCKET_FOLDER/websocket
docker buildx build \
    --platform linux/arm64 \
    -t $ACCOUNT_ID.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:${AGENT_NAME} \
    --push .
cd ../..

echo -e "${GREEN}✅ Docker image built and pushed${NC}"
echo ""

# Step 3: Create IAM role
echo -e "${YELLOW}🔐 Step 3: Creating IAM role...${NC}"

# Check if role already exists
if aws iam get-role --role-name $IAM_ROLE_NAME >/dev/null 2>&1; then
    echo "   ℹ️  IAM role $IAM_ROLE_NAME already exists"
    ROLE_ARN=$(aws iam get-role --role-name $IAM_ROLE_NAME --query 'Role.Arn' --output text)
    echo "   ✅ Using existing role: $ROLE_ARN"
    echo -e "${GREEN}✅ IAM role check complete${NC}"
    echo ""
else
    echo "   Creating IAM role: $IAM_ROLE_NAME for account $ACCOUNT_ID..."

    # Check if policy files exist
    if [ ! -f "./agent_role.json" ]; then
        echo "❌ Error: agent_role.json not found"
        exit 1
    fi

    if [ ! -f "./trust_policy.json" ]; then
        echo "❌ Error: trust_policy.json not found"
        exit 1
    fi

    # Substitute ACCOUNT_ID in agent_role.json
    AGENT_ROLE_POLICY=$(cat ./agent_role.json | sed "s/\${ACCOUNT_ID}/$ACCOUNT_ID/g")

    echo "   Creating IAM role..."
    # Create the IAM role
    aws iam create-role \
        --role-name $IAM_ROLE_NAME \
        --assume-role-policy-document file://trust_policy.json \
        --no-cli-pager \
        --output json > /dev/null 2>&1

    echo "   ✅ Role created"

    # Attach the policy
    echo "   Attaching policy..."
    aws iam put-role-policy \
        --role-name $IAM_ROLE_NAME \
        --policy-name ${IAM_ROLE_NAME}Policy \
        --policy-document "$AGENT_ROLE_POLICY" \
        --no-cli-pager \
        --output json > /dev/null 2>&1

    echo "   ✅ Policy attached"

    # Validate role exists
    echo "   Validating role..."
    ROLE_ARN=$(aws iam get-role --role-name $IAM_ROLE_NAME --query 'Role.Arn' --output text)
    echo "   ✅ Role validated: $ROLE_ARN"

    echo -e "${GREEN}✅ IAM role creation complete${NC}"
    echo ""

    # Wait for IAM role to propagate
    echo "⏳ Waiting 10 seconds for IAM role to propagate..."
    sleep 10
    echo "✅ Wait complete"
    echo ""
fi

# Step 4: Create agent with SigV4
echo -e "${YELLOW}🤖 Step 4: Creating Bedrock Agent with SigV4...${NC}"

# Generate random 4-character alphanumeric ID
RANDOM_ID=$(openssl rand -hex 2)

echo "   Creating agent: ${AGENT_NAME}_sigv4_$RANDOM_ID"

# Retry logic for agent creation
MAX_RETRIES=3
RETRY_DELAY=5
AGENT_RESPONSE=""

for attempt in $(seq 1 $MAX_RETRIES); do
    echo "   Attempt $attempt of $MAX_RETRIES..."
    
    # Build and execute AWS CLI command, capture output directly
    set +e  # Temporarily disable exit on error
    AGENT_RESPONSE=$(aws bedrock-agentcore-control create-agent-runtime \
      --agent-runtime-name ${AGENT_NAME}_sigv4_$RANDOM_ID \
      --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"$ACCOUNT_ID.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:${AGENT_NAME}\"}}" \
      --network-configuration '{"networkMode":"PUBLIC"}' \
      --role-arn arn:aws:iam::$ACCOUNT_ID:role/$IAM_ROLE_NAME \
      --region ${AWS_REGION} \
      --output json 2>&1)
    EXIT_CODE=$?
    set -e  # Re-enable exit on error
    
    # Check if command succeeded
    if [ $EXIT_CODE -eq 0 ]; then
        # Verify we got a valid response with agentRuntimeArn
        AGENT_ARN=$(echo "$AGENT_RESPONSE" | jq -r '.agentRuntimeArn' 2>/dev/null)
        if [ -n "$AGENT_ARN" ] && [ "$AGENT_ARN" != "null" ]; then
            echo -e "${GREEN}   ✅ Agent created successfully${NC}"
            break
        fi
    fi
    
    # If we're here, the attempt failed
    if [ $attempt -lt $MAX_RETRIES ]; then
        echo -e "${YELLOW}   ⚠️  Attempt $attempt failed, retrying in ${RETRY_DELAY}s...${NC}"
        echo "   Error: $(echo "$AGENT_RESPONSE" | head -n 3)"
        sleep $RETRY_DELAY
    else
        echo -e "${YELLOW}   ❌ All $MAX_RETRIES attempts failed${NC}"
        echo "   Last error response:"
        echo "$AGENT_RESPONSE"
        exit 1
    fi
done

# Extract agent ARN from response
export AGENT_ARN=$(echo "$AGENT_RESPONSE" | jq -r '.agentRuntimeArn')

echo -e "${GREEN}✅ Agent created: $AGENT_ARN${NC}"
echo ""

# Extract additional info
ECR_IMAGE="$ACCOUNT_ID.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:${AGENT_NAME}"
AGENT_RUNTIME_NAME="${AGENT_NAME}_sigv4_$RANDOM_ID"
IAM_ROLE_ARN="arn:aws:iam::$ACCOUNT_ID:role/$IAM_ROLE_NAME"

# Save configuration to JSON file for cleanup in the specified folder
CONFIG_FILE="./$WEBSOCKET_FOLDER/setup_config.json"
echo "💾 Saving configuration to $CONFIG_FILE..."
cat > "$CONFIG_FILE" << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "websocket_folder": "$WEBSOCKET_FOLDER",
  "aws_region": "$AWS_REGION",
  "account_id": "$ACCOUNT_ID",
  "iam_role_name": "$IAM_ROLE_NAME",
  "ecr_repo_name": "$ECR_REPO_NAME",
  "agent_name": "$AGENT_NAME",
  "agent_runtime_name": "$AGENT_RUNTIME_NAME",
  "agent_arn": "$AGENT_ARN",
  "iam_role_arn": "$IAM_ROLE_ARN",
  "ecr_image": "$ECR_IMAGE"
}
EOF
echo "✅ Configuration saved"
echo ""

# Display summary
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}� Configueration Summary${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}AWS Configuration:${NC}"
echo "   Account ID:        $ACCOUNT_ID"
echo "   Region:            $AWS_REGION"
echo ""
echo -e "${YELLOW}Agent Runtime:${NC}"
echo "   Agent Name:        $AGENT_RUNTIME_NAME"
echo "   Agent ARN:         $AGENT_ARN"
echo "   IAM Role:          $IAM_ROLE_ARN"
echo ""
echo -e "${YELLOW}Container Image:${NC}"
echo "   ECR Repository:    $ECR_REPO_NAME"
echo "   Image Tag:         $AGENT_NAME"
echo "   Full Image URI:    $ECR_IMAGE"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}🚀 Next Steps${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}1. Start the client (recommended):${NC}"
echo "   ./start_client.sh $WEBSOCKET_FOLDER"
echo ""
echo -e "${YELLOW}2. Or manually start the client:${NC}"
echo "   export AWS_REGION=\"$AWS_REGION\""
echo "   python $WEBSOCKET_FOLDER/client/client.py --runtime-arn \"$AGENT_ARN\""
echo ""
echo -e "${YELLOW}3. When done, clean up resources:${NC}"
echo "   ./cleanup.sh $WEBSOCKET_FOLDER"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
