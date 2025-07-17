# Setup Guide - Bedrock AgentCore Gateway MCP Integration

---
## 📋 Navigation
**🏠 [README](../README.md)** | **📖 [Setup Guide](SETUP.md)** | **🏗️ [Architecture](ARCHITECTURE-FLOW.md)** | **🔧 [Scripts](../scripts/README.md)** | **🤖 [Client](../client/README.md)** | **⚙️ [Config](../configs/README.md)** | **🔐 [Okta Setup](../okta-auth/OKTA-OPENID-PKCE-SETUP.md)**
---

## Prerequisites

- **AWS CLI**: Configured with `demo1` profile, region `us-east-1`
- **Python 3.11+**: For Lambda functions and scripts
- **AWS SAM CLI**: For Lambda deployment
- **Docker**: For container builds (required for Lambda deployments)
- **Okta Access Token**: For Bedrock AgentCore Gateway authentication
- **Latest boto3/botocore**: Install the latest wheel files for boto3/botocore (required for Bedrock AgentCore Gateway APIs)

## Step 1: Environment Setup

```bash
cd 07-Operational-Support-Lambda-Web-Adapter

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install boto3 python-dotenv requests

# Verify AWS setup
aws sts get-caller-identity --profile demo1
```

## Step 2: Configuration Setup

### **🔧 MANUAL STEP: Update Account ID**

```bash
# Get your AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --profile demo1 --query Account --output text)
echo "Your Account ID: $ACCOUNT_ID"

# Edit configuration file
nano configs/bedrock-agentcore-config.json
```

**Replace all instances of `YOUR_ACCOUNT_ID` with your actual account ID in:**
- `aws.default_account`
- `environments.dev.aws_account`
- `environments.dev.bedrock_agentcore_role_arn`
- `environments.dev.lambda_arn` (will update after Lambda deployment)

## Step 3: Deploy AWS Operations Agent Lambda

### **🔧 MANUAL STEP: Record Lambda ARN and Function URL**

```bash
cd agent-lambda

# Build and deploy
sam build --use-container
./deploy.sh dev

# Get Lambda ARN
LAMBDA_ARN=$(aws lambda get-function --function-name aws-operations-agent-dev --profile demo1 --query 'Configuration.FunctionArn' --output text)
echo "AWS Operations Agent Lambda ARN: $LAMBDA_ARN"

# Get Function URL
FUNCTION_URL=$(aws lambda get-function-url-config --function-name aws-operations-agent-dev --profile demo1 --query 'FunctionUrl' --output text)
echo "Function URL: $FUNCTION_URL"
```

### **🔧 MANUAL STEP: Update Configuration**

```bash
cd ..  # Back to project root
nano configs/bedrock-agentcore-config.json

# Update the following values:
# 1. environments.dev.lambda_arn with the ARN from above
# 2. environments.dev.function_url with the URL from above (without /stream suffix)
```

### **🧪 VALIDATION: Test AWS Operations Agent Lambda Deployment**

Before proceeding to MCP Tool Lambda deployment, verify the AWS Operations Agent Lambda is working correctly:

```bash
# Test basic Lambda invocation
aws lambda invoke \
  --function-name aws-operations-agent-dev \
  --payload '{"message": "Hello test"}' \
  --cli-binary-format raw-in-base64-out \
  --profile demo1 \
  --region us-east-1 \
  /tmp/agent-test-response.json

# Check the response
cat /tmp/agent-test-response.json
```

**Expected Response:** You should see:
1. **StatusCode: 200** - This confirms the Lambda executed successfully
2. **Response body with 404 Not Found** - This is expected since we're sending a basic test payload to a FastAPI application

The important part is the **StatusCode: 200**, which means the Lambda is deployed and running correctly. The 404 error in the response body is normal for this test.

**If you see errors:** Check the CloudWatch logs:
```bash
aws logs tail /aws/lambda/aws-operations-agent-dev --follow --profile demo1
```

## Step 4: Deploy MCP Tool Lambda

### **🔧 MANUAL STEP: Record MCP Lambda ARN**

