# Knowledge Base RAG Agent - Infrastructure

## Overview

This directory contains AWS CDK infrastructure code for deploying a complete
Bedrock Agent application.

## Stacks

### Core Stacks

- **AgentCoreApiStack**: API Gateway and Lambda functions for agent
  interactions
- **BedrockStack**: Bedrock agent configuration and model access
- **WebHostingStack**: CloudFront distribution and S3 bucket for web console

### Supporting Stacks

- **NetworkStack**: VPC, subnets, and security groups
- **StorageStack**: DynamoDB tables and S3 buckets
- **DatabaseStack**: Additional database resources
- **CognitoStack**: User authentication and authorization
- **MonitoringStack**: CloudWatch dashboards and alarms

## Deployment

### Prerequisites

- AWS CLI configured
- Node.js 18+ installed
- AWS CDK CLI installed (`npm install -g aws-cdk`)

### Commands

```bash
# Install dependencies
npm install

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy all stacks
cdk deploy --all

# Deploy specific stack
cdk deploy AgentCoreApiStack

# Destroy all stacks
cdk destroy --all
```

### Environment Variables

- `CDK_DEFAULT_ACCOUNT`: AWS account ID
- `CDK_DEFAULT_REGION`: AWS region (default: us-east-1)

## Customization

### Adding New Stacks

1. Create stack file in `lib/stacks/`
2. Export from `lib/index.ts`
3. Add to `bin/infrastructure.ts`

### Modifying Existing Stacks

- Update stack files in `lib/stacks/`
- Modify constructs in `lib/constructs/`
- Update Lambda code in `lib/lambda/`

## Security

- All resources use least-privilege IAM policies
- API Gateway includes CORS configuration
- Lambda functions have appropriate execution roles
- DynamoDB tables use encryption at rest
