#!/bin/bash

# Script to upload documents to the AgentCore Knowledge Base
# This automates step 3 from the deployment output

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}📚 AgentCore Knowledge Base - Document Upload${NC}\n"

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] [DIRECTORY]"
    echo ""
    echo "Upload documents to the AgentCore Knowledge Base and trigger sync."
    echo ""
    echo "Options:"
    echo "  -e, --examples        Upload example documents from docs/knowledge-base-examples/"
    echo "  -s, --sync-only       Only trigger sync, don't upload new documents"
    echo "  -w, --wait            Wait for sync to complete"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --examples                    # Upload example documents"
    echo "  $0 my-documents/                 # Upload documents from custom directory"
    echo "  $0 --examples --wait             # Upload examples and wait for sync"
    echo "  $0 --sync-only                   # Just trigger sync without uploading"
    echo ""
}

# Parse command line arguments
UPLOAD_EXAMPLES=false
SYNC_ONLY=false
WAIT_FOR_SYNC=false
CUSTOM_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--examples)
            UPLOAD_EXAMPLES=true
            shift
            ;;
        -s|--sync-only)
            SYNC_ONLY=true
            shift
            ;;
        -w|--wait)
            WAIT_FOR_SYNC=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            CUSTOM_DIR="$1"
            shift
            ;;
    esac
done

# Get the knowledge base bucket name from CloudFormation
echo -e "${YELLOW}🔍 Getting knowledge base bucket name...${NC}"
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name AgentCoreOpenSearchStack \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseBucketName`].OutputValue' \
  --output text 2>/dev/null)

if [ -z "$BUCKET_NAME" ] || [ "$BUCKET_NAME" == "None" ]; then
    echo -e "${RED}❌ Error: Could not find knowledge base bucket${NC}"
    echo -e "${YELLOW}Make sure the AgentCoreOpenSearchStack is deployed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found bucket: ${BUCKET_NAME}${NC}\n"

# Upload documents if not sync-only
if [ "$SYNC_ONLY" = false ]; then
    if [ "$UPLOAD_EXAMPLES" = true ]; then
        # Upload example documents
        DOCS_DIR="docs/knowledge-base-examples"
        
        if [ ! -d "$DOCS_DIR" ]; then
            echo -e "${RED}❌ Error: Example documents directory not found: $DOCS_DIR${NC}"
            exit 1
        fi
        
        echo -e "${YELLOW}📤 Uploading example documents from ${DOCS_DIR}...${NC}"
        aws s3 cp "$DOCS_DIR/" "s3://$BUCKET_NAME/" \
            --recursive \
            --exclude "README.md" \
            --exclude "*.DS_Store"
        
        echo -e "${GREEN}✓ Example documents uploaded${NC}\n"
        
    elif [ -n "$CUSTOM_DIR" ]; then
        # Upload custom directory
        if [ ! -d "$CUSTOM_DIR" ]; then
            echo -e "${RED}❌ Error: Directory not found: $CUSTOM_DIR${NC}"
            exit 1
        fi
        
        echo -e "${YELLOW}📤 Uploading documents from ${CUSTOM_DIR}...${NC}"
        aws s3 cp "$CUSTOM_DIR/" "s3://$BUCKET_NAME/" \
            --recursive \
            --exclude "*.DS_Store"
        
        echo -e "${GREEN}✓ Documents uploaded from ${CUSTOM_DIR}${NC}\n"
        
    else
        echo -e "${YELLOW}ℹ️  No upload specified. Use --examples or provide a directory.${NC}"
        echo -e "${YELLOW}   Run with --help for usage information.${NC}\n"
    fi
    
    # Show what's in the bucket
    echo -e "${BLUE}📋 Current documents in knowledge base:${NC}"
    aws s3 ls "s3://$BUCKET_NAME/" --recursive --human-readable | grep -v "/$" || echo "  (empty)"
    echo ""
fi

# Get knowledge base and data source IDs
echo -e "${YELLOW}🔍 Getting knowledge base configuration...${NC}"
KB_ID=$(aws cloudformation describe-stacks \
  --stack-name AgentCoreOpenSearchStack \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseId`].OutputValue' \
  --output text 2>/dev/null)

DS_ID=$(aws cloudformation describe-stacks \
  --stack-name AgentCoreOpenSearchStack \
  --query 'Stacks[0].Outputs[?OutputKey==`DataSourceId`].OutputValue' \
  --output text 2>/dev/null)

