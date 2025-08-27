# Deploying FastAPI to AWS Lambda with Mangum

This project demonstrates how to deploy a FastAPI application to AWS Lambda using Mangum adapter with API Gateway integration.

## Project Structure

```
cloud_insurance_api/
├── local_insurance_api/      # FastAPI application source code
│   ├── app.py                # FastAPI application definition
│   ├── data_loader.py        # Data loading utility
│   ├── routes/               # API route modules
│   └── services/             # Business logic services
├── lambda_function.py        # AWS Lambda handler with Mangum integration
├── deployment/
│   ├── template.yaml         # AWS SAM template for infrastructure
│   └── deploy.sh             # Deployment script using AWS SAM
├── openapi.json              # Generated OpenAPI specification
└── README.md                 # Project documentation
```

## How It Works

### 1. FastAPI Application

The `local_insurance_api` directory contains a FastAPI application that provides insurance-related endpoints. This is a standard FastAPI application that can run locally or be deployed to AWS Lambda.

### 2. Mangum Integration

[Mangum](https://github.com/jordaneremieff/mangum) is an adapter for using ASGI applications like FastAPI with AWS Lambda and API Gateway. It transforms API Gateway requests to a format that FastAPI can process, and then transforms FastAPI responses back to a format that API Gateway understands.

The integration is done in `lambda_function.py`:

```python
import os
import sys

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Import the FastAPI app
from local_insurance_api.app import app

# Import Mangum for AWS Lambda integration
from mangum import Mangum

# Create the handler
handler = Mangum(app)
```

The `handler` function is the Lambda function entry point. When API Gateway calls the Lambda function, Mangum processes the event and context, passes the request to the FastAPI app, and then returns the response in a format that API Gateway can understand.

### 3. AWS SAM Template

The `deployment/template.yaml` file defines the AWS resources that will be created using AWS Serverless Application Model (SAM). These include:

- Lambda Function: Runs the FastAPI application code
- API Gateway: Provides HTTP endpoints to invoke the Lambda function
- IAM Role: Permissions for Lambda execution
- CloudWatch Log Group: For Lambda execution logs

### 4. Deployment Process

The deployment is handled by the `deployment/deploy.sh` script, which uses AWS SAM CLI to:

1. Create an S3 bucket for deployment artifacts
2. Build a deployment package with the application code and dependencies
3. Upload the package to S3
4. Deploy the CloudFormation stack with the defined resources

## Prerequisites

Before deploying, ensure you have:

- AWS CLI installed and configured with appropriate permissions
- AWS SAM CLI installed
- Python 3.10+ installed
- An AWS account with access to Lambda, API Gateway, CloudFormation, S3, and IAM

## Deployment Steps

1. **Install Dependencies**

   Make sure your local environment has all the required dependencies:

   ```bash
   pip install -r local_insurance_api/requirements.txt
   pip install aws-sam-cli
   ```

2. **Export OpenAPI Specification (Optional)**

   The API has a pre-generated OpenAPI specification in `openapi.json`.

3. **Deploy to AWS**

   Run the deployment script:

   ```bash
   # Deploy to dev environment (default)
   ./deployment/deploy.sh

   # Deploy to specific environment (dev, test, prod)
   ./deployment/deploy.sh prod
   ```

4. **Test the API**

   After deployment, test your API using curl or any HTTP client:

   ```bash
   # Replace with your actual API Gateway URL
   ENDPOINT="https://i0zzy6t0x9.execute-api.us-west-2.amazonaws.com/dev"

   # Test health endpoint
   curl $ENDPOINT/health

   # Test policies endpoint
   curl $ENDPOINT/policies

   # Test customer info endpoint (POST request)
   curl -X POST $ENDPOINT/customer_info \
     -H "Content-Type: application/json" \
     -d '{"customer_id": "cust-001"}'
   ```

## Local Testing

To test locally before deployment:

```bash
# Run the FastAPI application directly
cd local_insurance_api
uvicorn app:app --reload --port 8001

# Test locally using AWS SAM
cd ..
sam local start-api
```

## Troubleshooting

Common issues and solutions:

### 1. Circular Imports

FastAPI applications can have circular imports when using modular structures. In Lambda, these can cause deployment failures. Solutions include:

- Using function-based imports inside functions rather than at module level
- Creating wrapper functions that import modules only when needed
- Using dependency injection patterns

For example, in our API:
```python
# Import routers using a function to avoid circular imports
def get_routers():
    from local_insurance_api.routes.general import router as general_router
    # more imports...
    return general_router, ...
```

### 2. Import Path Issues

When moving code between local environments and Lambda, import paths can break. Always use fully qualified imports in Lambda:

```python
# Use this in Lambda environments
from local_insurance_api.services import data_service

# Not this (which might work locally but break in Lambda)
from services import data_service
```

### 3. API Gateway Errors

- **403 Forbidden**: Check IAM permissions
- **500 Internal Server Error**: Check Lambda execution logs in CloudWatch
- **"Missing Authentication Token"**: Usually means the URL path is incorrect

### 4. Cold Start Latency

Lambda functions may experience "cold start" delays. To minimize:

- Increase Lambda memory allocation in `template.yaml`
- Use provisioned concurrency for critical endpoints
- Optimize dependency size

## API Documentation

The API provides several endpoints for insurance-related operations:
- `/openapi.json`: Raw OpenAPI specification
- `/health`: Health check endpoint
- `/policies`: Get all insurance policies
- `/customer_info`: Get customer information
- `/vehicle_info`: Get vehicle information
- `/insurance_products`: Get available insurance products

## Further Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Mangum Documentation](https://mangum.io/)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)

## Cleanup

When you're done with the Insurance API application, follow these steps to clean up all the AWS resources:

1. **Delete the CloudFormation Stack**:
   ```bash
   # Get the stack name (if you don't remember it)
   aws cloudformation list-stacks --query "StackSummaries[?contains(StackName,'insurance-api')].StackName" --output text
   
   # Delete the stack
   aws cloudformation delete-stack --stack-name insurance-api-stack-dev
   ```

2. **Delete the S3 Deployment Bucket** (if it's no longer needed):
   ```bash
   # List S3 buckets to find the deployment bucket
   aws s3 ls | grep insurance-api
   
   # Remove all files from the bucket first
   aws s3 rm s3://insurance-api-deployment-bucket-1234 --recursive
   
   # Delete the empty bucket
   aws s3api delete-bucket --bucket insurance-api-deployment-bucket-1234
   ```

3. **Verify Resource Deletion**:
   ```bash
   # Check if Lambda function still exists
   aws lambda list-functions --query "Functions[?contains(FunctionName,'insurance-api')].FunctionName" --output text
   
   # Check if API Gateway still exists
   aws apigateway get-rest-apis --query "items[?contains(name,'insurance-api')].id" --output text
   ```

4. **Clean up CloudWatch Logs** (optional):
   ```bash
   # Find the log group
   aws logs describe-log-groups --query "logGroups[?contains(logGroupName,'/aws/lambda/insurance-api')].logGroupName" --output text
   
   # Delete the log group
   aws logs delete-log-group --log-group-name /aws/lambda/insurance-api-function-dev
   ```

Note: Replace placeholder values like `insurance-api-stack-dev`, `insurance-api-deployment-bucket-1234`, and `/aws/lambda/insurance-api-function-dev` with your actual resource names.