```bash
cd mcp-tool-lambda

# Build and deploy Docker-based Lambda
./deploy-mcp-tool.sh

# Get MCP Tool Lambda ARN
MCP_LAMBDA_ARN=$(aws lambda get-function --function-name dev-bedrock-agentcore-mcp-tool --profile demo1 --query 'Configuration.FunctionArn' --output text)
echo "MCP Tool Lambda ARN: $MCP_LAMBDA_ARN"
```

### **🧪 VALIDATION: Test MCP Tool Lambda Deployment**

Before proceeding to Bedrock AgentCore Gateway setup, verify the MCP Tool Lambda is working correctly:

```bash
# Test basic Lambda invocation
aws lambda invoke \
  --function-name dev-bedrock-agentcore-mcp-tool \
  --payload '{"test": "hello"}' \
  --cli-binary-format raw-in-base64-out \
  --profile demo1 \
  --region us-east-1 \
  /tmp/mcp-test-response.json

# Check the response
cat /tmp/mcp-test-response.json
```

**Expected Response:** You should see:
1. **StatusCode: 200** - This confirms the Lambda executed successfully
2. **Response body containing `available_tools`** with a list of 20 AWS service tools:
   ```json
   {
     "success": false,
     "error": "Unable to determine tool name from context or event",
     "available_tools": ["hello_world", "get_time", "ec2_read_operations", "s3_read_operations", ...],
     "timestamp": "..."
   }
   ```

The key indicators of success are:
- **StatusCode: 200** (Lambda executed)
- **`available_tools` array** containing 20 tools (MCP tools are loaded correctly)

**If you see an error like "exec format error" or "Runtime.InvalidEntrypoint":**
This indicates a Docker architecture mismatch (ARM64 vs x86_64). Follow the troubleshooting steps in the Docker Architecture Issues section below.

## Step 5: Bedrock AgentCore Gateway Setup

> **⚠️ IMPORTANT: 64-Character Name Limit**
> 
> Bedrock AgentCore Gateway and Target names have a **64-character limit**. The scripts use short names to avoid this constraint:
> - Gateway names: `dev-aws-resource-inspector-gateway-{random}` (auto-generated)
> - Target names: `bac-tool` (Bedrock AgentCore tool - 8 chars)
> 
> Target names get prepended to tool names during invocation, so keeping them short is critical for longer tool names like `cloudformation_read_operations`.

### **🔧 MANUAL STEP: Create Gateway and Update Configuration**

```bash
cd ../scripts
source ../.venv/bin/activate

# List existing gateways (optional)
python list-gateways.py

# Create new gateway
python create-gateway.py --environment dev
```

After gateway creation, note the Gateway ID and URL from the output, then:

```bash
# Update bedrock-agentcore-config.json with the new gateway ID and URL
# The create-gateway.py script should automatically update these values
```

### Create Target

```bash
cd scripts

# Create target pointing to MCP Tool Lambda with SHORT name (critical for 64-char limit)
python create-target.py --environment dev --lambda-arn $MCP_LAMBDA_ARN --name "bac-tool"

# Verify target creation
python list-targets.py
```

> **⚠️ CRITICAL: Target Name Length**
> 
> The target name gets prepended to tool names when invoking tools. With tool names like `cloudformation_read_operations` (28 chars), using a short target name like `bac-tool` (8 chars) ensures we stay well under the 64-character limit (8 + 28 = 36 chars).
> 
> **bac-tool** = **B**edrock **A**gent**C**ore **tool** (short and descriptive)

## Step 6: Okta Authentication

### **🔧 MANUAL STEP: Setup Okta Token**

```bash
cd client

# Option 1: Use save_token.py script
python src/save_token.py

# Option 2: Create token file manually
echo "YOUR_OKTA_ACCESS_TOKEN" > ~/.okta_token

# Verify token file
ls -la ~/.okta_token
```

## Step 7: Testing

### Pre-Test Verification

```bash
# Verify all components are deployed
aws lambda get-function --function-name aws-operations-agent-dev --profile demo1 > /dev/null && echo "✅ AWS Operations Agent Lambda"
aws lambda get-function --function-name dev-bedrock-agentcore-mcp-tool --profile demo1 > /dev/null && echo "✅ MCP Tool Lambda"
[ -f "~/.okta_token" ] && echo "✅ Okta token file" || echo "❌ Missing Okta token"
```

