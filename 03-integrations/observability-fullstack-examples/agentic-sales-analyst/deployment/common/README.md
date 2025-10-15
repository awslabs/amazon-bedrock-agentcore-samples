# Common Infrastructure

These CloudFormation templates are shared by both ECS and EKS deployments.

## Templates

### 01-network.yaml
Creates VPC and networking infrastructure:
- VPC (10.0.0.0/16)
- 2 Public Subnets (across 2 AZs)
- Internet Gateway
- Route Tables

**Exports**:
- `{ProjectName}-vpc-id`
- `{ProjectName}-subnet-1-id`
- `{ProjectName}-subnet-2-id`

### 02-iam.yaml
Creates IAM roles for ECS/EKS tasks:
- Task Execution Role (pull images, write logs)
- Task Role (Bedrock, AgentCore Memory, CloudWatch, X-Ray)

**Exports**:
- `{ProjectName}-execution-role-arn`
- `{ProjectName}-task-role-arn`

### 03-ecr.yaml
Creates ECR repository for container images:
- Image scanning enabled
- Lifecycle policy (keep last 10 images)

**Exports**:
- `{ProjectName}-ecr-uri`

## Deployment Order

These templates must be deployed before ECS or EKS specific resources:

1. Network (01-network.yaml)
2. IAM (02-iam.yaml)
3. ECR (03-ecr.yaml)

The main `deploy-infrastructure.sh` script handles this automatically.

## Manual Deployment

```bash
cd deployment

# Deploy network
aws cloudformation create-stack \
  --stack-name agentic-sales-analyst-network \
  --template-body file://common/01-network.yaml \
  --parameters ParameterKey=ProjectName,ParameterValue=agentic-sales-analyst

# Deploy IAM
aws cloudformation create-stack \
  --stack-name agentic-sales-analyst-iam \
  --template-body file://common/02-iam.yaml \
  --parameters ParameterKey=ProjectName,ParameterValue=agentic-sales-analyst \
  --capabilities CAPABILITY_NAMED_IAM

# Deploy ECR
aws cloudformation create-stack \
  --stack-name agentic-sales-analyst-ecr \
  --template-body file://common/03-ecr.yaml \
  --parameters ParameterKey=ProjectName,ParameterValue=agentic-sales-analyst
```

## Cleanup

Delete in reverse order:
```bash
aws cloudformation delete-stack --stack-name agentic-sales-analyst-ecr
aws cloudformation delete-stack --stack-name agentic-sales-analyst-iam
aws cloudformation delete-stack --stack-name agentic-sales-analyst-network
```

Or use the cleanup script:
```bash
cd deployment
./cleanup-infrastructure.sh
```
