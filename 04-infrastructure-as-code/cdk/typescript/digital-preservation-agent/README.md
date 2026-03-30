# Digital Preservation Agent (CDK TypeScript)

Deploy a digital preservation agent using Amazon Bedrock AgentCore with multiple file analysis tools running on ECS Fargate: [Apache Tika](https://tika.apache.org/), [Siegfried](https://www.itforarchivists.com/siegfried), [DROID](https://digital-preservation.github.io/droid/), and [MediaInfo](https://mediaarea.net/en/MediaInfo). An AgentCore Gateway exposes all tools via MCP, Lambda functions bridge tool calls to each service, and an AgentCore Runtime hosts a Strands agent that orchestrates analysis workflows.

## Architecture

```
User → AgentCore Runtime (Strands Agent, Claude 3 Haiku)
         ↓  MCP
       AgentCore Gateway
         ↓
       Lambda functions (tool bridges)
         ↓
       Internal ALB (path-based routing)
         ├── /tika*, /detect/*, /meta*  → ECS Fargate (Apache Tika :9998)
         ├── /identify/*               → ECS Fargate (Siegfried :5138)
         ├── /api/*                    → ECS Fargate (DROID :8080)
         └── /mediainfo/*             → ECS Fargate (MediaInfo :8081)
         ↓
       S3 Bucket (document uploads + reports)
```

## Prerequisites

- [Node.js 18+](https://nodejs.org/) and npm
- [Docker](https://docs.docker.com/get-docker/) (required for building container images)
- [AWS CDK v2](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html) (`npm install -g aws-cdk`)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured with appropriate credentials
- [Bedrock Foundation model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) — ensure Claude 3 Haiku is enabled in your target region

## Deployment

```bash
cd infrastructure
npm install
npx cdk bootstrap   # first time only
npx cdk deploy
```

> Use `npx cdk` to run the project-local CDK CLI. A globally installed CDK may be too old for the `aws-cdk-lib` version used here.

### Stack Outputs

| Output | Description |
|---|---|
| `RuntimeArn` | AgentCore Runtime ARN (use to invoke the agent) |
| `GatewayUrl` | AgentCore Gateway URL (MCP endpoint) |
| `GatewayId` | AgentCore Gateway ID |
| `AlbDns` | Internal ALB DNS name |
| `DocsBucketName` | S3 bucket for uploads and reports |

## Usage

1. Upload a file:
   ```bash
   aws s3 cp my-report.pdf s3://<DocsBucketName>/my-report.pdf
   ```

2. Invoke the agent:
   ```python
   import boto3, json
   client = boto3.client("bedrock-agentcore")
   response = client.invoke_agent_runtime(
       agentRuntimeArn="<RuntimeArn>",
       request={"prompt": "Identify the format of my-report.pdf using Siegfried and extract its text with Tika"},
   )
   print(json.dumps(response, indent=2, default=str))
   ```

## Available Tools

| Tool | Service | Description |
|---|---|---|
| `tika_process` | Tika | Fetch S3 file → extract text, metadata, or detect MIME type (handles archives directly) |
| `siegfried_identify` | Siegfried | Identify file format using PRONOM registry (requires extraction for archives) |
| `droid_profile` | DROID | Profile file format using DROID (requires extraction for archives) |
| `mediainfo_analyze` | MediaInfo | Analyze media file technical metadata (requires extraction for archives) |
| `extract_archive` | Lambda | Extract ZIP/TAR archives to S3 |
| `save_report_to_s3` | Lambda | Save analysis report as JSON to S3 |

## ALB Routing

| Path Pattern | Target | Port |
|---|---|---|
| `/tika*`, `/detect/*`, `/meta*` | Apache Tika | 9998 |
| `/identify/*` | Siegfried | 5138 |
| `/api/*` | DROID | 8080 |
| `/mediainfo/*` | MediaInfo | 8081 |

## Sample Prompts

- Identify the format of my-report.pdf using Siegfried
- Extract text from presentation.pptx
- Analyze the media metadata of video.mp4
- Run a full preservation analysis on archive.zip — extract it, then identify all files
- Profile document.docx with DROID and save the results as a report

## Project Structure

```
digital-preservation-agent/
├── agent/
│   ├── main.py                # Strands agent for AgentCore Runtime
│   ├── requirements.txt
│   └── Dockerfile
├── backend/
│   ├── tika_handler.py         # Tika tool bridge
│   ├── siegfried_handler.py   # Siegfried tool bridge
│   ├── droid_handler.py       # DROID tool bridge
│   ├── mediainfo_handler.py   # MediaInfo tool bridge
│   ├── extract_handler.py     # Archive extraction (S3 only)
│   └── s3_report_handler.py   # Report persistence (S3 only)
├── containers/
│   ├── droid/                 # DROID Docker image (eclipse-temurin:17-jre)
│   └── mediainfo/            # MediaInfo Docker image (alpine:3.20)
├── infrastructure/
│   ├── bin/app.ts
│   ├── lib/stacks/
│   │   └── digital-preservation-stack.ts
│   ├── config.json
│   ├── package.json
│   ├── tsconfig.json
│   └── cdk.json
├── .gitignore
└── README.md
```

## Configuration

Edit `infrastructure/config.json`:

| Key | Default | Description |
|---|---|---|
| `agentModelId` | `eu.anthropic.claude-3-5-haiku-20241022-v1:0` | Foundation model ([cross-region inference profile](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html)) |
| `tikaImageTag` | `3.2.3.0-full` | Apache Tika Docker image tag |
| `fargateMemoryMiB` | `2048` | Fargate task memory (shared across all services) |
| `fargateCpu` | `1024` | Fargate task CPU |
| `desiredCount` | `1` | Number of Fargate tasks per service |

> Siegfried uses the pre-built `ghcr.io/keeps/siegfried:v1.10.1` image directly (no Dockerfile). DROID and MediaInfo have custom Dockerfiles in `containers/` and are built with `--platform linux/amd64` for ECS Fargate compatibility.

> The default `agentModelId` uses the `eu.` cross-region inference prefix, which routes requests to EU-based Bedrock endpoints. If deploying to a non-EU region, change this to a region-appropriate prefix (e.g., `us.anthropic.claude-3-5-haiku-20241022-v1:0`) or use the base model ID `anthropic.claude-3-5-haiku-20241022-v1:0`. See [cross-region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html) for available prefixes.

## Clean Up

```bash
cd infrastructure
npx cdk destroy
```
