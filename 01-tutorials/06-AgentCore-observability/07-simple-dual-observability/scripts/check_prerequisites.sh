#!/bin/bash

# Exit on error for validation commands
set -e

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track overall status
ALL_CHECKS_PASSED=true

# Help text
show_help() {
    cat << EOF
Check prerequisites for AgentCore Simple Dual Observability Tutorial.

This script verifies:
1. AWS CLI installation and configuration
2. Python installation
3. Required Python packages
4. AWS permissions
5. Service availability

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -v, --verbose           Show detailed output

Example:
    # Run prerequisite checks
    ./check_prerequisites.sh

    # Run with verbose output
    ./check_prerequisites.sh --verbose

EOF
}

VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

echo "========================================"
echo "PREREQUISITE CHECK"
echo "========================================"
echo ""

# Function to print check result
print_result() {
    local check_name="$1"
    local status="$2"
    local message="$3"

    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}[PASS]${NC} $check_name"
        if [ "$VERBOSE" = true ] && [ -n "$message" ]; then
            echo "       $message"
        fi
    elif [ "$status" = "WARN" ]; then
        echo -e "${YELLOW}[WARN]${NC} $check_name"
        if [ -n "$message" ]; then
            echo "       $message"
        fi
    else
        echo -e "${RED}[FAIL]${NC} $check_name"
        if [ -n "$message" ]; then
            echo "       $message"
        fi
        ALL_CHECKS_PASSED=false
    fi
}

# Check 1: AWS CLI
echo "Checking AWS CLI..."
if command -v aws &> /dev/null; then
    AWS_VERSION=$(aws --version 2>&1 | awk '{print $1}')
    print_result "AWS CLI installed" "PASS" "$AWS_VERSION"
else
    print_result "AWS CLI installed" "FAIL" "AWS CLI not found. Install from: https://aws.amazon.com/cli/"
fi

# Check 2: AWS Credentials
echo "Checking AWS credentials..."
if aws sts get-caller-identity &> /dev/null; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    CALLER_ARN=$(aws sts get-caller-identity --query Arn --output text)
    print_result "AWS credentials configured" "PASS" "Account: $ACCOUNT_ID"
    if [ "$VERBOSE" = true ]; then
        echo "       ARN: $CALLER_ARN"
    fi
else
    print_result "AWS credentials configured" "FAIL" "Run 'aws configure' to set up credentials"
fi

# Check 3: AWS Region
echo "Checking AWS region..."
AWS_REGION=$(aws configure get region 2>/dev/null || echo "")
if [ -n "$AWS_REGION" ]; then
    print_result "AWS region configured" "PASS" "Region: $AWS_REGION"
else
    print_result "AWS region configured" "WARN" "No default region. Will use us-east-1"
    AWS_REGION="us-east-1"
fi

# Check 4: Python
echo "Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    MAJOR_VERSION=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR_VERSION=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$MAJOR_VERSION" -ge 3 ] && [ "$MINOR_VERSION" -ge 11 ]; then
        print_result "Python 3.11+ installed" "PASS" "Version: $PYTHON_VERSION"
    else
        print_result "Python 3.11+ installed" "WARN" "Version $PYTHON_VERSION found. Recommend 3.11+"
    fi
else
    print_result "Python 3.11+ installed" "FAIL" "Python 3 not found"
fi

# Check 5: boto3
echo "Checking Python packages..."
if python3 -c "import boto3" &> /dev/null; then
    BOTO3_VERSION=$(python3 -c "import boto3; print(boto3.__version__)" 2>&1)
    print_result "boto3 installed" "PASS" "Version: $BOTO3_VERSION"
else
    print_result "boto3 installed" "FAIL" "Install with: pip install boto3"
fi

# Check 6: jq (for JSON parsing)
echo "Checking utilities..."
if command -v jq &> /dev/null; then
    JQ_VERSION=$(jq --version 2>&1)
    print_result "jq installed" "PASS" "$JQ_VERSION"
else
    print_result "jq installed" "WARN" "jq recommended for JSON parsing. Install with: sudo apt install jq"
fi

# Check 7: curl
if command -v curl &> /dev/null; then
    print_result "curl installed" "PASS"
else
    print_result "curl installed" "FAIL" "Required for Braintrust setup. Install with: sudo apt install curl"
fi

# Check 8: Amazon Bedrock AgentCore service availability
echo "Checking AWS service availability..."
if aws bedrock-agentcore-runtime help &> /dev/null; then
    print_result "AgentCore Runtime service available" "PASS" "Region: $AWS_REGION"
else
    print_result "AgentCore Runtime service available" "WARN" "Service may not be available in $AWS_REGION or AWS CLI needs update"
fi

# Check 9: CloudWatch permissions
echo "Checking AWS permissions..."
if aws cloudwatch list-dashboards --max-results 1 &> /dev/null; then
    print_result "CloudWatch access" "PASS"
else
    print_result "CloudWatch access" "WARN" "Limited CloudWatch access. May affect dashboard creation"
fi

# Check 10: X-Ray permissions
if aws xray get-sampling-rules &> /dev/null; then
    print_result "X-Ray access" "PASS"
else
    print_result "X-Ray access" "WARN" "Limited X-Ray access. May affect trace viewing"
fi

# Check 11: CloudWatch Logs permissions
if aws logs describe-log-groups --max-items 1 &> /dev/null; then
    print_result "CloudWatch Logs access" "PASS"
else
    print_result "CloudWatch Logs access" "WARN" "Limited CloudWatch Logs access"
fi

# Summary
echo ""
echo "========================================"
echo "SUMMARY"
echo "========================================"
echo ""

if [ "$ALL_CHECKS_PASSED" = true ]; then
    echo -e "${GREEN}All critical checks passed!${NC}"
    echo ""
    echo "You are ready to run the setup:"
    echo "  ./setup_all.sh"
    echo ""
    exit 0
else
    echo -e "${RED}Some checks failed.${NC}"
    echo ""
    echo "Please address the failed checks before proceeding."
    echo ""
    echo "Common fixes:"
    echo "1. Install AWS CLI: https://aws.amazon.com/cli/"
    echo "2. Configure credentials: aws configure"
    echo "3. Install Python 3.11+: https://www.python.org/"
    echo "4. Install boto3: pip install boto3"
    echo "5. Update AWS CLI: pip install --upgrade awscli"
    echo ""
    exit 1
fi
