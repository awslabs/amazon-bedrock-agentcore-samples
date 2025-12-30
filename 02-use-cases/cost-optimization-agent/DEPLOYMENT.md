# Cost Optimization Agent - Deployment Guide

This document contains detailed deployment instructions, monitoring, troubleshooting, and operational guidance for the Cost Optimization Agent.

## Detailed Installation & Deployment

### Prerequisites
- Python 3.10+
- AWS CLI configured with appropriate credentials
- Docker or Podman installed and running
- Access to Amazon Bedrock AgentCore
- AWS Cost Explorer enabled in your account

### Installation Steps

1. **Install uv** (if not already installed)
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

2. **Install Dependencies**
```bash
uv sync
```

3. **Deploy the Agent** (One Command!)
```bash
# Simple deployment
uv run python deploy.py

# Custom configuration (optional)
uv run python deploy.py \
  --agent-name "my-cost-agent" \
  --region "us-west-2" \
  --role-name "MyCustomRole"
```

**Available Options:**
- `--agent-name`: Name for the agent (default: cost_optimization_agent)
- `--role-name`: IAM role name (default: CostOptimizationAgentRole)
- `--region`: AWS region (default: us-east-1)
- `--skip-checks`: Skip prerequisite validation

4. **Test the Agent**
```bash
uv run python test/test_agent.py
```

## Usage Examples

### Cost Analysis
```
"What are my top 5 most expensive services this month?"
"Show me cost trends for the last 3 months"
"Which region is costing me the most?"
"Analyze my EC2 spending patterns"
```

### Anomaly Detection
```
"Are there any unusual cost spikes today?"
"What caused the increase in my S3 costs?"
"Show me services with abnormal spending"
```

### Optimization Recommendations
```
"How can I reduce my Lambda costs?"
"What Savings Plans should I consider?"
"Identify underutilized resources"
"Recommend model selection for my AI workloads"
```

### Budget Management
```
"How much of my monthly budget have I used?"
"Forecast my spending for next month"
"Set up alerts for when I reach 80% of budget"
"Show me budget vs actual for each team"
```

### Token Usage Optimization
```
"Analyze my Amazon Bedrock token usage"
"Which models are most cost-effective for my use case?"
"Recommend caching strategies for my agents"
"Calculate ROI of switching from Claude to Llama"
```

## Monitoring

### CloudWatch Logs
After deployment, monitor your agent:
```bash
# View logs (replace with your agent ID)
aws logs tail /aws/bedrock-agentcore/runtimes/{agent-id}-DEFAULT --follow
```

### Cost Tracking Dashboard
The agent automatically creates CloudWatch dashboards for:
- Real-time cost metrics
- Anomaly detection alerts
- Budget utilization
- Optimization recommendation tracking

### Health Checks
- Built-in health check endpoints
- Monitor agent availability and response times
- Track API call success rates

## Cleanup

### Complete Resource Cleanup
When you're done with the agent, use the cleanup script to remove all AWS resources:

```bash
# Complete cleanup (removes everything)
uv run python cleanup.py

# Preview what would be deleted (dry run)
uv run python cleanup.py --dry-run

# Keep IAM roles (useful if shared with other projects)
uv run python cleanup.py --skip-iam

# Cleanup in different region
uv run python cleanup.py --region us-west-2
```

**What gets cleaned up:**
- ✅ AgentCore Runtime instances
- ✅ AgentCore Memory instances  
- ✅ AgentCore Gateway configurations
- ✅ ECR repositories and container images
- ✅ CodeBuild projects
- ✅ S3 build artifacts
- ✅ SSM parameters
- ✅ IAM roles and policies (unless `--skip-iam`)
- ✅ CloudWatch dashboards
- ✅ Local deployment files

## Troubleshooting

### Common Issues

1. **Cost Explorer Access Denied**
   - Ensure Cost Explorer is enabled in your AWS account
   - Verify IAM permissions include `ce:*` actions
   - Check if you're using the correct account/organization

2. **Memory Instance Duplicates**
   - The agent uses SSM Parameter Store to prevent race conditions
   - If you see multiple memory instances, run: `uv run python cleanup.py`
   - Then redeploy with: `uv run python deploy.py`

3. **Gateway Connection Failures**
   - Verify Gateway is properly configured with Cost Explorer API
   - Check network connectivity and VPC settings
   - Review CloudWatch logs for detailed error messages

4. **Anomaly Detection False Positives**
   - Adjust sensitivity thresholds in agent configuration
   - Allow 30 days for baseline establishment
   - Review and update cost baselines regularly

### Debug Information
The deployment script includes comprehensive error reporting and will guide you through any issues.

## Security

### IAM Permissions
The deployment script automatically creates a role with:
- `ce:*` (Cost Explorer access)
- `budgets:*` (Budget management)
- `bedrock:InvokeModel` (for Amazon Bedrock Claude Sonnet)
- `bedrock-agentcore:*` (for memory, gateway, and runtime operations)
- `cloudwatch:*` (for metrics and dashboards)
- `pricing:*` (for AWS pricing data)

### Data Privacy

This solution handles AWS cost and usage data with the following privacy and security measures:

#### Data Classification
- **AWS Cost Data**: Classified as 'Confidential - Financial' information
- **Usage Patterns**: Classified as 'Internal - Operational' data
- **Optimization Recommendations**: Classified as 'Internal - Advisory' content

#### Data Handling Procedures
- **Storage**: Cost data is stored securely in Amazon Bedrock AgentCore Memory with encryption at rest
- **Transmission**: All communications use HTTPS/TLS encryption in transit
- **Processing**: Data is processed within your AWS environment and never shared externally
- **Access Controls**: Strict IAM-based access controls limit data access to authorized personnel only

#### Data Retention and Deletion
- **Retention Policy**: Cost data is retained for analysis purposes according to your organization's data retention policies
- **Automatic Cleanup**: Historical data older than configured retention periods is automatically purged
- **On-Demand Deletion**: Users can request immediate deletion of specific data through the cleanup procedures
- **Account Closure**: All data is permanently deleted when the agent is decommissioned

#### Multi-Tenant Considerations
- **Account Isolation**: Each AWS account's data is strictly isolated and cannot be accessed by other accounts
- **Role-Based Access**: Access is controlled through IAM roles and cannot cross account boundaries
- **Audit Logging**: All data access is logged for compliance and security monitoring

#### Compliance
- **GDPR Compliance**: Data handling procedures support GDPR requirements for data protection and deletion rights
- **SOC Compliance**: Follows AWS SOC compliance standards for data handling and security
- **Industry Standards**: Adheres to financial industry standards for handling cost and billing data

## Cost Considerations

### Agent Operating Costs
Estimated monthly costs for running this agent:
- **AgentCore Runtime**: ~$50-100/month (based on invocation frequency)
- **AgentCore Memory**: ~$10-20/month (based on data volume)
- **AgentCore Gateway**: ~$5-15/month (based on API calls)
- **Claude Sonnet 4**: Variable (based on analysis frequency)
- **Cost Explorer API**: Free (included with AWS account)

**Total Estimated Cost**: $65-135/month

### ROI Expectations
Typical cost savings identified by this agent:
- 10-30% reduction in compute costs through rightsizing
- 15-40% savings through Savings Plans recommendations
- 5-15% reduction in AI/ML costs through model optimization
- 20-50% savings by identifying and removing idle resources

**Expected ROI**: 10x-50x the agent's operating cost