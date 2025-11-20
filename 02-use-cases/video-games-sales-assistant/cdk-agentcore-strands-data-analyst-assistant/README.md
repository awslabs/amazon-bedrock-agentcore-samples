# Back-End Deployment - Data Source and Configuration Management Deployment with CDK

Deploy the back-end infrastructure for a Data Analyst Assistant for Video Game Sales using **[AWS Cloud Development Kit (CDK)](https://aws.amazon.com/cdk/)**.

> [!NOTE]
> **Working Directory**: Make sure you are in the `cdk-agentcore-strands-data-analyst-assistant/` folder before starting this tutorial. All commands in this guide should be executed from this directory.

## Overview

This tutorial deploys the foundational AWS services required for the video game sales data analyst agent with the following key components:

- **IAM AgentCore Execution Role**: Comprehensive permissions for Amazon Bedrock AgentCore execution, including access to Bedrock models, RDS Data API, DynamoDB, and Secrets Manager
- **VPC with Public and Private Subnets**: Network isolation and security for database resources with NAT Gateway for outbound connectivity
- **Amazon Aurora Serverless v2 PostgreSQL**: Scalable database cluster storing video game sales data with RDS Data API integration and encryption
- **Amazon DynamoDB**: Single table for tracking SQL query results with pay-per-request billing
- **AWS Secrets Manager**: Secure storage for database credentials
- **Amazon S3**: Import bucket for loading data into Aurora PostgreSQL with lifecycle policies
- **VPC Gateway Endpoints**: Cost-effective access to S3 and DynamoDB services
- **SSM Parameter Store**: Configuration management for AgentCore runtime parameters

> [!IMPORTANT]
> Remember to clean up resources after testing to avoid unnecessary costs by following the clean-up steps provided.

## Prerequisites

Before you begin, ensure you have:

* AWS Account and appropriate IAM permissions for services deployment
* **Development Environment**:
  * Python 3.10 or later installed
  * **[AWS CDK Installed](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html)**

* Run this command to create a service-linked role for RDS:

```bash
aws iam create-service-linked-role --aws-service-name rds.amazonaws.com
```

## AWS Deployment

Navigate to the CDK project folder and install dependencies:

```bash
npm install
```

Deploy the infrastructure:

```bash
cdk deploy
```

Default Parameters:
- **ProjectId**: "agentcore-data-analyst-assistant" - Project identifier used for naming resources
- **DatabaseName**: "video_games_sales" - Name of the database

Deployed Resources:

- **VPC**: Public/private subnets, NAT Gateway, security groups, VPC endpoints
- **Aurora PostgreSQL Serverless v2**: Database cluster with RDS Data API
- **DynamoDB**: Table for SQL query results
- **S3**: Bucket for data imports with lifecycle policies
- **Secrets Manager**: Database credentials storage
- **IAM**: AgentCore execution role with Bedrock, RDS, DynamoDB permissions
- **SSM Parameter Store**: Configuration parameters
  - `/<projectId>/SECRET_ARN`: Database secret ARN
  - `/<projectId>/AURORA_RESOURCE_ARN`: Aurora cluster ARN
  - `/<projectId>/DATABASE_NAME`: Database name
  - `/<projectId>/QUESTION_ANSWERS_TABLE`: DynamoDB question answers table name
  - `/<projectId>/MAX_RESPONSE_SIZE_BYTES`: Maximum response size in bytes (1MB)
  - `/<projectId>/MEMORY_ID`: AgentCore Memory ID for the Agent

  These parameters are automatically retrieved by the Strands Agent to establish database connections and configure agent behavior.

> [!IMPORTANT] 
> Enhance AI safety and compliance by implementing **[Amazon Bedrock Guardrails](https://aws.amazon.com/bedrock/guardrails/)** for your AI applications with the seamless integration offered by **[Strands Agents SDK](https://strandsagents.com/latest/user-guide/safety-security/guardrails/)**.

## Load Sample Data into PostgreSQL Database

1. Install required Python dependencies:

``` bash
pip install boto3
```

2. Set up the required environment variables:

``` bash
# Set the stack name environment variable
export STACK_NAME=CdkAgentcoreStrandsDataAnalystAssistantStack

# Retrieve the output values and store them in environment variables
export SECRET_ARN=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='SecretARN'].OutputValue" --output text)
export DATA_SOURCE_BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='DataSourceBucketName'].OutputValue" --output text)
export AURORA_SERVERLESS_DB_CLUSTER_ARN=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='AuroraServerlessDBClusterARN'].OutputValue" --output text)
export AGENT_CORE_ROLE_EXECUTION=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='AgentCoreMyRoleARN'].OutputValue" --output text)
export MEMORY_ID_SSM_PARAMETER=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='MemoryIdSSMParameter'].OutputValue" --output text)
cat << EOF
STACK_NAME: ${STACK_NAME}
SECRET_ARN: ${SECRET_ARN}
DATA_SOURCE_BUCKET_NAME: ${DATA_SOURCE_BUCKET_NAME}
AURORA_SERVERLESS_DB_CLUSTER_ARN: ${AURORA_SERVERLESS_DB_CLUSTER_ARN}
AGENT_CORE_ROLE_EXECUTION: ${AGENT_CORE_ROLE_EXECUTION}
MEMORY_ID_SSM_PARAMETER: ${MEMORY_ID_SSM_PARAMETER}
EOF

```

3. Load sample data into PostgreSQL:

``` bash
python3 resources/create-sales-database.py
```

The script uses the **[video_games_sales_no_headers.csv](./resources/database/video_games_sales_no_headers.csv)** as the data source.

> [!NOTE]
> The data source provided contains information from [Video Game Sales](https://www.kaggle.com/datasets/asaniczka/video-game-sales-2024) which is made available under the [ODC Attribution License](https://opendatacommons.org/licenses/odbl/1-0/).

## Next Step

You can now proceed to the **[Agent Deployment - Strands Agent Infrastructure Deployment with AgentCore](../agentcore-strands-data-analyst-assistant/))**.

## Cleaning-up Resources (Optional)

To avoid unnecessary charges, delete the CDK stack:

``` bash
cdk destroy
```

## Thank You

## License

This project is licensed under the Apache-2.0 License.