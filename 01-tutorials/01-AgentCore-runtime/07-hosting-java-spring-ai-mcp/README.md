# Hosting Java Spring AI MCP Servers

## Overview

In this tutorial we will learn how to host a Java Spring AI MCP server using Amazon Bedrock AgentCore Runtime.

### Tutorial Details

| Information         | Details                                                   |
|:--------------------|:----------------------------------------------------------|
| Tutorial type       | Hosting Tools                                             |
| Tool type           | MCP server                                                |
| Tutorial components | Hosting a Java Spring AI MCP server on AgentCore Runtime. |
| Tutorial vertical   | Cross-vertical                                            |
| Example complexity  | Easy                                                      |
| SDK used            | Java Spring AI                                            |

### Tutorial Architecture



## Run Locally

1. Run the app: `./gradlew bootRun`
1. Test the MCP server with [MCP Inspector](https://github.com/modelcontextprotocol/inspector)

## Run on AgentCore Runtime

Note: To build the container image you need to be on a ARM64 machine. If you are on an AMD64 machine, you should build the container image in a Code Build process (using ARM64 build machines) or in an ARM64 virtual machine.

Prereqs:
- AWS CLI installed and authenticated
- Docker installed
- [Create ECR Repo](https://us-east-1.console.aws.amazon.com/ecr/private-registry/repositories/create?region=us-east-1)
- [Auth `docker` to ECR](https://docs.aws.amazon.com/AmazonECR/latest/userguide/registry_auth.html)
  Create and push the image to ECR:
```
export ECR_REPO=<your account id>.dkr.ecr.us-east-1.amazonaws.com/<your repo path>

./gradlew bootBuildImage --imageName=$ECR_REPO

docker push $ECR_REPO
```

Now create an AgentCore Runtime agent from the container image:
1. https://us-east-1.console.aws.amazon.com/bedrock-agentcore/agents/create
2. Select the image you just pushed, in **Inbound Auth** select MCP and **Use IAM permissions**, click "Host agent"
3. Once the agent has been created, use the Agent Sandbox to test the agent with this input:
    ```
    TODO
    ```
