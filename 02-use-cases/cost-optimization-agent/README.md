# Cost Optimization Agent

## Overview

This use case implements an intelligent AWS cost optimization agent using Amazon Bedrock AgentCore that provides real-time cost monitoring, anomaly detection, budget tracking, and actionable recommendations for reducing cloud spend. The agent combines LLM-powered analysis with AWS Cost Explorer Service data and maintains persistent memory of cost baselines and optimization strategies.

## Use Case Architecture

![Cost Optimization Agent Architecture](images/cost-optimization-architecture.png)

> **Note**: To generate the architecture diagram, see [scripts/README.md](scripts/README.md). For a detailed text-based architecture view, see [ARCHITECTURE.md](ARCHITECTURE.md).

| Information | Details |
|-------------|---------|
| Use case type | Analytical & Monitoring |
| Agent type | Multi-Agent (Monitor + Analyzer + Recommender) |
| Use case components | Memory, Gateway, Code Interpreter, Observability |
| Use case vertical | FinOps / Cloud Operations |
| Example complexity | Advanced |
| SDK used | Amazon Bedrock AgentCore SDK, Strands Agents, AWS Cost Explorer |

## Features

### 💰 Real-Time Cost Monitoring
- **Multi-Account Support**: Track costs across multiple AWS accounts and organizational units
- **Service-Level Breakdown**: Detailed cost analysis by AWS service, region, and resource tags
- **Anomaly Detection**: Automatic identification of unusual spending patterns and cost spikes
- **Budget Tracking**: Monitor budget utilization and forecast overruns

### 🧠 Advanced Memory Management
- **Cost Baselines**: Maintains historical cost patterns and establishes normal spending ranges
- **Optimization History**: Tracks implemented recommendations and their impact
- **Team Preferences**: Stores cost allocation tags, budget owners, and notification preferences
- **Multi-Strategy Memory**: Uses both USER_PREFERENCE and SEMANTIC memory strategies

### 📊 Intelligent Analysis & Recommendations
- **Model Selection Optimization**: Recommends optimal model choices based on task complexity vs cost
- **Caching Strategies**: Identifies opportunities for response caching to reduce token usage
- **Resource Rightsizing**: Analyzes usage patterns and suggests appropriate instance types
- **Savings Plans Analysis**: Evaluates commitment discount opportunities

### 🔧 Code Interpreter Integration
- **Cost Forecasting**: Generates predictive models for future spending
- **Trend Analysis**: Creates visualizations and statistical analysis of cost patterns
- **ROI Calculations**: Computes return on investment for optimization recommendations
- **Custom Reports**: Generates executive summaries and detailed cost breakdowns

### 🚨 Proactive Alerting
- **Budget Alerts**: Configurable thresholds for budget consumption warnings
- **Anomaly Notifications**: Real-time alerts for unusual spending patterns
- **Optimization Opportunities**: Proactive identification of cost-saving opportunities
- **Scheduled Reports**: Daily, weekly, or monthly cost summaries

## Quick Start

### Prerequisites
- Python 3.10+
- AWS CLI configured with appropriate credentials
- Docker or Podman installed and running
- Access to Amazon Bedrock AgentCore
- AWS Cost Explorer enabled in your account

### Installation & Deployment

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

### 📊 Cost Analysis
```
"What are my top 5 most expensive services this month?"
"Show me cost trends for the last 3 months"
"Which region is costing me the most?"
"Analyze my EC2 spending patterns"
```

### 🔍 Anomaly Detection
```
"Are there any unusual cost spikes today?"
"What caused the increase in my S3 costs?"
"Show me services with abnormal spending"
```

### 💡 Optimization Recommendations
```
"How can I reduce my Lambda costs?"
"What Savings Plans should I consider?"
"Identify underutilized resources"
"Recommend model selection for my AI workloads"
```

### 📈 Budget Management
```
"How much of my monthly budget have I used?"
"Forecast my spending for next month"
"Set up alerts for when I reach 80% of budget"
"Show me budget vs actual for each team"
```

### 🎯 Token Usage Optimization
```
"Analyze my Amazon Bedrock token usage"
"Which models are most cost-effective for my use case?"
"Recommend caching strategies for my agents"
"Calculate ROI of switching from Claude to Llama"
```

## Architecture

### Multi-Agent System

