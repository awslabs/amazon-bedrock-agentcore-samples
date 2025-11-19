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

## Before Deploy Infrastructure - Video Ingestion

### Connecting the agent to a camera

Allowing the agent to query your cameras require the agent to have access to an API to retrieve images and videos. In this sample we use [Amazon Kinesis Video Streams](https://aws.amazon.com/kinesis/video-streams/), KVS, to securely stream video from connected devices to AWS. To get started with KVS you need a camera and a piece of hardware that connect to the camera, and send the stream to KVS. As an example, you can use a Raspberry Pi, that's either connected to a Pi camera module, or to an RTSP camera on the local network. To send the stream to AWS, you can use the AWS SDK, or the [KVS producer client](https://docs.aws.amazon.com/kinesisvideostreams/latest/dg/producer-sdk.html) which comes with a few convenience methods to help you get started quickly. Once the stream is in KVS, you can use the AWS API to get the current frame or generate videos etc.

#### Ingesting a camera stream

After you have set your camera to ingest video information, you should go to [camera_service.py](agent/services/camera_service.py) file and change following block to be your camera:

```python
CAMERA_STREAMS = {
    "backyard": {
        "stream_name": "hassela_camera_01",
    },
}
```

#### Accessing historical footage

There are many strategies for allowing the agent to understand what the camera has observed in the past. In this sample there's a separate process that continuously queries the KVS API, getting frames with a set interval. These frames are then analysed using an LLM, and a structured log is stored S3. These logs are then accessed with SQL, using Athena, to enable the agent to on-deman retreive a log of what has transpired during specific time ranges.

You will realize that this table was created into Athena using following schema:

```sql
CREATE EXTERNAL TABLE `cameras`(
  `timestamp_string` string COMMENT 'from deserializer', 
  `stream_name` string COMMENT 'from deserializer', 
  `description` string COMMENT 'from deserializer')
PARTITIONED BY ( 
  `ingest_date` string)
ROW FORMAT SERDE 
  'org.openx.data.jsonserde.JsonSerDe' 
STORED AS INPUTFORMAT 
  'org.apache.hadoop.mapred.TextInputFormat' 
OUTPUTFORMAT 
  'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
TBLPROPERTIES (
  'projection.enabled'='true', 
  'projection.ingest_date.format'='yyyy-MM-dd-HH', 
  'projection.ingest_date.interval'='1', 
  'projection.ingest_date.interval.unit'='HOURS', 
  'projection.ingest_date.range'='2024-09-01-00,NOW', 
  'projection.ingest_date.type'='date');
```

Then, you should create a local file into [tf](tf/) folder with name `terraform.tfvars`. This file should contain following entries:

```yaml
# Local configuration
camera_role_arn         = "<your-kvs-ARN>"
camera_region           = "<region>"
smart_home_bucket_name  = "<Bucket where your KVS is streaming>"
```

Finally, double check [variables.tf](tf/variables.tf) file to fill `athena_database` and `athena_workgroup` with your environment information.

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

## Next Steps

After deploying the backend infrastructure, proceed to deploy the frontend application:

👉 **[Deploy the Smart Home Assistant UI](../amplify-smart-home/)**

The frontend provides the conversational interface for users to interact with your AI-powered smart home assistant.

## Thanks

Thank you for following this guide! We hope this helps you build amazing AI-powered agent experiences.