if [ -z "$KB_ID" ] || [ -z "$DS_ID" ]; then
    echo -e "${RED}❌ Error: Could not find knowledge base or data source IDs${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Knowledge Base ID: ${KB_ID}${NC}"
echo -e "${GREEN}✓ Data Source ID: ${DS_ID}${NC}\n"

# Start ingestion job
echo -e "${YELLOW}🔄 Starting knowledge base sync...${NC}"
INGESTION_JOB=$(aws bedrock-agent start-ingestion-job \
  --knowledge-base-id "$KB_ID" \
  --data-source-id "$DS_ID" \
  --output json)

INGESTION_JOB_ID=$(echo "$INGESTION_JOB" | jq -r '.ingestionJob.ingestionJobId')

if [ -z "$INGESTION_JOB_ID" ]; then
    echo -e "${RED}❌ Error: Failed to start ingestion job${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Ingestion job started: ${INGESTION_JOB_ID}${NC}\n"

# Wait for sync if requested
if [ "$WAIT_FOR_SYNC" = true ]; then
    echo -e "${YELLOW}⏳ Waiting for sync to complete...${NC}"
    echo -e "${BLUE}   This usually takes 5-10 minutes depending on document count${NC}\n"
    
    STATUS="IN_PROGRESS"
    ATTEMPTS=0
    MAX_ATTEMPTS=60  # 60 attempts * 10 seconds = 10 minutes max
    
    while [ "$STATUS" = "IN_PROGRESS" ] && [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
        sleep 10
        ATTEMPTS=$((ATTEMPTS + 1))
        
        JOB_STATUS=$(aws bedrock-agent get-ingestion-job \
            --knowledge-base-id "$KB_ID" \
            --data-source-id "$DS_ID" \
            --ingestion-job-id "$INGESTION_JOB_ID" \
            --output json)
        
        STATUS=$(echo "$JOB_STATUS" | jq -r '.ingestionJob.status')
        
        # Show progress
        if [ $((ATTEMPTS % 6)) -eq 0 ]; then  # Every minute
            echo -e "${BLUE}   Still syncing... (${ATTEMPTS}0 seconds elapsed)${NC}"
        fi
    done
    
    if [ "$STATUS" = "COMPLETE" ]; then
        echo -e "\n${GREEN}✅ Knowledge base sync completed successfully!${NC}\n"
        
        # Show statistics
        STATS=$(echo "$JOB_STATUS" | jq -r '.ingestionJob.statistics')
        echo -e "${BLUE}📊 Sync Statistics:${NC}"
        echo "$STATS" | jq '.'
        echo ""
        
    elif [ "$STATUS" = "FAILED" ]; then
        echo -e "\n${RED}❌ Knowledge base sync failed${NC}"
        echo -e "${YELLOW}Check the failure reasons:${NC}"
        echo "$JOB_STATUS" | jq -r '.ingestionJob.failureReasons[]?' || echo "No failure reasons available"
        exit 1
        
    else
        echo -e "\n${YELLOW}⚠️  Sync is still in progress after 10 minutes${NC}"
        echo -e "${YELLOW}   Current status: ${STATUS}${NC}"
        echo -e "${YELLOW}   You can check status manually with:${NC}"
        echo -e "   ${GREEN}aws bedrock-agent get-ingestion-job \\${NC}"
        echo -e "   ${GREEN}  --knowledge-base-id $KB_ID \\${NC}"
        echo -e "   ${GREEN}  --data-source-id $DS_ID \\${NC}"
        echo -e "   ${GREEN}  --ingestion-job-id $INGESTION_JOB_ID${NC}"
    fi
else
    echo -e "${BLUE}ℹ️  Sync started in background${NC}"
    echo -e "${YELLOW}   Check sync status with:${NC}"
    echo -e "   ${GREEN}aws bedrock-agent list-ingestion-jobs \\${NC}"
    echo -e "   ${GREEN}  --knowledge-base-id $KB_ID \\${NC}"
    echo -e "   ${GREEN}  --data-source-id $DS_ID \\${NC}"
    echo -e "   ${GREEN}  --max-results 5${NC}\n"
    
    echo -e "${YELLOW}   Or run this script with --wait flag to wait for completion${NC}\n"
fi

echo -e "${GREEN}✅ Done!${NC}\n"

echo -e "${YELLOW}📝 Next steps:${NC}"
echo -e "1. Wait for the sync to complete (5-10 minutes)"
echo -e "2. Test the agent by asking questions about your documents"
echo -e "3. Check the web interface or use the API to interact with the agent"
echo ""
