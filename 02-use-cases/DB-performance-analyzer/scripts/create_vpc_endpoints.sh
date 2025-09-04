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
    echo "Subnet IDs: $SUBNET_IDS"
else
    echo "Error: VPC configuration not found at $PROJECT_DIR/config/vpc_config.env"
    exit 1
fi

# Set default region if not set
AWS_REGION=${AWS_REGION:-"us-west-2"}

# First, verify and fix DNS settings
echo "Verifying DNS settings for VPC..."
# Check DNS support
DNS_SUPPORT=$(aws ec2 describe-vpc-attribute --vpc-id $VPC_ID --attribute enableDnsSupport --region $AWS_REGION --query 'EnableDnsSupport.Value' --output text)
if [ "$DNS_SUPPORT" == "True" ] || [ "$DNS_SUPPORT" == "true" ]; then
    echo "DNS support is already enabled for VPC $VPC_ID"
else
    echo "Enabling DNS support for VPC $VPC_ID..."
    aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-support "{\"Value\":true}" --region $AWS_REGION
    echo "DNS support enabled"
fi

# Check DNS hostnames
DNS_HOSTNAMES=$(aws ec2 describe-vpc-attribute --vpc-id $VPC_ID --attribute enableDnsHostnames --region $AWS_REGION --query 'EnableDnsHostnames.Value' --output text)
if [ "$DNS_HOSTNAMES" == "True" ] || [ "$DNS_HOSTNAMES" == "true" ]; then
    echo "DNS hostnames are already enabled for VPC $VPC_ID"
else
    echo "Enabling DNS hostnames for VPC $VPC_ID..."
    aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames "{\"Value\":true}" --region $AWS_REGION
    echo "DNS hostnames enabled"
fi

echo "Creating VPC endpoints for AWS services..."

# Create security group for VPC endpoints
ENDPOINT_SG_NAME="vpc-endpoints-sg"
ENDPOINT_SG_DESC="Security group for VPC endpoints"

# Check if security group already exists
EXISTING_SG=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$ENDPOINT_SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
    --query "SecurityGroups[0].GroupId" \
    --output text \
    --region $AWS_REGION)

if [ "$EXISTING_SG" != "None" ] && [ ! -z "$EXISTING_SG" ]; then
    echo "Using existing security group: $EXISTING_SG"
    ENDPOINT_SG_ID=$EXISTING_SG
else
    echo "Creating security group for VPC endpoints..."
    ENDPOINT_SG_ID=$(aws ec2 create-security-group \
        --group-name $ENDPOINT_SG_NAME \
        --description "$ENDPOINT_SG_DESC" \
        --vpc-id $VPC_ID \
        --region $AWS_REGION \
        --output text \
        --query "GroupId")
    
    echo "Created security group: $ENDPOINT_SG_ID"
    
    # Add inbound rule to allow traffic from Lambda security group
    aws ec2 authorize-security-group-ingress \
        --group-id $ENDPOINT_SG_ID \
        --protocol tcp \
        --port 443 \
        --source-group $LAMBDA_SECURITY_GROUP_ID \
        --region $AWS_REGION
    
    echo "Added inbound rule to allow traffic from Lambda security group"
fi

# Get account ID for endpoint policy
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create endpoint policy that restricts access to this account only
ENDPOINT_POLICY='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":"*","Action":"*","Resource":"*","Condition":{"StringEquals":{"aws:PrincipalAccount":"'"$ACCOUNT_ID"'"}}}]}'

# Create VPC endpoints for required AWS services
SERVICES=("ssm" "secretsmanager" "logs" "monitoring")

for SERVICE in "${SERVICES[@]}"; do
    echo "Creating VPC endpoint for $SERVICE..."
    
    # Check if endpoint already exists
    EXISTING_ENDPOINT=$(aws ec2 describe-vpc-endpoints \
        --filters "Name=vpc-id,Values=$VPC_ID" "Name=service-name,Values=com.amazonaws.$AWS_REGION.$SERVICE" \
        --query "VpcEndpoints[0].VpcEndpointId" \
        --output text \
        --region $AWS_REGION)
    
    if [ "$EXISTING_ENDPOINT" != "None" ] && [ ! -z "$EXISTING_ENDPOINT" ]; then
        echo "VPC endpoint for $SERVICE already exists: $EXISTING_ENDPOINT"
        
        # Update the existing endpoint policy
        echo "Updating policy for existing endpoint $EXISTING_ENDPOINT..."
        aws ec2 modify-vpc-endpoint \
            --vpc-endpoint-id $EXISTING_ENDPOINT \
            --policy "$ENDPOINT_POLICY" \
            --region $AWS_REGION
        
        continue
    fi
    
    # Convert comma-separated subnet IDs to array for AWS CLI
    IFS=',' read -ra SUBNET_ARRAY <<< "$SUBNET_IDS"
    
    # Create the VPC endpoint with proper subnet formatting
    echo "Creating endpoint for $SERVICE with subnets: ${SUBNET_ARRAY[@]}"
    ENDPOINT_ID=$(aws ec2 create-vpc-endpoint \
        --vpc-id $VPC_ID \
        --vpc-endpoint-type Interface \
        --service-name com.amazonaws.$AWS_REGION.$SERVICE \
        --subnet-ids ${SUBNET_ARRAY[@]} \
        --security-group-ids $ENDPOINT_SG_ID \
        --policy "$ENDPOINT_POLICY" \
        --private-dns-enabled \
        --region $AWS_REGION \
        --output text \
        --query "VpcEndpoint.VpcEndpointId")
    
    echo "Created VPC endpoint for $SERVICE: $ENDPOINT_ID"
done

# Verify route tables for the subnets
echo "Verifying route tables for subnets..."
IFS=',' read -ra SUBNET_ARRAY <<< "$SUBNET_IDS"
for SUBNET in "${SUBNET_ARRAY[@]}"; do
    echo "Checking route table for subnet $SUBNET"
    ROUTE_TABLE=$(aws ec2 describe-route-tables \
        --filters "Name=association.subnet-id,Values=$SUBNET" \
        --query "RouteTables[0].RouteTableId" \
        --output text \
        --region $AWS_REGION)
    
    if [ "$ROUTE_TABLE" != "None" ] && [ ! -z "$ROUTE_TABLE" ]; then
        echo "Subnet $SUBNET is associated with route table $ROUTE_TABLE"
    else
        echo "WARNING: Subnet $SUBNET is not associated with any route table!"
    fi
done

echo "VPC endpoints created successfully"