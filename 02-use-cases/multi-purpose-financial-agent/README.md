# Financial Analyzer Agent

A production-ready AI agent demonstrating AWS Bedrock AgentCore integration with the Strands framework for financial data analysis.

## Quick Start

**Prerequisites:** Python 3.9+, AWS CLI configured with credentials

```bash
./setup.sh
```

That's it! The script will:
1. ✓ Check prerequisites (Python, AWS CLI, credentials)
2. ✓ Create virtual environment
3. ✓ Install all dependencies
4. ✓ Launch Jupyter Notebook automatically

The infrastructure setup notebook will open in your browser. Follow the notebook cells to provision all AWS resources.

---

## Overview

This sample demonstrates how to build an enterprise financial analysis agent that:

- **Queries project budget data** from DynamoDB via AgentCore Gateway (MCP tools)
- **Analyzes quarterly financial data** from S3 using AgentCore Code Interpreter
- **Authenticates securely** with Cognito JWT tokens
- **Runs on any framework** (Strands Agents, LangChain, LangGraph, or custom)

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Financial Analyzer Agent                     │
│                  (Strands/LangChain/LangGraph)                  │
└────────────┬────────────────────────────────────┬───────────────┘
             │                                    │
             │ MCP Tools                          │ Code Execution
             ▼                                    ▼
┌────────────────────────┐          ┌────────────────────────────┐
│  AgentCore Gateway     │          │  AgentCore Code Interpreter│
│  + Identity (Cognito)  │          │  (Secure Sandbox)          │
└────────┬───────────────┘          └────────────┬───────────────┘
         │                                       │
         │ Lambda Invocation                     │ S3 Access
         ▼                                       ▼
┌────────────────────────┐          ┌────────────────────────────┐
│  Lambda Function       │          │  S3 Bucket                 │
│  (Project Queries)     │          │  (Quarterly Data CSV)      │
└────────┬───────────────┘          └────────────────────────────┘
         │
         │ DynamoDB Queries
         ▼
┌────────────────────────┐
│  DynamoDB Table        │
│  (Project Budget Data) │
└────────────────────────┘
```

## Features

### 1. **Project Budget Queries** (Gateway + Lambda + DynamoDB)
- List all projects
- Get specific project details
- Filter by department (Engineering, Marketing, Sales, etc.)
- Filter by budget range
- Filter by status (Active, At Risk, Completed, etc.)

### 2. **Financial Data Analysis** (Code Interpreter + S3)
- Load quarterly financial data from S3
- Analyze revenue and expense trends
- Calculate year-over-year growth
- Identify top-performing quarters
- Generate financial insights

### 3. **Secure Authentication** (Cognito + AgentCore Identity)
- OAuth 2.0 client credentials flow
- Machine-to-machine authentication
- Secure token management

## What Gets Created

When you run the infrastructure notebook, it provisions:

- **DynamoDB Table** - 10 sample projects with budget data
- **S3 Bucket** - Quarterly financial data (XLSX)
- **Lambda Function** - Query interface for DynamoDB
- **Cognito User Pool** - JWT authentication
- **AgentCore Gateway** - Converts Lambda to MCP tools
- **IAM Roles** - Proper permissions for all services
- **SSM Parameters** - Configuration storage

**Time**: ~5-10 minutes

## Running the Agent

After infrastructure is provisioned, run the agent:

```bash
source venv/bin/activate
python -m src.agent.analyst_assistant_unified_strands
```

Or with PYTHONPATH:

```bash
export PYTHONPATH=$(pwd):$PYTHONPATH
python src/agent/analyst_assistant_unified_strands.py
```

The agent will:
1. Load configuration from SSM Parameter Store
2. Authenticate with Cognito
3. Connect to AgentCore Gateway
4. Start Code Interpreter session
5. Enter interactive chat mode

### Example Queries

Try these example queries:

**Project Budget Queries:**
```
You: Show me project PROJ-001
You: List all Marketing department projects
You: Find projects with budgets over $50,000
You: Show me all projects that are "At Risk"
```

**Financial Analysis:**
```
You: What was our Q4 2023 revenue?
You: Show me expense trends over time
You: Which quarter had the highest revenue?
You: Analyze our year-over-year growth
```

## Project Structure

```
finance-analyzer/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── src/                              # Source code
│   ├── agent/                        # Agent implementations
│   │   └── analyst_assistant_unified_strands.py  # Strands-based agent
│   ├── lambda/                       # AWS Lambda functions
│   │   └── project-budget-lambda.py  # DynamoDB query Lambda
│   └── utils/                        # Shared utilities
│       └── utils.py                  # Config, auth, helper functions
├── infrastructure/                    # Infrastructure as Code
│   ├── infrastructure_setup.ipynb    # Jupyter notebook for AWS setup
│   ├── data/                         # Sample data files
│   │   ├── project-budget.json       # Sample project data (10 projects)
│   │   └── quarterly_results.xlsx    # Sample quarterly financial data
│   └── schemas/                      # Tool and API schemas
│       └── gateway-projects-budget.json  # Gateway tool definitions
├── config/                           # Configuration files (uses SSM Parameter Store)
└── docs/                             # Documentation
    ├── PROJECT_STRUCTURE.md          # Detailed structure guide
    └── MIGRATION_GUIDE.md            # Migration from old structure
