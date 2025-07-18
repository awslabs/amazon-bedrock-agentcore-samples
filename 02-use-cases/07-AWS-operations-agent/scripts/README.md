# Bedrock AgentCore Gateway Scripts

---
## 📋 Navigation
**🏠 [README](../README.md)** | **📖 [Setup Guide](../docs/SETUP.md)** | **🏗️ [Architecture](../docs/ARCHITECTURE-FLOW.md)** | **🔧 [Scripts](README.md)** | **🤖 [Client](../client/README.md)** | **⚙️ [Config](../configs/README.md)** | **🔐 [Okta Setup](../okta-auth/OKTA-OPENID-PKCE-SETUP.md)**
---

This directory contains **10 essential scripts** for Bedrock AgentCore Gateway management. All scripts read configuration from `/configs` and show clean, formatted request/response objects.

## 📋 **Essential Scripts**

### **1. create-gateway.py** - Create Bedrock AgentCore Gateway
```bash
# Create gateway for dev environment
python create-gateway.py --environment dev

# Create gateway with custom name
python create-gateway.py --name "my-custom-gateway"

# Create gateway with custom description
python create-gateway.py --description "My custom gateway"
```
- ✅ **Reads config** from `/configs/bedrock-agentcore-config.json`
- ✅ **Updates state** in `/configs/bedrock-agentcore-config.json`
- ✅ **Shows formatted** request/response objects

### **2. create-target.py** - Create MCP Target
```bash
# Create target for dev environment
python create-target.py --environment dev

# Create target with custom name
python create-target.py --name "my-custom-target"

# Create target with specific Lambda ARN
python create-target.py --lambda-arn "arn:aws:lambda:us-west-2:123456789012:function:my-function"
```
- ✅ **Reads config** from `/configs/bedrock-agentcore-config.json`
- ✅ **Updates state** in `/configs/bedrock-agentcore-config.json`
- ✅ **Shows formatted** request/response objects
- ✅ **Auto-detects** available gateways

### **3. list-gateways.py** - List All Gateways
```bash
# List all gateways
python list-gateways.py

# List gateways with specific endpoint
python list-gateways.py --endpoint production

# Update local config with live data
python list-gateways.py --update-config
```
- ✅ **Pulls live data** from AWS Bedrock AgentCore API
- ✅ **Shows formatted** response objects
- ✅ **Optionally updates** local config

### **4. list-targets.py** - List All Targets
```bash
# List all targets for active gateway
python list-targets.py

# List targets for specific gateway
python list-targets.py --gateway-id ABC123XYZ

# Update local config with live data
python list-targets.py --update-config
```
- ✅ **Pulls live data** from AWS Bedrock AgentCore API
- ✅ **Shows formatted** response objects
- ✅ **Detailed tool information**

### **5. update-gateway.py** - Update Gateway
```bash
# Update gateway name
python update-gateway.py --gateway-id ABC123XYZ --name "New Name"

# Update gateway description
python update-gateway.py --gateway-id ABC123XYZ --description "New description"

# Update gateway role ARN
python update-gateway.py --gateway-id ABC123XYZ --description "Updated description" --role-arn "arn:aws:iam::123456789012:role/new-role"
```
- ✅ **Reads config** from `/configs/bedrock-agentcore-config.json`
- ✅ **Shows formatted** request/response objects
- ✅ **Confirmation prompt** for safety

### **6. update-target.py** - Update Target
```bash
# Update target name
python update-target.py --gateway-id ABC123XYZ --target-id DEF456UVW --name "New Name"

# Update target description
python update-target.py --gateway-id ABC123XYZ --target-id DEF456UVW --description "New description"

# Update target tools from file
python update-target.py --gateway-id ABC123XYZ --target-id DEF456UVW --tools-file "/path/to/tools.json"
```
- ✅ **Reads config** from `/configs/bedrock-agentcore-config.json`
- ✅ **Shows formatted** request/response objects
- ✅ **Confirmation prompt** for safety

### **7. delete-target.py** - Delete Target
```bash
# Delete target with confirmation prompt
python delete-target.py --gateway-id ABC123XYZ --target-id DEF456UVW

# Force delete without confirmation
python delete-target.py --gateway-id ABC123XYZ --target-id DEF456UVW --force
```
- ✅ **Reads config** from `/configs/bedrock-agentcore-config.json`
- ✅ **Updates state** in `/configs/bedrock-agentcore-config.json`
- ✅ **Shows formatted** request/response objects
- ✅ **Confirmation prompt** for safety

### **8. delete-gateway.py** - Delete Gateway
```bash
# Delete gateway with confirmation prompt
python delete-gateway.py --gateway-id ABC123XYZ

# Force delete without confirmation
python delete-gateway.py --gateway-id ABC123XYZ --force
```
- ✅ **Reads config** from `/configs/bedrock-agentcore-config.json`
- ✅ **Shows formatted** request/response objects
- ✅ **Auto-deletes targets** if requested
- ✅ **Confirmation prompt** for safety

