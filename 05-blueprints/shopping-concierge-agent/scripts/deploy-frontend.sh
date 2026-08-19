#!/bin/bash
set -e

# Frontend deployment script for Vite app to Amplify Hosting
# Usage: ./scripts/deploy-frontend.sh [--mock|--no-mock]
#   --mock    : Use Visa mock mode (no real API calls)
#   --no-mock : Use real Visa API via Lambda proxy

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}🚀 Deploying Frontend to Amplify${NC}\n"

# Parse flags
MOCK_FLAG=""
for arg in "$@"; do
    case $arg in
        --mock) MOCK_FLAG="--mock" ;;
        --no-mock) MOCK_FLAG="--no-mock" ;;
    esac
done

# Get deployment ID from config
DEPLOYMENT_ID=$(node -p "require('./deployment-config.json').deploymentId")
STACK_NAME="FrontendStack-${DEPLOYMENT_ID}"

# Set default region if not set
export AWS_REGION=${AWS_REGION:-us-east-1}

# Get configuration from CDK stack
echo -e "${BLUE}Fetching Amplify configuration...${NC}"
APP_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='AmplifyAppId'].OutputValue" \
    --output text 2>/dev/null)

STAGING_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='StagingBucketName'].OutputValue" \
    --output text 2>/dev/null)

if [ -z "$APP_ID" ] || [ "$APP_ID" = "None" ]; then
    echo -e "${RED}❌ Error: Could not find Amplify App ID${NC}"
    echo -e "${YELLOW}💡 Deploy the frontend stack first:${NC}"
    echo -e "   cd infrastructure/frontend-stack && npm install && cdk deploy"
    exit 1
fi

echo -e "${GREEN}✓${NC} App ID: $APP_ID"
echo -e "${GREEN}✓${NC} Staging Bucket: $STAGING_BUCKET"
echo ""

# Update environment configuration
echo -e "${BLUE}Updating environment configuration...${NC}"
./scripts/setup-web-ui-env.sh --force $MOCK_FLAG
echo ""

# Build the frontend
echo -e "${BLUE}Building frontend...${NC}"
cd web-ui
npm run build

if [ ! -d "dist" ]; then
    echo -e "${RED}❌ Error: Build directory 'dist' not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Build completed"
echo ""

# Create deployment package
echo -e "${BLUE}Creating deployment package...${NC}"
cd dist
S3_KEY="amplify-deploy-$(date +%s).zip"
zip -r ../amplify-deploy.zip . -q
cd ..

ZIP_SIZE=$(ls -lah amplify-deploy.zip | awk '{print $5}')
echo -e "${GREEN}✓${NC} Package created (${ZIP_SIZE})"
echo ""

# Upload to S3
echo -e "${BLUE}Uploading to S3...${NC}"
aws s3 cp amplify-deploy.zip "s3://$STAGING_BUCKET/$S3_KEY" --no-progress

echo -e "${GREEN}✓${NC} Upload completed"
echo ""

# Start Amplify deployment
echo -e "${BLUE}Starting Amplify deployment...${NC}"
DEPLOYMENT_OUTPUT=$(aws amplify start-deployment \
    --app-id "$APP_ID" \
    --branch-name main \
    --source-url "s3://$STAGING_BUCKET/$S3_KEY" \
    --output json 2>&1)

if [ $? -eq 0 ]; then
    JOB_ID=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.jobSummary.jobId')
    echo -e "${GREEN}✓${NC} Deployment initiated (Job ID: $JOB_ID)"
    echo ""
    
    # Get app URL
    APP_URL=$(aws amplify get-app --app-id "$APP_ID" --query 'app.defaultDomain' --output text)
    
    echo -e "${BLUE}Monitoring deployment...${NC}"
    while true; do
        STATUS=$(aws amplify get-job \
            --app-id "$APP_ID" \
            --branch-name main \
            --job-id "$JOB_ID" \
            --output json | jq -r '.job.summary.status')
        
        echo "  Status: $STATUS"
        
        case $STATUS in
            "SUCCEED")
                echo ""
                echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
                echo ""
                echo -e "${BLUE}App URL:${NC} https://main.$APP_URL"
                echo -e "${BLUE}Console:${NC} https://console.aws.amazon.com/amplify/apps/$APP_ID"
                break
                ;;
            "FAILED")
                echo -e "${RED}❌ Deployment failed${NC}"
                exit 1
                ;;
            "CANCELLED")
                echo -e "${RED}❌ Deployment was cancelled${NC}"
                exit 1
                ;;
            *)
                sleep 10
                ;;
        esac
    done
else
    echo -e "${RED}❌ Amplify deployment failed${NC}"
    echo "$DEPLOYMENT_OUTPUT"
    exit 1
fi

# Return to project root
cd ..

# Cleanup
rm -f web-ui/amplify-deploy.zip
