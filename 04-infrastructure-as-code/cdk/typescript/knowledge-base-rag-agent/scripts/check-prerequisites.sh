#!/bin/bash

# Prerequisite checker for Bedrock AgentCore Template
# This script verifies all required tools are installed and configured

set -e

echo "🔍 Checking prerequisites for Bedrock AgentCore Template..."
echo ""

ERRORS=0
WARNINGS=0

# Color codes for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
  if [ "$1" = "ok" ]; then
    echo -e "${GREEN}✓${NC} $2"
  elif [ "$1" = "error" ]; then
    echo -e "${RED}✗${NC} $2"
    ERRORS=$((ERRORS + 1))
  elif [ "$1" = "warning" ]; then
    echo -e "${YELLOW}⚠${NC} $2"
    WARNINGS=$((WARNINGS + 1))
  fi
}

# Check Node.js
echo "Checking Node.js..."
if command -v node &> /dev/null; then
  NODE_VERSION=$(node --version | cut -d'v' -f2)
  REQUIRED_NODE="24.8.0"
  if [ "$(printf '%s\n' "$REQUIRED_NODE" "$NODE_VERSION" | sort -V | head -n1)" = "$REQUIRED_NODE" ]; then
    print_status "ok" "Node.js $NODE_VERSION (>= $REQUIRED_NODE required)"
  else
    print_status "error" "Node.js $NODE_VERSION found, but >= $REQUIRED_NODE required"
    echo "  Install from: https://nodejs.org/"
  fi
else
  print_status "error" "Node.js not found"
  echo "  Install from: https://nodejs.org/"
fi

# Check npm
echo ""
echo "Checking npm..."
if command -v npm &> /dev/null; then
  NPM_VERSION=$(npm --version)
  REQUIRED_NPM="10.0.0"
  if [ "$(printf '%s\n' "$REQUIRED_NPM" "$NPM_VERSION" | sort -V | head -n1)" = "$REQUIRED_NPM" ]; then
    print_status "ok" "npm $NPM_VERSION (>= $REQUIRED_NPM required)"
  else
    print_status "error" "npm $NPM_VERSION found, but >= $REQUIRED_NPM required"
    echo "  Update with: npm install -g npm@latest"
  fi
else
  print_status "error" "npm not found"
fi

# Check AWS CLI
echo ""
echo "Checking AWS CLI..."
if command -v aws &> /dev/null; then
  AWS_VERSION=$(aws --version 2>&1 | cut -d' ' -f1 | cut -d'/' -f2)
  print_status "ok" "AWS CLI $AWS_VERSION"
  
  # Check AWS credentials
  if aws sts get-caller-identity &> /dev/null; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    REGION=$(aws configure get region || echo "not set")
    print_status "ok" "AWS credentials configured (Account: $ACCOUNT_ID, Region: $REGION)"
  else
    print_status "error" "AWS credentials not configured"
    echo "  Run: aws configure"
  fi
else
  print_status "error" "AWS CLI not found"
  echo "  Install from: https://aws.amazon.com/cli/"
fi

# Check Docker
echo ""
echo "Checking Docker..."
if command -v docker &> /dev/null; then
  DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | cut -d',' -f1)
  print_status "ok" "Docker $DOCKER_VERSION"
  
  # Check if Docker daemon is running
  if docker info &> /dev/null; then
    print_status "ok" "Docker daemon is running"
  else
    print_status "error" "Docker is installed but daemon is not running"
    echo "  Start Docker Desktop or run: sudo systemctl start docker"
  fi
else
  print_status "error" "Docker not found"
  echo "  Install from: https://www.docker.com/get-started"
fi

# Check CDK CLI
echo ""
echo "Checking AWS CDK CLI..."
if command -v cdk &> /dev/null; then
  CDK_VERSION=$(cdk --version | cut -d' ' -f1)
  print_status "ok" "AWS CDK $CDK_VERSION"
else
  print_status "warning" "AWS CDK CLI not found (optional but recommended)"
  echo "  Install with: npm install -g aws-cdk"
fi

# Check if dependencies are installed
echo ""
echo "Checking project dependencies..."
if [ -d "node_modules" ]; then
  print_status "ok" "Root dependencies installed"
else
  print_status "warning" "Root dependencies not installed"
  echo "  Run: npm install"
fi

if [ -d "infrastructure/node_modules" ]; then
  print_status "ok" "Infrastructure dependencies installed"
else
  print_status "warning" "Infrastructure dependencies not installed"
  echo "  Run: npm install"
fi

if [ -d "infrastructure/src/functions/layers/common/nodejs/node_modules" ]; then
  print_status "ok" "Lambda layer dependencies installed"
else
  print_status "warning" "Lambda layer dependencies not installed"
  echo "  Run: npm install"
fi

# Summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
  echo -e "${GREEN}✓ All prerequisites satisfied!${NC}"
  echo ""
  echo "Next steps:"
  echo "  1. Run: npm install (if dependencies not installed)"
  echo "  2. Run: npm run build --workspace=web-console"
  echo "  3. Run: ./scripts/deploy.sh"
  exit 0
elif [ $ERRORS -eq 0 ]; then
  echo -e "${YELLOW}⚠ Prerequisites mostly satisfied with $WARNINGS warning(s)${NC}"
  echo ""
  echo "You can proceed, but consider addressing the warnings above."
  exit 0
else
  echo -e "${RED}✗ $ERRORS error(s) and $WARNINGS warning(s) found${NC}"
  echo ""
  echo "Please install missing prerequisites before deploying."
  exit 1
fi
