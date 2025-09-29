

# SageMaker Managed MLflow Observability for Strands Agents on Amazon Bedrock AgentCore
This example provides step-by-step instructions, sample code, and deployment jupyter notebook to operationalize Strands Agents in Amazon Bedrock's AgentCore Runtime with Amazon SageMaker managed MLflow for observability. With this you will be able to observe Real-time agent interactions and tool invocations are recorded in MLflow for auditing and analytics of your agentic applications deployed in Amazon Bedrock AgentCore Runtime.

![image](./images/sagemaker-mlflow-agentCore.png)

## Features
- Deployment of tool-augmented financial analysis agents via Amazon Bedrock AgentCore Runtime
- AgentCore Runtime integration with SageMaker managed MLflow
- Automated tracing and experiment tracking using SageMaker managed MLflow (MLflow 3.4.0+ required). Sample output shown below.
- Example: Streaming real-time financial agent responses for investment advice

![image](./images/sagemaker-mlflow-output.png)

## Sample Code Repository [sample-aiops-on-amazon-sagemakerai](https://github.com/aws-samples/sample-aiops-on-amazon-sagemakerai/tree/main/examples/sagemaker-mlflow-agentcore-runtime)
You can find the code samples and the accompanying jupyter notebook in the respository: [sample-aiops-on-amazon-sagemakerai](https://github.com/aws-samples/sample-aiops-on-amazon-sagemakerai/tree/main/examples/sagemaker-mlflow-agentcore-runtime)

# License
This library is licensed under the MIT-0 License. See the LICENSE file.
---

*This solution demonstrates modern automation architecture patterns for AI/ML workloads on AWS, showcasing how to build scalable Agentic workloads.*