#!/bin/bash
set -e

# Get the script directory and project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Load VPC configuration
if [ -f "$PROJECT_DIR/config/vpc_config.env" ]; then
    source "$PROJECT_DIR/config/vpc_config.env"
    echo "Loaded VPC configuration"
    echo "VPC ID: $VPC_ID"
else
    echo "Error: VPC configuration not found at $PROJECT_DIR/config/vpc_config.env"
    exit 1
fi

# Set default region if not set
AWS_REGION=${AWS_REGION:-"us-west-2"}

echo "Cleaning up VPC endpoints..."

# Find and delete VPC endpoints
ENDPOINTS=$(aws ec2 describe-vpc-endpoints \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query "VpcEndpoints[?ServiceName.contains(@, 'com.amazonaws.$AWS_REGION')].VpcEndpointId" \
    --output json \
    --region $AWS_REGION)

# Remove quotes and brackets
ENDPOINTS=$(echo $ENDPOINTS | sed 's/\[//g' | sed 's/\]//g' | sed 's/"//g' | sed 's/,/ /g')

if [ ! -z "$ENDPOINTS" ]; then
    for ENDPOINT in $ENDPOINTS; do
        echo "Deleting VPC endpoint: $ENDPOINT"
        aws ec2 delete-vpc-endpoints \
            --vpc-endpoint-ids $ENDPOINT \
            --region $AWS_REGION
    done
else
    echo "No VPC endpoints found to delete"
fi

# Find and delete the security group for VPC endpoints
ENDPOINT_SG_NAME="vpc-endpoints-sg"
ENDPOINT_SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$ENDPOINT_SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
    --query "SecurityGroups[0].GroupId" \
    --output text \
    --region $AWS_REGION)

if [ "$ENDPOINT_SG_ID" != "None" ] && [ ! -z "$ENDPOINT_SG_ID" ]; then
    echo "Deleting security group for VPC endpoints: $ENDPOINT_SG_ID"
    aws ec2 delete-security-group \
        --group-id $ENDPOINT_SG_ID \
        --region $AWS_REGION || echo "Failed to delete security group, continuing..."
else
    echo "No security group found for VPC endpoints"
fi

echo "VPC endpoints cleanup completed"