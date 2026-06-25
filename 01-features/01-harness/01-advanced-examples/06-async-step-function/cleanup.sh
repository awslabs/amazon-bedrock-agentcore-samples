#!/bin/bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}  Weather Workflow Cleanup${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# Load config
if [ ! -f "deployment_info.json" ]; then
  echo -e "${YELLOW}⚠ deployment_info.json not found${NC}"
  read -p "Stack name [weather-workflow-stack]: " STACK_NAME
  STACK_NAME=${STACK_NAME:-weather-workflow-stack}
  read -p "Region [us-west-2]: " REGION
  REGION=${REGION:-us-west-2}
else
  STACK_NAME=$(jq -r '.stackName' deployment_info.json)
  REGION=$(jq -r '.region' deployment_info.json)
  DYNAMO_TABLE=$(jq -r '.dynamoTableName' deployment_info.json)
fi

echo "Stack: $STACK_NAME"
echo "Region: $REGION"
echo ""

read -p "Delete all resources? [y/N]: " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  echo -e "${YELLOW}Cancelled${NC}"
  exit 0
fi
echo ""

# Optional: Empty DynamoDB first
if [ ! -z "$DYNAMO_TABLE" ] && [ "$DYNAMO_TABLE" != "null" ]; then
  ITEM_COUNT=$(aws dynamodb scan \
    --table-name "$DYNAMO_TABLE" \
    --region $REGION \
    --select COUNT \
    --output json 2>/dev/null | jq -r '.Count' || echo "0")

  if [ "$ITEM_COUNT" -gt 0 ]; then
    echo "DynamoDB table has $ITEM_COUNT items"
    read -p "Delete items first (faster)? [y/N]: " DELETE_ITEMS
    if [[ "$DELETE_ITEMS" =~ ^[Yy]$ ]]; then
      echo "Deleting items..."
      aws dynamodb scan --table-name "$DYNAMO_TABLE" --region $REGION | \
        jq -r '.Items[] | [.id.S, .timestamp.S] | @tsv' | \
        while IFS=$'\t' read -r id timestamp; do
          aws dynamodb delete-item \
            --table-name "$DYNAMO_TABLE" \
            --key "{\"id\":{\"S\":\"$id\"},\"timestamp\":{\"S\":\"$timestamp\"}}" \
            --region $REGION 2>/dev/null || true
        done
      echo -e "${GREEN}✓ Items deleted${NC}"
    fi
  fi
fi

echo ""
echo "Deleting CloudFormation stack..."
aws cloudformation delete-stack \
  --stack-name "$STACK_NAME" \
  --region $REGION

echo "Waiting for deletion..."
aws cloudformation wait stack-delete-complete \
  --stack-name "$STACK_NAME" \
  --region $REGION 2>&1

if [ $? -eq 0 ]; then
  echo -e "${GREEN}✓ Stack deleted${NC}"
else
  echo -e "${YELLOW}⚠ Check AWS Console for status${NC}"
fi

# Clean up local files
rm -f deployment_info.json

echo ""
echo -e "${BLUE}=====================================${NC}"
echo -e "${GREEN}✓ Cleanup Complete!${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""
