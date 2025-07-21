# Command Line Arguments Reference

This document describes all command line arguments available for the AgentCore Gateway Management Tool.

## Usage

```bash
python main.py [-h] [--region REGION] [--endpoint-url ENDPOINT_URL] --role-arn ROLE_ARN --discovery-url DISCOVERY_URL 
               [--allowed-audience ALLOWED_AUDIENCE] [--allowed-clients ALLOWED_CLIENTS] 
               [--description-for-gateway DESCRIPTION] [--description-for-target DESCRIPTION] 
               [--search-type SEARCH_TYPE] [--protocol-version PROTOCOL_VERSION] 
               [--create-s3-target] [--s3-uri S3_URI] [--create-inline-target] 
               [--openapi-schema-file OPENAPI_SCHEMA_FILE] [--provider-arn PROVIDER_ARN] 
               [--save-gateway-url] [--delete-gateway-if-exists] [--output-json]
               gateway_name
```

## Required Arguments

### `gateway_name`
- **Type**: String
- **Description**: Name for the AgentCore Gateway

## AWS Configuration

### `--region`
- **Type**: String
- **Default**: us-east-1
- **Description**: AWS region

### `--endpoint-url`
- **Type**: String
- **Default**: https://bedrock-agentcore-control.us-east-1.amazonaws.com
- **Description**: Amazon Bedrock AgentCore Control endpoint URL

### `--role-arn`
- **Type**: String
- **Required**: Yes
- **Description**: IAM Role ARN with gateway permissions

## Authorization Configuration

### `--discovery-url`
- **Type**: String
- **Required**: Yes
- **Description**: JWT discovery URL for authorization

### `--allowed-audience`
- **Type**: String
- **Default**: MCPGateway
- **Description**: Allowed JWT audience (for Auth0/Okta)

### `--allowed-clients`
- **Type**: String (comma-separated)
- **Description**: Allowed JWT client IDs (for Cognito)

## Gateway Configuration

### `--description-for-gateway`
- **Type**: String
- **Default**: "AgentCore Gateway created via SDK"
- **Description**: Gateway description

### `--description-for-target`
- **Type**: String (can be specified multiple times)
- **Default**: "S3 target for OpenAPI schema"
- **Description**: Target description (can be specified multiple times for multiple targets)

### `--search-type`
- **Type**: String
- **Default**: SEMANTIC
- **Description**: MCP search type

### `--protocol-version`
- **Type**: String
- **Default**: 2025-03-26
- **Description**: MCP protocol version

## Target Configuration

### `--create-s3-target`
- **Type**: Flag
- **Description**: Create an S3 OpenAPI target

### `--s3-uri`
- **Type**: String (can be specified multiple times)
- **Description**: S3 URI for OpenAPI schema (can be specified multiple times to create multiple targets)

### `--create-inline-target`
- **Type**: Flag
- **Description**: Create an inline OpenAPI target

### `--openapi-schema-file`
- **Type**: String
- **Description**: File containing OpenAPI schema for inline target

### `--provider-arn`
- **Type**: String
- **Description**: OAuth credential provider ARN for targets

## Output Options

### `--save-gateway-url`
- **Type**: Flag
- **Description**: Save gateway URL to .gateway_uri file

### `--delete-gateway-if-exists`
- **Type**: Flag
- **Description**: Delete gateway if it already exists before creating new one

### `--output-json`
- **Type**: Flag
- **Description**: Output responses in JSON format

## Examples

### Create Gateway for Cognito

```bash
python main.py "CognitoGateway" \
    --role-arn "arn:aws:iam::123456789012:role/TestRole" \
    --discovery-url "https://cognito-idp.us-west-2.amazonaws.com/YourUserPoolId/.well-known/openid-configuration" \
    --allowed-clients "your-client-id"
```

### Create Gateway for Okta

```bash
python main.py "OktaGateway" \
    --role-arn "arn:aws:iam::123456789012:role/TestRole" \
    --discovery-url "https://dev-xxxxx.okta.com/oauth2/default/.well-known/openid-configuration" \
    --allowed-audience "gateway123"
```

### Create Gateway for Auth0

```bash
python main.py "Auth0Gateway" \
    --role-arn "arn:aws:iam::123456789012:role/TestRole" \
    --discovery-url "https://dev-xxxxx.us.auth0.com/.well-known/openid-configuration" \
    --allowed-audience "gateway123"
```

### Full Example with S3 Target

```bash
python main.py "ProductionGateway" \
    --region "us-east-1" \
    --role-arn "arn:aws:iam::123456789012:role/GatewayRole" \
    --discovery-url "https://cognito-idp.us-west-2.amazonaws.com/us-west-2_xxxxx/.well-known/openid-configuration" \
    --allowed-audience "MCPGateway" \
    --description-for-gateway "Production Gateway for API Integration" \
    --create-s3-target \
    --s3-uri "s3://my-bucket/openapi-spec.yaml" \
    --provider-arn "arn:aws:bedrock-agentcore:us-east-1:123456789012:token-vault/default/oauth2credentialprovider/Cognito" \
    --save-gateway-url \
    --output-json
```

### Create Gateway with Inline OpenAPI Target

```bash
python main.py "TestGateway" \
    --role-arn "arn:aws:iam::123456789012:role/GatewayRole" \
    --discovery-url "https://your-domain.auth0.com/.well-known/openid-configuration" \
    --create-inline-target \
    --openapi-schema-file "./schemas/hello.yaml" \
    --provider-arn "arn:aws:bedrock-agentcore:us-east-1:123456789012:token-vault/default/oauth2credentialprovider/Auth0"
```

### Create Gateway with Multiple S3 Targets

```bash
python main.py "MultiTargetGateway" \
    --role-arn "arn:aws:iam::123456789012:role/GatewayRole" \
    --discovery-url "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_xxxxx/.well-known/openid-configuration" \
    --allowed-clients "client-id-1,client-id-2" \
    --create-s3-target \
    --s3-uri "s3://my-bucket/api1.yaml" \
    --s3-uri "s3://my-bucket/api2.yaml" \
    --s3-uri "s3://my-bucket/api3.yaml" \
    --description-for-target "First API schema" \
    --description-for-target "Second API schema" \
    --description-for-target "Third API schema" \
    --provider-arn "arn:aws:bedrock-agentcore:us-east-1:123456789012:token-vault/default/oauth2credentialprovider/Cognito" \
    --save-gateway-url
```