### **🔧 MANUAL STEP: Interactive Testing**

```bash
cd client
python src/main.py --verbose

# Test these commands:
# 1. "What time is it? Use the get_time tool."
# 2. "List my S3 buckets"
# 3. "Show me EC2 instances"
# 4. "What Lambda functions do I have?"
```

### Verify Architecture Flow

The complete flow should work as:
1. **Client** → **Function URL** (SigV4 + Okta token)
2. **Function URL** → **AWS Operations Agent Lambda** (aws-operations-agent-dev)
3. **AWS Operations Agent Lambda** → **DynamoDB** (conversation persistence)
4. **AWS Operations Agent Lambda** → **Bedrock AgentCore Gateway** (MCP + Okta token)
5. **Bedrock AgentCore Gateway** → **MCP Tool Lambda** (validates Okta token)
6. **MCP Tool Lambda** → **20 AWS Tools** (EC2, S3, Lambda, etc.)

## Troubleshooting

### Common Issues

**Configuration Mismatch** (Most Common):
```bash
# Check configuration has actual values (not templates)
cd scripts
python -c "
import json
config = json.load(open('../configs/bedrock-agentcore-config.json'))
gateway_id = config['bedrock_agentcore']['production_endpoints']['gateway_id']
if '<' in gateway_id:
    print('❌ Configuration still has template values')
else:
    print('✅ Configuration updated with actual values')
"
```

**Authentication Errors**:
```bash
# Check Okta token
if [ -f "~/.okta_token" ] && [ $(wc -c < ~/.okta_token) -gt 100 ]; then
    echo "✅ Okta token appears valid"
else
    echo "❌ Okta token missing or invalid"
fi
```

**Lambda Deployment Issues**:
```bash
# Check Lambda logs
aws logs tail /aws/lambda/aws-operations-agent-dev --follow --profile demo1
aws logs tail /aws/lambda/dev-bedrock-agentcore-mcp-tool --follow --profile demo1
```

**Docker Architecture Issues** (Critical for Mac/ARM64 users):
```bash
# If you see "Runtime.InvalidEntrypoint" or "exec format error"
# This means Docker built for ARM64 but Lambda needs x86_64

# Fix: Rebuild with correct platform
cd mcp-tool-lambda/lambda
docker build --platform linux/amd64 -t mcp-tool-lambda:latest .

# Then redeploy
cd ..
sam deploy --template-file mcp-tool-template.yaml --stack-name dev-bedrock-agentcore-mcp-tool \
  --region us-east-1 --parameter-overrides Environment=dev  \
  --capabilities CAPABILITY_IAM --no-confirm-changeset --no-fail-on-empty-changeset \
  --resolve-s3 --resolve-image-repos --profile demo1

# Verify fix
aws lambda invoke --function-name dev-bedrock-agentcore-mcp-tool \
  --payload '{"test": "hello"}' --cli-binary-format raw-in-base64-out \
  --profile demo1 --region us-east-1 /tmp/test-response.json
cat /tmp/test-response.json
# Should show available_tools list, not exec format error
```

**Bedrock AgentCore Gateway Issues**:
```bash
cd scripts
python get-gateway.py  # Should show Status: READY
python get-target.py   # Should show Status: READY
```

### Quick Verification Commands

```bash
# Get your specific setup values
cd scripts
echo "Gateway ID: $(python list-gateways.py | grep 'Gateway ID' | head -1)"
echo "Target ID: $(python list-targets.py | grep 'Target ID' | head -1)"
echo "Function URL: $(aws lambda get-function-url-config --function-name aws-operations-agent-dev --profile demo1 --query 'FunctionUrl' --output text)"
```

## Dynamic Values Reference

These values are unique per deployment:
- **Gateway ID**: `dev-aws-resource-inspector-gateway-<random>` 
- **Target ID**: `<random-alphanumeric>`
- **Function URL**: `https://<unique-id>.lambda-url.us-east-1.on.aws/`

Always use YOUR specific values, not template placeholders like `<gateway-id>`.

---

**Setup Complete!** 🎉

Your Bedrock AgentCore Gateway MCP integration is ready for natural language AWS operations through the AWS Operations Agent interface.