```

For more details, see [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md).

## Sample Data

### Project Budget Data (DynamoDB)

10 sample projects across different departments:
- **Engineering**: GenAI Customer Support Bot, Mobile App Redesign, SOC2 Compliance
- **Marketing**: Q4 Digital Ad Spend, SEO & Content Optimization
- **Sales**: Salesforce Licensing, Global Tech Conference Booth
- **DevOps**: CI/CD Pipeline Migration
- **Finance**: Financial Forecasting Tool
- **IT/Ops**: Engineering Laptop Refresh

### Quarterly Financial Data (S3)

CSV file with quarterly results including:
- Revenue by quarter
- Expenses by quarter
- Year-over-year comparisons
- Quarterly trends

## AgentCore Components Used

### 1. **AgentCore Gateway**
Converts the Lambda function into MCP-compatible tools that agents can discover and use:
- `list_all_projects`
- `get_project`
- `list_department_projects`
- `filter_by_budget`
- `list_by_status`

### 2. **AgentCore Identity**
Manages authentication between the agent and Gateway using Cognito:
- OAuth 2.0 client credentials flow
- Automatic token refresh
- Secure credential storage in SSM Parameter Store

### 3. **AgentCore Code Interpreter**
Provides secure Python code execution for data analysis:
- Loads CSV files from S3
- Executes pandas operations
- Generates insights and visualizations
- Runs in isolated sandbox environment

### 4. **AgentCore Runtime** (Optional)
Deploy the agent to serverless runtime for production:
```bash
# Configure and deploy
agentcore configure
agentcore deploy
```

## Configuration

All configuration is stored in AWS Systems Manager Parameter Store under `/{prefix}/`:

### Required Parameters

These parameters are automatically created by `infrastructure_setup.ipynb`:

- `/finance-analyzer/dynamodb_table` - DynamoDB table name
- `/finance-analyzer/s3_bucket` - S3 bucket name
- `/finance-analyzer/s3_quarterly_data_path` - S3 path to quarterly data (e.g., `s3://bucket-name/quarterly-data/`)
- `/finance-analyzer/lambda_function` - Lambda function ARN
- `/finance-analyzer/user_pool_id` - Cognito User Pool ID
- `/finance-analyzer/client_id` - Cognito App Client ID
- `/finance-analyzer/client_secret` - Cognito App Client Secret (SecureString)
- `/finance-analyzer/cognito_domain` - Cognito domain prefix
- `/finance-analyzer/gateway_id` - AgentCore Gateway ID
- `/finance-analyzer/gateway_arn` - AgentCore Gateway ARN
- `/finance-analyzer/gateway_url` - AgentCore Gateway URL

### Configuration Override

The agent loads configuration from SSM Parameter Store by default. You can customize the region and prefix:

```python
# In analyst_assistant_unified_strands.py
config, config_loaded = load_config_from_ssm(
    prefix="/finance-analyzer",  # SSM parameter prefix
    region=None  # AWS region (None uses boto3 default region resolution)
)
```

The agent uses boto3's default region resolution, which checks (in order):
1. `AWS_REGION` environment variable
2. `AWS_DEFAULT_REGION` environment variable
3. AWS config file (`~/.aws/config`)
4. Instance metadata (if running on EC2)

## Cleanup

To remove all created resources:

```bash
cd infrastructure
./cleanup.sh --region us-west-2
```

This will delete:
- DynamoDB table
- S3 bucket (and all contents)
- Lambda function
- IAM roles and policies
- Cognito User Pool
- AgentCore Gateway
- SSM parameters

## Cost Estimate

Running this sample incurs minimal costs:

- **DynamoDB**: Pay-per-request pricing (~$0.01/day for testing)
- **S3**: Storage + requests (~$0.01/day)
- **Lambda**: Free tier covers most testing
- **Cognito**: Free tier covers up to 50,000 MAUs
- **AgentCore Gateway**: Pay per request
- **AgentCore Code Interpreter**: Pay per execution
- **Bedrock**: Pay per token (Claude Sonnet 4.0)

**Estimated cost for testing**: < $5/day

## Troubleshooting

### Gateway Connection Issues

If you see "I/O operation on closed file" errors:
- The MCP session is closing prematurely
- This is fixed in `analyst_assistant_unified_langchain_v2.py`
- Ensure the session context manager wraps the entire agent loop

### Authentication Errors

If you see 401 Unauthorized errors:
- Check Cognito credentials in SSM Parameter Store
- Verify the Gateway is configured with the correct User Pool
- Ensure the App Client has client credentials flow enabled

### Tool Parameter Errors

If the agent tries multiple parameter formats:
- The tool schema isn't being passed correctly
- Use v2 implementation which properly converts MCP schemas to Pydantic models

### Code Interpreter Errors

If file loading fails:
- Verify S3 bucket permissions
- Check the Code Interpreter session is active
- Ensure the file path is correct

## Learn More

- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
- [AgentCore Samples Repository](https://github.com/awslabs/amazon-bedrock-agentcore-samples)
- [Strands Agents Documentation](https://strandsagents.com/)
- [LangChain Documentation](https://python.langchain.com/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

## Contributing

Contributions are welcome! Please see the main [AgentCore Samples Contributing Guidelines](https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/CONTRIBUTING.md).

## License

This sample is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Related Samples

- [AgentCore Runtime Quickstart](https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/01-tutorials/01-AgentCore-runtime)
- [AgentCore Gateway Tutorial](https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/01-tutorials/02-AgentCore-gateway)
- [Multi-Agent Patterns](https://github.com/awslabs/amazon-bedrock-agentcore-samples/tree/main/03-integrations)