```
┌─────────────────────────────────────────────────────────────────┐
│                  Cost Optimization Agent System                  │
├─────────────────────────────────────────────────────────────────┤
│  Monitor Agent (Real-time tracking)                             │
│  ├── AWS Cost Explorer Integration                              │
│  ├── CloudWatch Metrics Collection                              │
│  └── Anomaly Detection Engine                                   │
├─────────────────────────────────────────────────────────────────┤
│  Analyzer Agent (Deep analysis)                                 │
│  ├── Claude Sonnet 4 (LLM)                                     │
│  ├── Code Interpreter (Forecasting & Visualization)            │
│  └── Historical Pattern Analysis                                │
├─────────────────────────────────────────────────────────────────┤
│  Recommender Agent (Actionable insights)                        │
│  ├── Optimization Strategy Generation                           │
│  ├── ROI Calculation                                            │
│  └── Implementation Guidance                                    │
├─────────────────────────────────────────────────────────────────┤
│  AgentCore Multi-Strategy Memory                                │
│  ├── USER_PREFERENCE: Team preferences, budgets, thresholds    │
│  └── SEMANTIC: Cost baselines, optimization history            │
├─────────────────────────────────────────────────────────────────┤
│  AgentCore Gateway (AWS API Integration)                        │
│  ├── Cost Explorer API                                          │
│  ├── CloudWatch API                                             │
│  ├── Compute Optimizer API                                      │
│  └── Pricing API                                                │
└─────────────────────────────────────────────────────────────────┘
```

### Memory Strategies
- **USER_PREFERENCE**: Stores team preferences, budget allocations, notification settings, cost allocation tags
- **SEMANTIC**: Maintains cost baselines, historical patterns, optimization recommendations, and their outcomes

### Available Tools

**Cost Monitoring** (`tools/cost_explorer_tools.py`):
- `get_cost_and_usage(start_date, end_date, granularity, group_by)`: Retrieve detailed cost data
- `get_cost_forecast(start_date, end_date)`: Predict future costs based on historical patterns
- `detect_cost_anomalies(lookback_days)`: Identify unusual spending patterns
- `get_service_costs(service_name, time_period)`: Analyze specific service costs

**Budget Management** (`tools/budget_tools.py`):
- `get_budget_status(budget_name)`: Check current budget utilization
- `forecast_budget_overrun(budget_name)`: Predict if budget will be exceeded
- `get_all_budgets()`: List all configured budgets and their status
- `calculate_burn_rate(time_period)`: Compute daily/weekly spending rate

**Optimization Analysis** (`tools/optimization_tools.py`):
- `analyze_savings_plans_coverage()`: Evaluate Savings Plans utilization
- `identify_idle_resources()`: Find unused or underutilized resources
- `recommend_model_selection(use_case, requirements)`: Suggest optimal AI models
- `calculate_caching_roi(usage_pattern)`: Estimate savings from response caching
- `analyze_rightsizing_opportunities()`: Identify oversized instances

**Memory & Baseline Management** (`tools/memory_tools.py`):
- `store_cost_baseline(service, baseline_data)`: Save normal spending patterns
- `get_cost_baseline(service)`: Retrieve established baselines
- `update_optimization_history(recommendation, outcome)`: Track recommendation results
- `get_team_preferences(team_id)`: Retrieve team-specific settings

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

## AI/GenAI Usage Disclosure

This solution uses Amazon Bedrock with Claude 3.5 Sonnet to provide intelligent cost optimization recommendations. Please note:

1. **AI-Generated Recommendations**: All cost optimization suggestions are generated by AI and should be reviewed by qualified personnel before implementation
2. **Suggestions, Not Guarantees**: The agent provides suggestions based on data analysis, not guaranteed outcomes or definitive financial advice
3. **Human Oversight Required**: Users maintain full responsibility for cost optimization decisions and should validate all recommendations
4. **Data Processing**: The AI processes your AWS cost and usage data to generate insights, but does not store or share this data outside your AWS environment

## Bias and Fairness Considerations

This AI-powered cost optimization agent is designed with the following considerations:

1. **Balanced Recommendations**: The agent analyzes all AWS services equally and does not favor specific services or vendors in its recommendations
2. **Performance Safeguards**: Recommendations include safeguards against over-aggressive cost cutting that could negatively impact system performance or reliability
3. **Multi-Account Fairness**: In multi-account scenarios, the agent provides equitable analysis across all accounts without bias toward larger or smaller usage patterns
4. **Transparency**: All recommendations include clear explanations of the analysis methodology and data sources used
5. **Human Review Requirements**: Critical cost optimization decisions require human oversight, especially for changes that could impact production systems or exceed predefined thresholds

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

## Contributing

We welcome contributions to improve the Cost Optimization Agent! Please follow these guidelines:

### Contributor License Agreement
By contributing to this project, you agree that your contributions will be licensed under the same Apache License 2.0 that covers this project. This ensures that the project remains open source and that all contributors' work is properly protected.

### How to Contribute
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

### Contribution Guidelines
- Follow existing code style and patterns
- Include comprehensive tests for new features
- Update documentation as needed
- Ensure all security best practices are followed

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](../../LICENSE) file for details.
