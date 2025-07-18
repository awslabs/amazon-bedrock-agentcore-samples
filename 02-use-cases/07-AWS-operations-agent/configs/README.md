# Bedrock AgentCore Gateway JSON Configuration System

---
## 📋 Navigation
**🏠 [README](../README.md)** | **📖 [Setup Guide](../docs/SETUP.md)** | **🏗️ [Architecture](../docs/ARCHITECTURE-FLOW.md)** | **🔧 [Scripts](../scripts/README.md)** | **🤖 [Client](../client/README.md)** | **⚙️ [Config](README.md)** | **🔐 [Okta Setup](../okta-auth/OKTA-OPENID-PKCE-SETUP.md)**
---

This directory contains the centralized JSON-based configuration system for the Bedrock AgentCore Gateway project. It provides a single source of truth for configuration and dynamic state management.

## 📁 **File Structure**

```
configs/
├── README.md                    # This file - Configuration documentation
├── bedrock-agentcore-config.json          # Static configuration (endpoints, schemas, environments)
└── config_manager.py            # Python module for config management
```

## 📋 **Configuration Files**

### **`bedrock-agentcore-config.json`** - Centralized Configuration
Contains all static configuration for the Bedrock AgentCore Gateway project:

#### **🔧 AWS Configuration**
- **Default Profile**: `demo1` for AWS CLI operations
- **Default Region**: `us-east-1` for AWS services
- **Default Account**: Your AWS account ID

#### **🌐 Bedrock AgentCore Gateway Settings**
- **Control Plane**: Production endpoints for gateway management
- **Gateway ID**: Your gateway ID (auto-generated)
- **Gateway URL**: Your gateway URL (auto-generated)

#### **🔐 Okta Authentication**
- **Discovery URL**: `https://dev-12345678.okta.com/oauth2/default/.well-known/openid-configuration`
- **Audience**: `api://default` for JWT validation
- **OAuth2 Configuration**: For Bedrock AgentCore Gateway authentication

#### **🛠️ Tool Schemas (21 AWS Tools)**
- **hello_world**: Basic greeting tool
- **get_time**: Server time tool
- **ec2_read_operations**: EC2 instance queries
- **s3_read_operations**: S3 bucket operations
- **lambda_read_operations**: Lambda function queries
- **cloudformation_read_operations**: Stack queries
- **iam_read_operations**: IAM role/policy queries
- **rds_read_operations**: Database queries
- **cloudwatch_read_operations**: Metrics and logs
- **cost_explorer_read_operations**: Cost analysis
- **ecs_read_operations**: Container queries
- **eks_read_operations**: Kubernetes queries
- **sns_read_operations**: Topic queries
- **sqs_read_operations**: Queue queries
- **dynamodb_read_operations**: Table queries
- **route53_read_operations**: DNS queries
- **apigateway_read_operations**: API queries
- **ses_read_operations**: Email queries
- **bedrock_read_operations**: Model queries
- **sagemaker_read_operations**: ML queries

#### **🌍 Environment Configurations**
- **AWS Profile/Region/Account**: Environment-specific AWS settings
- **Resource Prefixes**: For naming consistency
- **IAM Roles**: Bedrock AgentCore Gateway execution roles
- **Lambda ARNs**: Target Lambda function references

### **`config_manager.py`** - Configuration Manager

#### **📖 Configuration Access**
```python
from config_manager import BedrockAgentCoreConfigManager

config = BedrockAgentCoreConfigManager()
aws_config = config.get_aws_config('dev')
bedrock_agentcore_config = config.get_bedrock_agentcore_config()
okta_config = config.get_okta_authorizer_config()
```

#### **🔧 Key Methods**
- **`get_aws_config(environment)`**: AWS settings for specific environment
- **`get_bedrock_agentcore_config()`**: Bedrock AgentCore Gateway endpoints and settings
- **`get_okta_authorizer_config()`**: Okta authentication configuration
- **`get_tool_schemas()`**: All 21 MCP tool definitions
- **`get_environment_config(environment)`**: Environment-specific settings
- **`validate_config()`**: Validate configuration completeness
- **`update_gateway_info_from_response()`**: Update gateway info after creation
- **`clear_gateway_info()`**: Clear gateway info after deletion

## 🚀 **Usage Examples**

### **1. Basic Configuration Access**
```python
from config_manager import BedrockAgentCoreConfigManager

# Initialize configuration manager
config = BedrockAgentCoreConfigManager()

# Get AWS configuration for dev environment
aws_config = config.get_aws_config('dev')
print(f"AWS Profile: {aws_config['profile']}")
print(f"AWS Region: {aws_config['region']}")
print(f"AWS Account: {aws_config['account']}")
```

### **2. Bedrock AgentCore Gateway Configuration**
```python
# Get Bedrock AgentCore Gateway settings
bedrock_agentcore_config = config.get_bedrock_agentcore_config()
print(f"Control Plane: {bedrock_agentcore_config['control_plane']}")
print(f"Gateway ID: {bedrock_agentcore_config['gateway_id']}")
print(f"Data Plane URL: {bedrock_agentcore_config['gateway_url']}")
```

### **3. Tool Schema Access**
```python
# Get all tool schemas
tools = config.get_tool_schemas()
print(f"Available Tools: {len(tools)}")

# Get specific tool schema
ec2_tool = config.get_tool_schema('ec2_read_operations')
print(f"EC2 Tool Description: {ec2_tool['description']}")
```

### **4. Environment Configuration**
```python
# Get environment-specific configuration
env_config = config.get_environment_config('dev')
print(f"Lambda ARN: {env_config['lambda_arn']}")
print(f"Bedrock AgentCore Role: {env_config['bedrock_agentcore_role_arn']}")
```

