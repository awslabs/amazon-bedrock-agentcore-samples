#!/bin/bash
set -e

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Load configurations
source "$PROJECT_DIR/config/iam_config.env"
source "$PROJECT_DIR/config/cognito_config.env"

echo "Creating Lambda functions for DB Performance Analyzer..."

# Use the correct path to the pg_analyze_performance.py file
PG_ANALYZE_PY_FILE="$SCRIPT_DIR/pg_analyze_performance.py"
if [ -f "$PG_ANALYZE_PY_FILE" ]; then
    echo "Using pg_analyze_performance.py from $PG_ANALYZE_PY_FILE"
else
    echo "Error: pg_analyze_performance.py not found at $PG_ANALYZE_PY_FILE"
    exit 1
fi

# Create a directory for the Lambda code
LAMBDA_DIR=$(mktemp -d)
echo "Creating Lambda package in $LAMBDA_DIR"
cp "$PG_ANALYZE_PY_FILE" "$LAMBDA_DIR/lambda_function.py"

# Create a zip file for the Lambda function
ZIP_FILE=$(mktemp).zip
(cd "$LAMBDA_DIR" && zip -r "$ZIP_FILE" .)
echo "Created zip file at $ZIP_FILE"

# Load VPC configuration if available
if [ -f "$PROJECT_DIR/config/vpc_config.env" ]; then
    source "$PROJECT_DIR/config/vpc_config.env"
    echo "Loaded VPC configuration"
    echo "VPC ID: $VPC_ID"
    echo "Subnet IDs: $SUBNET_IDS"
    echo "Lambda Security Group ID: $LAMBDA_SECURITY_GROUP_ID"
    echo "DB Security Group IDs: $DB_SECURITY_GROUP_IDS"
    
    # Check if LAMBDA_SECURITY_GROUP_ID is set
    if [ -z "$LAMBDA_SECURITY_GROUP_ID" ]; then
        echo "Error: LAMBDA_SECURITY_GROUP_ID is not set in vpc_config.env"
        exit 1
    fi
    
    # Prepare VPC config JSON
    VPC_CONFIG="{\"SubnetIds\":[\"${SUBNET_IDS//,/\",\"}\"],\"SecurityGroupIds\":[\"$LAMBDA_SECURITY_GROUP_ID\"]}"
    echo "VPC Config: $VPC_CONFIG"
    
    # Load layer configuration if available
    LAYERS_PARAM=""
    if [ -f "$PROJECT_DIR/config/layer_config.env" ]; then
        source "$PROJECT_DIR/config/layer_config.env"
        if [ ! -z "$PSYCOPG2_LAYER_ARN" ]; then
            LAYERS_PARAM="--layers $PSYCOPG2_LAYER_ARN"
            echo "Using psycopg2 layer: $PSYCOPG2_LAYER_ARN"
        else
            echo "Warning: PSYCOPG2_LAYER_ARN is empty in layer_config.env"
        fi
    else
        echo "Warning: layer_config.env not found at $PROJECT_DIR/config/layer_config.env"
        echo "Creating psycopg2 layer..."
        "$SCRIPT_DIR/create_psycopg2_layer.sh"
        if [ -f "$PROJECT_DIR/config/layer_config.env" ]; then
            source "$PROJECT_DIR/config/layer_config.env"
            if [ ! -z "$PSYCOPG2_LAYER_ARN" ]; then
                LAYERS_PARAM="--layers $PSYCOPG2_LAYER_ARN"
                echo "Using psycopg2 layer: $PSYCOPG2_LAYER_ARN"
            else
                echo "Error: PSYCOPG2_LAYER_ARN is still empty after creating layer"
                exit 1
            fi
        else
            echo "Error: layer_config.env still not found after creating layer"
            exit 1
        fi
    fi
    
    # Create the Lambda function with VPC configuration
    echo "Creating Lambda function with VPC configuration..."
    LAMBDA_RESPONSE=$(aws lambda create-function \
      --function-name DBPerformanceAnalyzer \
      --runtime python3.12 \
      --role $LAMBDA_ROLE_ARN \
      --handler lambda_function.lambda_handler \
      --zip-file fileb://$ZIP_FILE \
      --vpc-config "$VPC_CONFIG" \
      $LAYERS_PARAM \
      --timeout 30 \
      --environment "Variables={REGION=$AWS_REGION}" \
      --region $AWS_REGION)
    
else
    # Create the Lambda function without VPC configuration
    echo "Creating Lambda function without VPC configuration..."
    LAMBDA_RESPONSE=$(aws lambda create-function \
      --function-name DBPerformanceAnalyzer \
      --runtime python3.12 \
      --role $LAMBDA_ROLE_ARN \
      --handler lambda_function.lambda_handler \
      --zip-file fileb://$ZIP_FILE \
      --environment "Variables={REGION=$AWS_REGION}" \
      --region $AWS_REGION)
fi

LAMBDA_ARN=$(echo $LAMBDA_RESPONSE | jq -r '.FunctionArn')
echo "Lambda function created: $LAMBDA_ARN"

