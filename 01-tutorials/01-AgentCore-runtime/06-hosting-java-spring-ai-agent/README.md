Hosting a Java Spring AI Agent
------------------------------

## Run Locally

1. [Create a Bedrock Bearer token](https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/api-keys/long-term/create)
2. Set the env var: `export AWS_BEARER_TOKEN_BEDROCK=YOUR_TOKEN`
3. Run the app: `./gradlew bootRun`
4. Test the agent:
    ```
    curl -X POST -d '{"question": "tell me a joke"}' -H 'Content-Type: application/json' http://localhost:8080/invocations
    ```

## Run on AgentCore Runtime

Note: To build the container image you need to be on a ARM64 machine. If you are on an AMD64 machine, you should build the container image in a Code Build process (using ARM64 build machines) or in an ARM64 virtual machine.

Prereqs:
- [Create ECR Repo](https://us-east-1.console.aws.amazon.com/ecr/private-registry/repositories/create?region=us-east-1)
- [Auth `docker` to ECR](https://docs.aws.amazon.com/AmazonECR/latest/userguide/registry_auth.html)

Create an push the image to ECR:
```
export ECR_REPO=<your account id>.dkr.ecr.us-east-1.amazonaws.com/<your repo path>

./gradlew bootBuildImage --imageName=$ECR_REPO

docker push $ECR_REPO:latest
```

Now create an AgentCore Runtime agent from the container image:

1. https://us-east-1.console.aws.amazon.com/bedrock-agentcore/agents/create
2. Select the image you just pushed and click "Host agent"
3. Use the Agent Sandbox to test the agent with this input:
    ```
    {"question": "tell me a joke"}
    ```