### **5. Configuration Validation**
```python
# Validate configuration
is_valid = config.validate_config()
if is_valid:
    print("✅ Configuration is valid")
else:
    print("❌ Configuration has issues")
    
# Check for missing required settings
missing = config.validate_required_settings('dev')
if missing:
    print(f"Missing settings: {', '.join(missing)}")
```

## 🔧 **Configuration Management**

### **Updating Configuration**
```bash
# Edit the main configuration file
nano configs/bedrock-agentcore-config.json

# Validate configuration after changes
python -c "from config_manager import BedrockAgentCoreConfigManager; BedrockAgentCoreConfigManager().validate_config()"
```

### **Gateway Information Updates**
```python
# After creating a gateway, update configuration
gateway_response = {
    'gatewayId': 'abc123xyz',
    'gatewayUrl': 'https://abc123xyz.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp'
}
config.update_gateway_info_from_response(gateway_response)

# After deleting a gateway, clear configuration
config.clear_gateway_info('abc123xyz')
```

## 📋 **Configuration Schema**

### **Top-Level Structure**
```json
{
  "aws": { ... },
  "bedrock_agentcore": { ... },
  "okta": { ... },
  "environments": { ... },
  "tool_schemas": [ ... ]
}
```

### **Required Sections**
- ✅ **`aws`**: AWS account, region, profile settings
- ✅ **`bedrock_agentcore`**: Bedrock AgentCore Gateway endpoints and settings
- ✅ **`okta`**: Okta authentication configuration
- ✅ **`environments`**: Environment-specific configurations
- ✅ **`tool_schemas`**: Tool definitions for MCP

### **Validation**
```python
# Validate entire configuration
config = BedrockAgentCoreConfigManager()
is_valid = config.validate_config()

# Check specific sections
aws_valid = config.get_aws_config('dev') is not None
bedrock_agentcore_valid = config.get_bedrock_agentcore_config() is not None
```

## 🔍 **Example Configuration**

```json
{
  "aws": {
    "default_profile": "demo1",
    "default_region": "us-east-1",
    "default_account": "123456789012"
  },
  "bedrock_agentcore": {
    "service_account_id": "xxxxx",
    "service_name": "bedrock-agentcore-control",
    "active_endpoint": "production_endpoints",
    "production_endpoints": {
      "control_plane": "https://bedrock-agentcore-control.us-east-1.amazonaws.com",
      "gateway_id": "example-gateway-abc123def456",
      "gateway_url": "https://example-gateway-abc123def456.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
    }
  },
  "okta": {
    "audience": "api://default",
    "discovery_url": "https://dev-12345678.okta.com/oauth2/default/.well-known/openid-configuration"
  },
  "environments": {
    "dev": {
      "aws_profile": "demo1",
      "aws_region": "us-east-1",
      "aws_account": "123456789012",
      "resource_prefix": "dev",
      "bedrock_agentcore_role_name": "example-bedrock-agentcore-gateway-role",
      "bedrock_agentcore_policy_name": "example-bedrock-agentcore-gateway-policy"
    }
  }
}
```

## 🧰 **Configuration Manager API**

### **Basic Usage**
```python
from config_manager import BedrockAgentCoreConfigManager

# Initialize manager
config_manager = BedrockAgentCoreConfigManager()

# Get configuration for environment
config = config_manager.get_aws_config('dev')
```

### **Available Methods**

#### **AWS Configuration**
- `get_aws_config(environment)`: Get AWS settings for environment
- `get_default_environment()`: Get default environment name
- `get_environments()`: Get list of available environments

#### **Bedrock AgentCore Gateway Configuration**
- `get_bedrock_agentcore_endpoints()`: Get active endpoints
- `get_bedrock_agentcore_role_arn(environment)`: Get role ARN
- `get_mcp_endpoint_url(gateway_id)`: Get MCP endpoint URL
- `get_mcp_gateway_url(gateway_id)`: Get gateway URL

#### **Dynamic ARN Generation**
```python
# Generate ARNs and URLs
role_arn = config_manager.get_bedrock_agentcore_role_arn("prod")
lambda_arn = config_manager.get_lambda_arn("dev", "my-function")
mcp_url = config_manager.get_mcp_gateway_url("GATEWAY123")
```

#### **Tool Management**
- `get_tool_schemas()`: Get all tool schemas
- `get_tool_schema(tool_name)`: Get specific tool schema
- `get_tool_count()`: Get total number of tools
- `get_tool_names()`: Get list of all tool names

#### **Gateway Management**
- `update_gateway_info_from_response(response)`: Update gateway info
- `clear_gateway_info(gateway_id)`: Clear gateway info
- `get_gateway_description(environment)`: Generate gateway description
- `get_target_description(environment)`: Generate target description

#### **Utility Methods**
- `print_config_summary(environment)`: Print configuration summary
- `validate_config()`: Validate configuration completeness
- `validate_required_settings(environment)`: Check for missing settings

## 🔄 **Legacy Support**

For backward compatibility with .env files:

```python
# Get equivalent of .env variable
token_url = config_manager.get_env_equivalent('OKTA_TOKEN_URL')
```

## 🧪 **Testing**

```bash
# Run configuration manager tests
python config_manager.py

# Expected output:
# 🧪 Testing Bedrock AgentCore Configuration Manager
# ==================================================
# 📋 Configuration Summary
# ...
# ✅ Configuration Manager Test Complete
```

## 🔌 **Environment Variables**

For scripts that need environment variables:

```bash
export AWS_PROFILE=myprofile
export AWS_REGION=us-east-1
export BEDROCK_AGENTCORE_GATEWAY_ID=ABC123XYZ

python create-target-json.py
```

---