# Add permission for Gateway to invoke Lambda
echo "Adding permission for Gateway to invoke Lambda..."
echo "Gateway Role ARN: $GATEWAY_ROLE_ARN"

# Add permission for Gateway service to invoke Lambda
aws lambda add-permission \
  --function-name DBPerformanceAnalyzer \
  --statement-id GatewayServiceInvoke \
  --action lambda:InvokeFunction \
  --principal bedrock-agentcore.amazonaws.com \
  --region $AWS_REGION

# Add permission for Gateway role to invoke Lambda
aws lambda add-permission \
  --function-name DBPerformanceAnalyzer \
  --statement-id GatewayRoleInvoke \
  --action lambda:InvokeFunction \
  --principal $GATEWAY_ROLE_ARN \
  --region $AWS_REGION

# Clean up temporary files
rm -rf $LAMBDA_DIR
rm $ZIP_FILE

# Create config directory if it doesn't exist
mkdir -p "$PROJECT_DIR/config"

# Save Lambda ARN to config
cat > "$PROJECT_DIR/config/lambda_config.env" << EOF
export LAMBDA_ARN=$LAMBDA_ARN
EOF

# Create PGStat Lambda function
echo "Creating PGStat Lambda function..."

# Use the correct path to the pgstat_analyse_database.py file
PGSTAT_PY_FILE="$SCRIPT_DIR/pgstat_analyse_database.py"
if [ -f "$PGSTAT_PY_FILE" ]; then
    echo "Using pgstat_analyse_database.py from $PGSTAT_PY_FILE"
else
    echo "Error: pgstat_analyse_database.py not found at $PGSTAT_PY_FILE"
    exit 1
fi

# Create a directory for the Lambda code
PGSTAT_LAMBDA_DIR=$(mktemp -d)
echo "Creating PGStat Lambda package in $PGSTAT_LAMBDA_DIR"
cp "$PGSTAT_PY_FILE" "$PGSTAT_LAMBDA_DIR/lambda_function.py"

# Create a zip file for the Lambda function
PGSTAT_ZIP_FILE=$(mktemp).zip
(cd "$PGSTAT_LAMBDA_DIR" && zip -r "$PGSTAT_ZIP_FILE" .)
echo "Created PGStat zip file at $PGSTAT_ZIP_FILE"

# Create the Lambda function with VPC configuration if available
if [ -f "$PROJECT_DIR/config/vpc_config.env" ]; then
    # VPC config already loaded above
    
    # Create the Lambda function with VPC configuration
    echo "Creating PGStat Lambda function with VPC configuration..."
    PGSTAT_LAMBDA_RESPONSE=$(aws lambda create-function \
      --function-name PGStatAnalyzeDatabase \
      --runtime python3.12 \
      --role $LAMBDA_ROLE_ARN \
      --handler lambda_function.lambda_handler \
      --zip-file fileb://$PGSTAT_ZIP_FILE \
      --vpc-config "$VPC_CONFIG" \
      $LAYERS_PARAM \
      --timeout 300 \
      --environment "Variables={REGION=$AWS_REGION}" \
      --region $AWS_REGION)
    
else
    # Create the Lambda function without VPC configuration
    echo "Creating PGStat Lambda function without VPC configuration..."
    PGSTAT_LAMBDA_RESPONSE=$(aws lambda create-function \
      --function-name PGStatAnalyzeDatabase \
      --runtime python3.12 \
      --role $LAMBDA_ROLE_ARN \
      --handler lambda_function.lambda_handler \
      --zip-file fileb://$PGSTAT_ZIP_FILE \
      --timeout 300 \
      --environment "Variables={REGION=$AWS_REGION}" \
      --region $AWS_REGION)
fi

PGSTAT_LAMBDA_ARN=$(echo $PGSTAT_LAMBDA_RESPONSE | jq -r '.FunctionArn')
echo "PGStat Lambda function created: $PGSTAT_LAMBDA_ARN"

# Add permission for Gateway to invoke PGStat Lambda
echo "Adding permission for Gateway to invoke PGStat Lambda..."
echo "Gateway Role ARN: $GATEWAY_ROLE_ARN"

# Add permission for Gateway service to invoke PGStat Lambda
aws lambda add-permission \
  --function-name PGStatAnalyzeDatabase \
  --statement-id GatewayServiceInvoke \
  --action lambda:InvokeFunction \
  --principal bedrock-agentcore.amazonaws.com \
  --region $AWS_REGION

# Add permission for Gateway role to invoke PGStat Lambda
aws lambda add-permission \
  --function-name PGStatAnalyzeDatabase \
  --statement-id GatewayRoleInvoke \
  --action lambda:InvokeFunction \
  --principal $GATEWAY_ROLE_ARN \
  --region $AWS_REGION

# Clean up temporary files
rm -rf $PGSTAT_LAMBDA_DIR
rm $PGSTAT_ZIP_FILE

# Append PGStat Lambda ARN to config
cat >> "$PROJECT_DIR/config/lambda_config.env" << EOF
export PGSTAT_LAMBDA_ARN=$PGSTAT_LAMBDA_ARN
EOF

echo "Lambda functions setup completed successfully"