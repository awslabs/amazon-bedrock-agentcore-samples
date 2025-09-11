# MCP Client Authentication Examples

## Overview

This section provides complete examples of how to connect to MCP servers hosted on Amazon Bedrock AgentCore Runtime using standard MCP SDKs with different authentication methods.

These examples demonstrate authentication patterns that can be used to build applications that consume MCP tools and services hosted on AgentCore.

## Available SDKs and Examples

### Python SDK Examples

📁 **[01-python-sdk/](01-python-sdk/)**

Complete Python implementation showing:
- **OAuth 2.0 Authentication** (4 different modes)
- **AWS SigV4 Authentication** (IAM-based)
- Environment-based configuration
- Interactive and automated authentication flows
- Comprehensive error handling

**Key Features:**
- Standalone applications that work independently
- Support for AWS Cognito and generic OAuth 2.0 providers
- Multiple authentication modes for different use cases
- Comprehensive setup documentation

## Authentication Methods Comparison

| Method | Best For | Setup Complexity | User Interaction |
|--------|----------|------------------|------------------|
| **OAuth 2.0** | User applications, web apps | Medium | Yes (except M2M) |
| **AWS SigV4** | Service-to-service, automation | Simple | No |

## When to Use Each Method

### OAuth 2.0 Authentication
- **Interactive applications** requiring user login
- **Web applications** with user sessions
- **Development and testing** with browser-based flows
- **Machine-to-machine** communication with client credentials

### AWS SigV4 Authentication  
- **Backend services** and microservices
- **Automated systems** and scheduled jobs
- **AWS-native applications** using IAM roles
- **Simple authentication** without OAuth complexity

## Getting Started

1. **Choose your SDK**: Currently Python SDK is available
2. **Select authentication method**: OAuth 2.0 or SigV4 based on your use case
3. **Follow the setup guide** in the respective SDK directory
4. **Configure your environment** with the required credentials
5. **Run the example clients** to test connectivity

## Prerequisites

### For OAuth Authentication
- AWS Cognito User Pool (or other OAuth 2.0 provider)
- Properly configured App Client
- Test user account (for interactive flows)

### For SigV4 Authentication
- AWS IAM credentials (access keys, profiles, or roles)
- Proper IAM permissions for AgentCore access
- AgentCore Runtime ARN

## Additional Resources

- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [AWS Cognito Developer Guide](https://docs.aws.amazon.com/cognito/latest/developerguide/)
- [AWS IAM User Guide](https://docs.aws.amazon.com/IAM/latest/UserGuide/)