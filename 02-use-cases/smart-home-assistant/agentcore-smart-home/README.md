# Smart Home Agent and Backend Deployment Guide

A Python-based backend infrastructure that powers the Smart Home Assistant using **[Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)** for AI-powered smart home management.

> [!NOTE]
> **Working Directory**: Make sure you are in the `agentcore-smart-home/` folder before starting this tutorial. All commands in this guide should be executed from this directory.

## Overview

This backend solution provides the AI agent infrastructure and data processing capabilities for smart home management.

**Services Deployed by This Guide:**
- **Amazon Bedrock AgentCore**: AI agent runtime with MCP servers
- **Amazon DynamoDB**: Media assets and session storage
- **Amazon Kinesis Video Streams**: Camera stream ingestion
- **Amazon Athena**: SQL queries for historical footage analysis
- **AWS Lambda**: Serverless compute for data processing
- **Terraform**: Infrastructure as Code deployment

**How It Works:**
1. Camera streams are ingested via Amazon Kinesis Video Streams
2. Frames are continuously extracted and analyzed using LLMs
3. Structured logs are stored in S3 and queried via Athena
4. MCP servers provide text-to-SQL capabilities for the agent
5. AgentCore runtime processes natural language queries
6. Media assets are stored in DynamoDB for frontend retrieval

> [!IMPORTANT]
> This sample application is for demonstration purposes only and is not production-ready. Please validate the code against your organization's security best practices.

## Prerequisites

- Python 3.9 or higher
- Terraform installed
- AWS CLI configured with appropriate permissions
- Camera hardware (e.g., Raspberry Pi with camera module or RTSP camera)

## Setup

Create virtual environment and install dependencies:

```bash
python -m venv .env
source .env/bin/activate
pip install -r requirements.txt
```

### Deploy Infrastructure

Deploy AWS infrastructure using Terraform:

```bash
terraform -chdir=tf init
terraform -chdir=tf plan
terraform -chdir=tf apply --auto-approve
```

Or from the tf directory:

```bash
cd tf
terraform init
terraform plan
terraform apply --auto-approve
```

### Running & Testing MCP Servers

#### Start MCP Servers

Terminal 1 (Sync server - port 8000):

```bash
python agent/text_to_sql.py
```

Terminal 2 (Async server - port 8001):

```bash
python agent/text_to_sql_async.py
```

### Connecting the agent to a camera

#### Ingesting a camera stream

Allowing the agent to query your cameras require the agent to have access to an API to retrieve images and videos. In this sample we use [Amazon Kinesis Video Streams](https://aws.amazon.com/kinesis/video-streams/), KVS, to securely stream video from connected devices to AWS. To get started with KVS you need a camera and a piece of hardware that connect to the camera, and send the stream to KVS. As an example, you can use a Raspberry Pi, that's either connected to a Pi camera module, or to an RTSP camera on the local network. To send the stream to AWS, you can use the AWS SDK, or the [KVS producer client](https://docs.aws.amazon.com/kinesisvideostreams/latest/dg/producer-sdk.html) which comes with a few convenience methods to help you get started quickly. Once the stream is in KVS, you can use the AWS API to get the current frame or generate videos etc.

#### Accessing historical footage

There are many strategies for allowing the agent to understand what the camera has observed in the past. In this sample there's a separate process that continuously queries the KVS API, getting frames with a set interval. These frames are then analysed using an LLM, and a structured log is stored S3. These logs are then accessed with SQL, using Athena, to enable the agent to on-deman retreive a log of what has transpired during specific time ranges.

## Next Steps

After deploying the backend infrastructure, proceed to deploy the frontend application:

👉 **[Deploy the Smart Home Assistant UI](../amplify-smart-home/)**

The frontend provides the conversational interface for users to interact with your AI-powered smart home assistant.

## License

This project is licensed under the Apache-2.0 License.

## Thanks

Thank you for following this guide! We hope this helps you build amazing AI-powered agent experiences.