### **9. get-gateway.py** - Get Gateway Details
```bash
# Get gateway details
python get-gateway.py --gateway-id ABC123XYZ

# Get gateway details and update local config
python get-gateway.py --gateway-id ABC123XYZ --update-local
```
- ✅ **Pulls live data** from AWS Bedrock AgentCore API
- ✅ **Shows formatted** request/response objects
- ✅ **Detailed configuration** display

### **10. get-target.py** - Get Target Details
```bash
# Get target details
python get-target.py --gateway-id ABC123XYZ --target-id DEF456UVW

# Get target details and update local config
python get-target.py --gateway-id ABC123XYZ --target-id DEF456UVW --update-local
```
- ✅ **Pulls live data** from AWS Bedrock AgentCore API
- ✅ **Shows formatted** request/response objects
- ✅ **Detailed tool schemas** display

### **Configuration Files Used**
- **`/configs/bedrock-agentcore-config.json`** - Static configuration (endpoints, schemas, environments)

### **Live Data Approach**
- ✅ **All scripts** pull live data from AWS Bedrock AgentCore API
- ✅ **No local state** management - AWS is single source of truth
- ✅ **Configuration-driven** with environment-specific settings

## 🔍 **Example Outputs**

### **Create Gateway Response**
```json
{
  "gatewayId": "example-gateway-abc123def456",
  "gatewayArn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:gateway/example-gateway-abc123def456",
  "gatewayUrl": "https://example-gateway-abc123def456.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
  "name": "example-operations-gateway",
  "description": "AWS Operations Agent Gateway for AWS operations",
  "status": "CREATING",
  "protocolType": "MCP",
  "authorizerType": "CUSTOM_JWT",
  "customJWTAuthorizer": {
    "allowedAudience": ["api://default"],
    "discoveryUrl": "https://dev-12345678.okta.com/oauth2/default/.well-known/openid-configuration"
  },
  "roleArn": "arn:aws:iam::123456789012:role/example-bedrock-agentcore-gateway-role",
  "createdAt": "2025-07-01T17:00:00.000Z",
  "updatedAt": "2025-07-01T17:00:00.000Z"
}
```

### **Create Target Response**
```json
{
  "gatewayArn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:gateway/example-gateway-abc123def456",
  "targetId": "EXAMPLE123",
  "name": "example-mcp-target",
  "description": "Example MCP tools target with sample configuration",
  "status": "CREATING",
  "protocolType": "MCP",
  "authorizerType": "CUSTOM_JWT",
  "roleArn": "arn:aws:iam::123456789012:role/example-bedrock-agentcore-gateway-role",
  "createdAt": "2025-07-01T17:00:00.000Z",
  "updatedAt": "2025-07-01T17:00:00.000Z"
}
```

### **List Gateways Response**
```
Live Gateways:
============================================================
Gateway ID: example-gateway-abc123def456
Gateway Name: example-operations-gateway
Status: READY
Description: AWS Operations Agent Gateway for AWS operations
Created: 2025-07-01 17:00:00.000000+00:00
Updated: 2025-07-01 17:00:00.000000+00:00
MCP Endpoint: https://example-gateway-abc123def456.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp
```

## 🧰 **Script Design**

### **Common Features**
- **Consistent interface** across all scripts
- **Detailed help** with `--help` flag
- **Environment support** with `--environment` flag
- **AWS profile selection** with `--profile` flag
- **Endpoint selection** with `--endpoint` flag
- **Formatted output** for readability
- **Error handling** with clear messages

### **Live Data Approach**
- **All scripts** pull live data from AWS Bedrock AgentCore API
- **AWS Bedrock AgentCore API** is the single source of truth
- **Configuration-driven** with environment-specific settings
- **No local state** synchronization complexity

### **Configuration Management**
- **Read from** `/configs/bedrock-agentcore-config.json`
- **Update to** `/configs/bedrock-agentcore-config.json` when needed
- **Environment-specific** settings (dev, staging, prod)
- **Endpoint selection** (beta, gamma, production)

## 🚀 **Getting Started**

### **Prerequisites**
- Python 3.11+
- boto3 library
- AWS CLI configured

### **Configuration Setup**
1. **Valid `/configs/bedrock-agentcore-config.json`** with endpoints and environments
2. **AWS profile** configured (default: `demo1`)
3. **Bedrock AgentCore Gateway access** permissions
4. **IAM roles** created for Bedrock AgentCore Gateway

### **AWS Permissions**
Scripts require permissions for:
- `bedrock-agentcore:*` (Bedrock AgentCore Gateway operations)
- `iam:PassRole` (for role assumption)
- AWS profile with Bedrock AgentCore API access

## 🗂️ **File Organization**

```
scripts/
├── README.md                # This file
├── create-gateway.py        # Create new gateway
├── create-target.py         # Create new target
├── delete-gateway.py        # Delete gateway
├── delete-target.py         # Delete target
├── get-gateway.py           # Get gateway details
├── get-target.py            # Get target details
├── list-gateways.py         # List all gateways
├── list-targets.py          # List all targets
├── update-gateway.py        # Update gateway
└── update-target.py         # Update target
```

---
