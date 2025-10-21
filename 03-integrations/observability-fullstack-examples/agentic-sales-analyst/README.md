# Agentic Sales Analyst

An agentic sales analyst that combines data from a sales database, along with real-time web research to provide complete market context for business decisions. The agent is built with the Strands Agent SDK and deployed to ECS (support for EKS coming soon), uses AgentCore Memory for conversational context and AgentCore Observability for insights into agent performance. It uses the Claude Sonnet v3 Model for its reasoning capabilities.

## Features

- 🤖 **Agentic AI** - Uses Strands SDK with Claude 3 Sonnet
- 🗄️ **Database Integration** - PostgreSQL with sample sales data
- 🌐 **Web Search** - Brave Search API for market intelligence
- 💾 **Conversation Memory** - Amazon Bedrock AgentCore Memory
- 📊 **Observability** - Amazon Bedrock AgentCore Observability
- 🎨 **Modern UI** - React frontend with streaming responses

## Architecture

### Local Development
```
Docker Compose (3 containers):
├─ PostgreSQL (port 5432) - Sample sales data
├─ Backend (port 8080) - Python Flask + Strands SDK
└─ Frontend (port 3000) - React app
```

### AWS Deployment

**ECS**
<!-- TODO: Add ECS architecture diagram -->

**EKS (Work in Progress)**
<!-- TODO: Add EKS architecture diagram -->

## Quick Start

### Local Development

```bash
# 1. Clone repository
git clone <repo-url>
cd agentic-sales-analyst

# 2. Add IAM permissions (required for Bedrock and AgentCore Memory)
aws iam put-user-policy \
  --user-name YOUR_AWS_USERNAME \
  --policy-name BedrockLocalDev \
  --policy-document file://local-dev-policy.json

# 3. Set environment variables
export BRAVE_SEARCH_API_KEY=your-api-key
export AWS_REGION=ap-southeast-2

# 4. Start all services (uses your ~/.aws credentials)
docker-compose -f docker-compose.local.yml up

# 5. Access application
open http://localhost:3000
```

### AWS Deployment

#### AWS Infrastructure
```bash
cd deployment
./deploy-infrastructure.sh
```

#### ECS
```bash
cd deployment/ecs
./deploy-ecs.sh
```

#### EKS (Work in Progress)
```bash
# Note: EKS deployment is still under development
cd deployment/eks
./deploy-k8s.sh
```

### Cleanup

**Remove ECS/EKS deployment (keeps shared infrastructure)**
```bash
# ECS
cd deployment/ecs
./cleanup-ecs.sh

# EKS (WIP)
cd deployment/eks
./cleanup-k8s.sh
```

**Remove all infrastructure (including VPC, IAM, ECR)**
```bash
cd deployment
./cleanup-infrastructure.sh
```

**Note:** Run deployment-specific cleanup first, then infrastructure cleanup to avoid dependency issues.

## Project Structure

```
.
├── client/                      # React frontend
│   ├── src/
│   │   ├── App.tsx             # Main chat interface
│   │   └── index.css           # Styles
│   ├── Dockerfile              # Frontend container
│   └── package.json
├── deployment/                  # AWS deployment files
│   ├── deploy-infrastructure.sh # Shared infrastructure deployment
│   ├── cleanup-infrastructure.sh # Shared infrastructure cleanup
│   ├── common/                 # Shared CloudFormation templates
│   │   ├── 01-network.yaml    # VPC, subnets, IGW
│   │   ├── 02-iam.yaml        # IAM roles and policies
│   │   └── 03-ecr.yaml        # ECR repository
│   ├── ecs/                    # ECS-specific files
│   │   ├── cluster.yaml       # ECS cluster and ALB
│   │   ├── service.yaml       # ECS service (3 containers)
│   │   ├── deploy-ecs.sh      # ECS deployment script
│   │   ├── cleanup-ecs.sh     # ECS cleanup script
│   │   └── README.md          # ECS documentation
│   └── eks/                    # EKS-specific files (WIP)
│       ├── cluster.yaml       # EKS cluster
│       ├── k8s-deployment.yaml # Kubernetes manifest
│       ├── deploy-k8s.sh      # EKS deployment script
│       ├── cleanup-k8s.sh     # EKS cleanup script
│       └── README.md          # EKS documentation
├── strands_agentcore_runtime.py # Main Python runtime
├── Dockerfile                   # Backend container
├── Dockerfile.postgres          # PostgreSQL with data
├── docker-compose.local.yml     # Local development

├── create_and_load_sales_data.sql # Database schema
├── sales_data_sample_utf8.csv   # Sample data
└── requirements.txt             # Python dependencies
```

## Technology Stack

### Backend
- **Python 3.11** - Runtime
- **Flask** - Web framework
- **Strands SDK** - Agentic AI framework
- **psycopg2** - PostgreSQL driver
- **boto3** - AWS SDK
- **ADOT** - Observability

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Node 18** - Build tooling

### Infrastructure
- **AWS Fargate** - Serverless containers (ECS)
- **Amazon EFS** - File storage (ECS)
- **Application Load Balancer** - Traffic routing
- **Amazon ECR** - Container registry
- **CloudWatch** - Logging and metrics
- **AgentCore** - Observability

### AI/ML
- **Amazon Bedrock** - Claude 3 Sonnet
- **Bedrock AgentCore Memory** - Conversation history
- **Brave Search API** - Web search

## Configuration

### Required Environment Variables

```bash
# AWS Configuration
AWS_REGION=ap-southeast-2
AWS_ACCOUNT_ID=123456789012

# API Keys
BRAVE_SEARCH_API_KEY=your-brave-api-key

# Database (auto-configured in containers)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sales_db
```

## Development

### Prerequisites

**Required:**
- Docker and Docker Compose
- AWS CLI configured with credentials
- Brave Search API key (get one at https://brave.com/search/api/)
- Node.js 18+ (for local frontend development)
- Python 3.11+ (for local backend development)

**IAM Permissions:**

For local development, your AWS user needs Bedrock and AgentCore Memory permissions:
```bash
aws iam put-user-policy \
  --user-name YOUR_AWS_USERNAME \
  --policy-name BedrockLocalDev \
  --policy-document file://local-dev-policy.json
```

### Known Vulnerabilities

The frontend has known vulnerabilities in build-time dependencies (react-scripts 5.0.1):
- `nth-check`, `postcss`, `webpack-dev-server` - Used during development and build
- These are inherited from Create React App, which is no longer actively maintained
- Vulnerabilities affect the build process only, not the production bundle
- Production bundle is scanned and minified, removing vulnerable code paths
- Mitigation: Only run `npm start` and `npm build` in trusted environments


