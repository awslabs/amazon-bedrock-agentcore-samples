# Gateway Module

This module handles the creation and configuration of the Amazon Bedrock Gateway and Gateway Target for the Device Management MCP server.

## Components

- `cognito_oauth_setup.py`: Script to set up Cognito OAuth and automatically update .env with credentials
- `create_gateway.py`: Script to create a gateway in Amazon Bedrock with Cognito authentication
- `device-management-target.py`: Script to create a gateway target that connects to the Lambda function

## Setup

1. Create a `.env` file in this directory with the following variables:

```
# AWS and endpoint configuration
AWS_REGION=us-west-2
ENDPOINT_URL=https://bedrock-agentcore-control.us-west-2.amazonaws.com

# Lambda configuration (from device-management module)
LAMBDA_ARN=arn:aws:lambda:us-west-2:your-account-id:function:DeviceManagementLambda

# Target configuration
GATEWAY_IDENTIFIER=your-gateway-identifier
TARGET_NAME=device-management-target
TARGET_DESCRIPTION=List, Update device management activities

# Gateway creation configuration
COGNITO_USERPOOL_ID=your-cognito-userpool-id
COGNITO_APP_CLIENT_ID=your-cognito-app-client-id
GATEWAY_NAME=Device-Management-Gateway
ROLE_ARN=arn:aws:iam::your-account-id:role/YourGatewayRole
GATEWAY_DESCRIPTION=Device Management Gateway
```

## Usage

### Setup Cognito OAuth (First Time)

Before creating the gateway, set up Cognito OAuth configuration:

```bash
python cognito_oauth_setup.py
```

This will:
- Create a Cognito OAuth authorizer
- Automatically update your `.env` file with:
  - `COGNITO_USERPOOL_ID`
  - `COGNITO_CLIENT_ID` 
  - `COGNITO_CLIENT_SECRET`
  - `COGNITO_DOMAIN`

### Create Gateway

```bash
python create_gateway.py
```

This will create a new gateway in Amazon Bedrock and output the Gateway ID.

### Create Gateway Target

After creating the gateway and deploying the Lambda function (from the device-management module), run:

```bash
python device-management-target.py
```

This will create a gateway target that connects to the Lambda function and configure the tool schema.

### Setup Gateway Observability

After creating the gateway, enable observability logging:

```bash
python gateway_observability.py
```

This will:
- Create a CloudWatch log group for gateway logs
- Set up log delivery from the gateway to CloudWatch
- Enable monitoring of gateway operations

**Note**: Ensure your `.env` file contains `GATEWAY_ARN` and `GATEWAY_ID` before running this script.

## IAM Permissions

The IAM role used for gateway creation should have the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "iam:PassRole",
                "bedrock-agentcore:*"
            ],
            "Resource": "*"
        }
    ]
}
```

## Integration with Other Modules

- **Device Management Module**: The gateway target connects to the Lambda function defined in the device-management module.
- **Frontend Module**: The frontend will use the gateway URL to communicate with the MCP server.
