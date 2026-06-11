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

echo "Verifying DNS settings for VPC $VPC_ID..."

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

echo "DNS settings verification completed"