# Device Management Module

This module implements the core functionality of the Device Management system, including the Lambda function that handles all MCP server tools, DynamoDB models, and testing utilities.

## Components

- `lambda_function.py`: Main Lambda handler that implements all MCP tools
- `dynamodb_models.py`: DynamoDB table definitions and initialization
- `synthetic_data.py`: Script to generate synthetic test data
- `test_lambda.py`: Script to test the Lambda function locally
- `deploy.sh`: Deployment script for the Lambda function
- `requirements.txt`: Python dependencies

## Setup

1. Create a `.env` file in this directory with the following variables:

```
# AWS configuration
AWS_REGION=us-west-2

# Lambda configuration
LAMBDA_FUNCTION_NAME=DeviceManagementLambda
LAMBDA_ROLE_NAME=DeviceManagementLambdaRole

# Agent Gateway IAM configuration
AGENT_GATEWAY_POLICY_NAME=AgentGatewayAccess
AGENT_GATEWAY_ROLE_NAME=AgentGatewayAccessRole
```

2. Install the required Python packages:

```bash
pip install -r requirements.txt
```

## Deployment

You can deploy the Lambda function using the provided deployment script:

```bash
chmod +x deploy.sh
./deploy.sh
```

The deployment script performs the following actions:
- Packages the Lambda function code with dependencies
- Creates an IAM role with necessary permissions (if it doesn't exist)
- Creates or updates the Lambda function
- Configures the function with appropriate memory and timeout settings

## DynamoDB Tables

The function uses the following DynamoDB tables in the configured AWS region:

- `Devices`: Device inventory and status
- `DeviceSettings`: Device configuration settings
- `WifiNetworks`: WiFi network configurations
- `Users`: User accounts and profiles
- `UserActivities`: User activity logs

## Generate Test Data

To populate the tables with synthetic test data:

```bash
python synthetic_data.py
```

## Test the Lambda Function

You can test the Lambda function locally using the provided test script:

```bash
python test_lambda.py
```

This script tests all available tools and verifies that they work correctly.

## IAM Permissions

The Lambda function requires the following IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:UpdateItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-west-2:*:table/Devices",
        "arn:aws:dynamodb:us-west-2:*:table/DeviceSettings",
        "arn:aws:dynamodb:us-west-2:*:table/WifiNetworks",
        "arn:aws:dynamodb:us-west-2:*:table/Users",
        "arn:aws:dynamodb:us-west-2:*:table/UserActivities",
        "arn:aws:dynamodb:us-west-2:*:table/UserActivities/index/ActivityTypeIndex"
      ]
    }
  ]
}
```

## Available MCP Tools

The Lambda function exposes the following MCP tools:

1. `list_devices`: Lists all devices in the system
2. `get_device_settings`: Retrieves settings for a specific device
3. `list_wifi_networks`: Lists WiFi networks for a specific device
4. `list_users`: Lists all users in the system
5. `query_user_activity`: Queries user activity within a time period
6. `update_wifi_ssid`: Updates the SSID for a WiFi network
7. `update_wifi_security`: Updates the security type for a WiFi network

## Integration with Other Modules

- **Gateway Module**: The Lambda function is the target for the gateway created in the gateway module.
- **Frontend Module**: The frontend communicates with this Lambda function through the gateway.
