# CloudFormation Samples

Deploy Amazon Bedrock AgentCore resources using CloudFormation templates.

## Prerequisites

- AWS CLI installed and configured
- CloudFormation permissions to create stacks and resources
- Access to Amazon Bedrock AgentCore (preview)

## General Deployment Pattern

```bash
# Deploy
aws cloudformation create-stack \
  --stack-name <stack-name> \
  --template-body file://<template-file> \
  --capabilities CAPABILITY_IAM \
  --region <region>

# Monitor
aws cloudformation describe-stacks \
  --stack-name <stack-name> \
  --region <region>

# Cleanup
aws cloudformation delete-stack \
  --stack-name <stack-name> \
  --region <region>
```

## Samples

- **[mcp-server-agentcore-runtime/](./mcp-server-agentcore-runtime/)** - MCP Server with JWT authentication
- **[basic-runtime/](./basic-runtime/)** - Simple agent deployment
- **[multi-agent-runtime/](./multi-agent-runtime/)** - Multi-agent system
- **[end-to-end-weather-agent/](./end-to-end-weather-agent/)** - Weather agent with tools and memory

## Troubleshooting

### Stack Creation Fails
```bash
aws cloudformation describe-stack-events \
  --stack-name <stack-name> \
  --region <region>
```

### CodeBuild Failures
```bash
aws codebuild batch-get-builds \
  --ids <build-id> \
  --region <region>
```
