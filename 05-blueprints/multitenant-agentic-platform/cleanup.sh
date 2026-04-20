#!/bin/bash

set -e  # Exit on error

echo "🧹 Starting cleanup process..."
echo ""

# Get stack outputs
echo "📋 Retrieving stack information..."
STACK_OUTPUTS=$(aws cloudformation describe-stacks --stack-name BedrockAgentStack --query 'Stacks[0].Outputs' --output json 2>/dev/null || echo "[]")

if [ "$STACK_OUTPUTS" = "[]" ]; then
    echo "⚠️  Stack not found or already deleted. Skipping agent cleanup."
else
    # Extract API endpoint and key
    API_ENDPOINT=$(echo $STACK_OUTPUTS | jq -r '.[] | select(.OutputKey=="ApiEndpoint") | .OutputValue')
    API_KEY_ID=$(echo $STACK_OUTPUTS | jq -r '.[] | select(.OutputKey=="ApiKeyId") | .OutputValue')
    
    if [ -n "$API_ENDPOINT" ] && [ -n "$API_KEY_ID" ]; then
        # Get the actual API key value
        echo "🔑 Retrieving API key..."
        API_KEY=$(aws apigateway get-api-key --api-key $API_KEY_ID --include-value --query 'value' --output text 2>/dev/null || echo "")
        
        if [ -n "$API_KEY" ]; then
            echo "🤖 Fetching deployed agents..."
            
            # Get list of all agents (only agents deployed by this app from DynamoDB)
            AGENTS=$(curl -s -H "x-api-key: $API_KEY" "$API_ENDPOINT/agents" || echo "[]")
            
            # Check if we got valid JSON
            if echo "$AGENTS" | jq empty 2>/dev/null; then
                AGENT_COUNT=$(echo "$AGENTS" | jq 'length')
                
                if [ "$AGENT_COUNT" -gt 0 ]; then
                    echo "Found $AGENT_COUNT agent(s) deployed by this application to delete..."
                    echo ""
                    
                    # Ask for confirmation
                    read -p "⚠️  Are you sure you want to delete all agents and destroy the stack? (yes/no): " CONFIRM
                    
                    if [ "$CONFIRM" != "yes" ]; then
                        echo "❌ Cleanup cancelled by user"
                        exit 0
                    fi
                    
                    echo ""
                    
                    # Delete each agent
                    echo "$AGENTS" | jq -c '.[]' | while read -r agent; do
                        TENANT_ID=$(echo "$agent" | jq -r '.tenantId')
                        AGENT_ID=$(echo "$agent" | jq -r '.agentRuntimeId')
                        AGENT_NAME=$(echo "$agent" | jq -r '.agentName // "Unnamed"')
                        
                        echo "  🗑️  Deleting agent: $AGENT_NAME (Tenant: $TENANT_ID)"
                        
                        DELETE_RESPONSE=$(curl -s -X DELETE -H "x-api-key: $API_KEY" \
                            "$API_ENDPOINT/agent?tenantId=$TENANT_ID&agentRuntimeId=$AGENT_ID")
                        
                        if echo "$DELETE_RESPONSE" | grep -q "deleted successfully\|Agent deleted"; then
                            echo "     ✅ Deleted successfully"
                        else
                            echo "     ⚠️  Delete response: $DELETE_RESPONSE"
                        fi
                    done
                    
                    echo ""
                    echo "✅ All agents deleted"
                else
                    echo "✅ No agents found to delete"
                fi
            else
                echo "⚠️  Could not retrieve agents list. Proceeding with stack deletion..."
            fi
        else
            echo "⚠️  Could not retrieve API key. Skipping agent cleanup."
        fi
    else
        echo "⚠️  Could not find API endpoint or key. Skipping agent cleanup."
    fi
fi

echo ""
echo "☁️  Destroying CDK stack..."
echo ""

# Ask for final confirmation before destroying stack
read -p "⚠️  Proceed with CDK stack destruction? (yes/no): " STACK_CONFIRM

if [ "$STACK_CONFIRM" != "yes" ]; then
    echo "❌ Stack destruction cancelled by user"
    exit 0
fi

echo ""

cdk destroy --app "python3 src/cdk_app.py" --force

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "All resources have been removed:"
echo "  - Bedrock Agent Core agents"
echo "  - API Gateway and Lambda functions"
echo "  - DynamoDB tables"
echo "  - S3 buckets"
echo "  - CloudFront distribution"
echo "  - SQS queue"
echo "  - IAM roles"
