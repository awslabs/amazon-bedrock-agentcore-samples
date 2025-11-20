# Java Google ADK Agent example for Amazon Bedrock AgentCore Runtime

This project implements the HTTP protocol contract for Amazon Bedrock AgentCore Runtime using [Java Spring Boot](https://spring.io/projects/spring-boot). It provides a foundation for integrating [Java Google's Agent Development Kit (ADK)](https://github.com/google/adk-java) with Amazon Bedrock AgentCore Runtime.

| Information         | Details                                                                      |
|---------------------|------------------------------------------------------------------------------|
| Agent type          | Synchronous                                                                  |
| Agentic Framework   | Java Google ADK                                                              |
| LLM model           | Gemini 2.0 Flash                                                             |
| Components          | AgentCore Runtime                                                            |
| Example complexity  | Easy                                                                         |

## Overview

Amazon Bedrock AgentCore Runtime provides a secure, serverless hosting environment for deploying AI agents. This implementation creates REST API endpoints that comply with the AgentCore HTTP protocol contract.

## Prerequisites

- **Java 17** or higher, [download](https://www.oracle.com/java/technologies/downloads/)
- **Maven 3.6+**, [download](https://maven.apache.org/download.cgi)
- **AWS account**: You need an active AWS account with appropriate permissions
  - [Create an AWS account](https://aws.amazon.com/account/)
  - [AWS Management Console access](https://aws.amazon.com/console/)
- **AWS CLI**: Install and configure AWS CLI with your credentials
  - [Install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  - [Configure AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)
- Google AI API key (for the Gemini model), [docs](https://ai.google.dev/gemini-api/docs/api-key)

## Project Structure

```bash
java_adk/
├── src/
│   ├── main/
│   │   ├── java/com/agentswithek/GoogleADKAgentCore/
│   │   │   ├── controllers/
│   │   │   │   └── AgentCoreRuntimeController.java    # REST endpoints
│   │   │   ├── entities/
│   │   │   │   ├── InvocationRequest.java             # Request DTO
│   │   │   │   ├── InvocationResponse.java            # Response DTO
│   │   │   │   └── PingResponse.java                  # Health check DTO
│   │   │   └── GoogleAdkAgentCoreApplication.java     # Main application
│   │   └── resources/
│   │       └── application.properties                  # Configuration
│   └── test/
├── Dockerfile                                          # ARM64 Docker build
├── pom.xml                                             # Maven dependencies
└── README.md                                           # This file
```

## Local Development & Testing

```bash
git clone https://github.com/awslabs/amazon-bedrock-agentcore-samples.git
cd 03-integrations/agentic-frameworks/java_adk
```

### Google API Key

> [!IMPORTANT]  
> Make sure to replace `<ValidAPIKey>` with valid API key from [Google](https://ai.google.dev/gemini-api/docs/api-key).

```bash
export GOOGLE_API_KEY="<ValidAPIKey>"
```

### Build and Run

```bash
# Run with Maven
mvn spring-boot:run
```

The application will start on `http://localhost:8080`

### Test the Endpoints

**Test /invocations:**

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -H "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: gfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmt" \
  -d '{"prompt": "Hello, how are you?"}'
```

**Test /ping:**

```bash
curl http://localhost:8080/ping
```

## Deploy to AgentCore Runtime Using AWS CloudFormation

### Step 1: Deploy CloudFormation Stack

> [!IMPORTANT]  
> Make sure to replace `<ValidAPIKey>` with valid API key from [Google](https://ai.google.dev/gemini-api/docs/api-key).

```bash
# Deploy the CloudFormation stack
aws cloudformation create-stack \
  --stack-name java-adk-agent \
  --template-body file://cloudformation/github-source.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters \
    ParameterKey=AgentName,ParameterValue=adkjavaagent \
    ParameterKey=GoogleApiKey,ParameterValue=<ValidAPIKey>

# Wait for stack creation to complete
aws cloudformation wait stack-create-complete \
  --stack-name java-adk-agent

# Get stack outputs
aws cloudformation describe-stacks \
  --stack-name java-adk-agent \
  --query "Stacks[0].Outputs" \
  --output table
```

### Step 2: Testing

Once your agent is deployed, you can test it using the integration tests.

### Step 1: Get Agent Runtime ARN from SSM Parameter Store

```bash
# Export the ARN directly (replace 'adkjavaagent' with your agent name)
export AGENT_RUNTIME_ARN=$(aws ssm get-parameter \
  --name "/hostagent/agentcore/adkjavaagent/runtime-arn" \
  --query "Parameter.Value" \
  --output text )

# Verify it's set
echo $AGENT_RUNTIME_ARN

export AWS_REGION="us-west-2"
```

### Step 2: Run Integration Tests

```bash
# Run all tests
mvn test -Dtest=AgentRuntimeInvokerTest
```

## Cleanup

To delete all resources created by the CloudFormation stack:

```bash
# Delete the CloudFormation stack
aws cloudformation delete-stack \
  --stack-name java-adk-agent 

# Wait for stack deletion to complete
aws cloudformation wait stack-delete-complete \
  --stack-name java-adk-agent 

# Verify deletion
aws cloudformation describe-stacks \
  --stack-name java-adk-agent | grep -q "does not exist" && echo "Stack successfully deleted"
```
