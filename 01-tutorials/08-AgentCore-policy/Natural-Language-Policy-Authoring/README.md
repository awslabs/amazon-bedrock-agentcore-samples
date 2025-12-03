# AgentCore Policy - Getting Started Demo

A complete, hands-on demo of implementing policy-based security controls for AI agents using Amazon Bedrock AgentCore Policy.

## 🚀 Quick Start

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Open notebook**: `jupyter notebook AgentCore-Policy-Demo.ipynb`
3. **Follow the steps** in the notebook

> **Note**: Requires boto3 version 1.42.0 or higher for native policy-registry API support.

## Overview

This demo provides a complete walkthrough of implementing policy-based security controls for AI agent interactions.

## What You'll Learn

- ✅ Setup AgentCore Gateway with Lambda targets
- ✅ Create and configure Policy Engines
- ✅ Write Cedar policies for fine-grained access control
- ✅ Test policy enforcement with real requests

## Demo Scenario

We'll build a **refund processing system** with policy controls:

- **Tool**: RefundTool (Lambda function)
- **Parameters**: 
  - `amount` (integer) - The refund amount in USD
  - `orderId` (string) - Unique identifier for the order
- **Policy Rule**: Only allow refunds under $1000
- **Test Cases**: 
  - ✅ $200 refund (ALLOWED)
  - ❌ $2000 refund (DENIED)

> **Important**: Policies can only reference parameters defined in the Gateway target schema. The RefundTool schema includes `amount` and `orderId` parameters.

## Prerequisites

Before starting, ensure you have:

- AWS CLI configured with appropriate credentials
- Python 3.10+ with boto3 1.42.0+ installed
- `bedrock_agentcore_starter_toolkit` package installed
- Access to AWS Lambda
- IAM role with trust policy for AgentCore service
- Working in **us-east-1 (N.Virginia)** region

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Important**: Ensure boto3 version 1.42.0 or higher is installed:

```bash
pip install --upgrade boto3
```

### 2. Open the Demo Notebook

```bash
jupyter notebook AgentCore-Policy-Demo.ipynb
```

### 3. Follow the Notebook

The notebook guides you through:

1. **Environment Setup** - Verify credentials and dependencies
2. **Lambda Creation** - Create RefundTool Lambda function
3. **Gateway Setup** - Configure AgentCore Gateway with OAuth
4. **Policy Engine** - Create policy engine and Cedar policies
5. **Testing** - Test ALLOW and DENY scenarios with real AI agents

> **Note**: The demo uses boto3's native policy-registry client (available in boto3 1.42.0+), eliminating the need for manual service model configuration.

## Project Structure

```
Getting-Started/
├── AgentCore-Policy-Demo.ipynb    # Main demo notebook
├── README.md                       # This file
├── requirements.txt                # Python dependencies
└── scripts/                        # Supporting scripts
    ├── setup_gateway.py            # Gateway setup
    ├── create_policies.py          # Policy creation
    ├── test_gateway_policies.py    # Policy testing
    ├── policy_generator.py         # NL to Cedar generation
    ├── deploy_lambda.py            # Lambda deployment
    └── refund_tool.mjs             # Lambda function code
```

## Key Concepts

### AgentCore Gateway

A MCP like client that allows agents to access tools.

### Policy Engine

A collection of Cedar policies that evaluates requests against defined rules in real-time.

### Cedar Policy Language

A declarative policy language with this structure:

```cedar
permit(
  principal,              // Who can access
  action,                 // What action they can perform  
  resource                // What resource they can access
) when {
  conditions              // Under what conditions
};
```

### Policy Modes

- **LOG_ONLY**: Evaluates policies but doesn't block requests (for testing)
- **ENFORCE**: Actively blocks requests that violate policies (for production)

## Example Policy

```cedar
permit(
  principal,
  action == AgentCore::Action::"RefundToolTarget___refund",
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  context.input.amount <= 1000
};
```

This policy:
- Allows refund requests under $1000
- Denies refund requests of $1000 or more
- Applies to the RefundTool target
- Evaluates the `amount` parameter in real-time

## Architecture

```
┌─────────────┐
│   AI Agent  │
└──────┬──────┘
       │ Tool Call Request
       ▼
┌─────────────────────┐
│  AgentCore Gateway  │
│  + OAuth Auth       │
└──────┬──────────────┘
       │ Policy Check
       ▼
┌─────────────────────┐
│   Policy Engine     │
│   (Cedar Policies)  │
└──────┬──────────────┘
       │ ALLOW / DENY
       ▼
┌─────────────────────┐
│   Lambda Target     │
│   (RefundTool)      │
└─────────────────────┘
```

## Testing

The demo includes comprehensive testing:

### Test 1: ALLOW Scenario ✅
- Amount: $200
- Expected: ALLOWED
- Reason: $200 <= $1000
- Result: Lambda executes, refund processed

### Test 2: DENY Scenario ❌
- Amount: $2000
- Expected: DENIED
- Reason: $2000 > $1000
- Result: Policy blocks request, Lambda never executes

## Advanced Features

### Multiple Conditions

```cedar
permit(...) when {
  context.input.amount <= 1000 &&
  has(context.input.orderId) &&
  context.input.orderId != ""
};
```

### Order-Based Conditions

```cedar
permit(...) when {
  context.input.amount <= 1000 &&
  context.input.orderId.startsWith("VIP")
};
```

### Range-Based Conditions

```cedar
permit(...) when {
  context.input.amount >= 100 &&
  context.input.amount <= 1000
};
```

### Deny Policies

```cedar
forbid(...) when {
  context.input.amount > 10000
};
```

## Monitoring and Debugging

### CloudWatch Logs

Policy decisions are logged to CloudWatch:

- **Gateway Logs**: Request/response details
- **Policy Engine Logs**: Policy evaluation results
- **Lambda Logs**: Tool execution details

### Common Issues

1. **Policy Not Enforcing**
   - Verify ENFORCE mode (not LOG_ONLY)
   - Check policy status is ACTIVE
   - Confirm gateway attachment

2. **All Requests Denied**
   - Review policy conditions
   - Verify action name matches target
   - Check resource ARN matches gateway

3. **Authentication Failures**
   - Verify OAuth credentials
   - Check token endpoint accessibility
   - Ensure client_id and client_secret are correct

4. **Module Import Errors**
   - Ensure boto3 1.42.0+ is installed: `pip install --upgrade boto3`
   - Restart Jupyter kernel after updating dependencies
   - Clear Python cache: `rm -rf scripts/__pycache__`


## Additional Resources

- **Cedar Policy Language**: [Cedar Documentation](https://docs.cedarpolicy.com/)
- **Amazon Bedrock AgentCore Policy**: [AWS AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html)

---

**Happy Building!** 🚀
