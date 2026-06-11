#!/bin/bash
set -e

echo "=== AgentCore Gateway Setup for DB Performance Analyzer ==="
echo "This script will create all necessary resources for AgentCore Gateway"

# Create config directory
mkdir -p config

# Step 1: Install required packages
echo "Step 1: Installing required packages..."
# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment and install packages
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Step 2: Create IAM role for Gateway
echo "Step 2: Creating IAM role for Gateway..."
./scripts/create_iam_roles.sh

# Step 3: Set up Cognito resources
echo "Step 3: Setting up Cognito resources..."
source venv/bin/activate
python3 scripts/setup_cognito.py
deactivate

# Load Cognito configuration
if [ -f "config/cognito_config.env" ]; then
    source config/cognito_config.env
    echo "Loaded Cognito configuration"
else
    echo "Error: config/cognito_config.env not found"
    exit 1
fi

# Step 4: Create psycopg2 Lambda layer
echo "Step 4: Creating psycopg2 Lambda layer..."
./scripts/create_psycopg2_layer.sh

# Step 5: Get VPC configuration from database cluster
echo "Step 5: Getting VPC configuration..."
# Check if we have database configuration
if [ -f "config/db_prod_config.env" ]; then
    source config/db_prod_config.env
    if [ ! -z "$DB_CLUSTER_NAME" ]; then
        source venv/bin/activate
        python3 scripts/get_vpc_config.py --cluster-name "$DB_CLUSTER_NAME"
        deactivate
    else
        echo "Warning: DB_CLUSTER_NAME not found in config/db_prod_config.env"
    fi
elif [ -f "config/db_dev_config.env" ]; then
    source config/db_dev_config.env
    if [ ! -z "$DB_CLUSTER_NAME" ]; then
        source venv/bin/activate
        python3 scripts/get_vpc_config.py --cluster-name "$DB_CLUSTER_NAME"
        deactivate
    else
        echo "Warning: DB_CLUSTER_NAME not found in config/db_dev_config.env"
    fi
else
    echo "Warning: No database configuration found. Lambda will be created without VPC configuration."
fi

# Step 5b: Create VPC endpoints for AWS services
if [ -f "config/vpc_config.env" ]; then
    echo "Step 5b: Creating VPC endpoints for AWS services..."
    chmod +x ./scripts/create_vpc_endpoints.sh
    ./scripts/create_vpc_endpoints.sh
fi

# Step 6: Create Lambda function
echo "Step 6: Creating Lambda function..."
./scripts/create_lambda.sh

# Step 7: Create Gateway
echo "Step 7: Creating Gateway..."
# Load IAM configuration
if [ -f "config/iam_config.env" ]; then
    source config/iam_config.env
    echo "Loaded IAM configuration with GATEWAY_ROLE_ARN: $GATEWAY_ROLE_ARN"
else
    echo "Error: config/iam_config.env not found. Creating IAM roles again..."
    ./scripts/create_iam_roles.sh
    if [ -f "config/iam_config.env" ]; then
        source config/iam_config.env
        echo "Loaded IAM configuration with GATEWAY_ROLE_ARN: $GATEWAY_ROLE_ARN"
    else
        echo "Error: Failed to create IAM roles"
        exit 1
    fi
fi

# Set the role ARN for the gateway
export ROLE_ARN=$GATEWAY_ROLE_ARN
echo "Setting ROLE_ARN=$ROLE_ARN"

# Create the gateway
source venv/bin/activate
python3 scripts/create_gateway.py
deactivate

# Load Gateway configuration
if [ -f "config/gateway_config.env" ]; then
    source config/gateway_config.env
    echo "Loaded Gateway configuration with GATEWAY_IDENTIFIER: $GATEWAY_IDENTIFIER"
else
    echo "Warning: config/gateway_config.env not found, checking parent directory..."
    if [ -f "../config/gateway_config.env" ]; then
        # Copy the file to the expected location
        cp ../config/gateway_config.env config/
        source config/gateway_config.env
        echo "Loaded Gateway configuration with GATEWAY_IDENTIFIER: $GATEWAY_IDENTIFIER"
    else
        echo "Error: Gateway configuration not found in any location"
        exit 1
    fi
fi

# Step 8: Create Gateway Target
echo "Step 8: Creating Gateway Target..."
# Export environment variables for lambda-target-analyze-db-performance.py
export LAMBDA_ARN=$LAMBDA_ARN
export TARGET_NAME="db-performance-analyzer"
export TARGET_DESCRIPTION="DB Performance Analyzer tools"

# Create the target using create_target.py
source venv/bin/activate
python3 scripts/create_target.py
deactivate

# Step 9: Test Gateway
echo "Step 9: Testing Gateway..."
# Construct the gateway endpoint
MCP_ENDPOINT="https://${GATEWAY_IDENTIFIER}.gateway.bedrock-agentcore.${REGION}.amazonaws.com/mcp"

# Get a fresh token
echo "Getting a fresh token for testing..."
source venv/bin/activate
python3 scripts/get_token.py
deactivate

# Reload the Cognito configuration to get the fresh token
if [ -f "config/cognito_config.env" ]; then
    source config/cognito_config.env
    echo "Loaded fresh token from config/cognito_config.env"
fi

# Test listing tools with the correct format
echo "Testing listTools with the correct format..."
curl -s -X POST \
  -H "Authorization: Bearer $COGNITO_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "list-tools-request",
    "method": "tools/list",
    "params": {}
  }' \
  "$MCP_ENDPOINT" | jq .

# Test invoking explain_query tool with the correct format
echo -e "\nTesting invokeTool with the correct format..."
curl -s -X POST \
  -H "Authorization: Bearer $COGNITO_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "invoke-tool-request",
    "method": "tools/call",
    "params": {
      "name": "db-performance-analyzer___explain_query",
      "arguments": {
        "environment": "dev",
        "action_type": "explain_query",
        "query": "SELECT version()"
      }
    }
  }' \
  "$MCP_ENDPOINT" | jq .

# Test invoking slow_query tool with the correct format
echo -e "\nTesting slow_query tool..."
curl -s -X POST \
  -H "Authorization: Bearer $COGNITO_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "invoke-slow-query-request",
    "method": "tools/call",
    "params": {
      "name": "pgstat-analyzer___slow_query",
      "arguments": {
        "environment": "dev",
        "action_type": "slow_query"
      }
    }
  }' \
  "$MCP_ENDPOINT" | jq .

echo -e "\n=== Setup Complete ==="
echo "Gateway ID: $GATEWAY_IDENTIFIER"
echo "Gateway Endpoint: $MCP_ENDPOINT"
if [ -f "config/target_config.env" ]; then
    source config/target_config.env
    echo "Target ID: $TARGET_ID"
fi
echo "To clean up resources, run: ./cleanup.sh"