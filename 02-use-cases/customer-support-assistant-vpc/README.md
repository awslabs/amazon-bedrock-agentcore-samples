# Customer Support Assistant - Private VPC

> [!IMPORTANT]
> The examples provided in this repository are for experimental and educational purposes only. They demonstrate concepts and techniques but are not intended for direct use in production environments.

This is a customer support agent implementation using Amazon Bedrock AgentCore deployed in a fully private VPC environment. The system provides an AI-powered customer support interface with capabilities for warranty checking, customer profile management, and cross-system data access across multiple data sources including Aurora PostgreSQL, DynamoDB tables, and Lambda-based APIs. The architecture demonstrates secure, isolated deployment using VPC endpoints for AWS service access without internet connectivity.

## Architecture Overview

![arch](./images/architecture.png)

## Prerequisites

1. **AWS Account**: You need an active AWS account with appropriate permissions
   - [Create AWS Account](https://aws.amazon.com/account/)
   - [AWS Console Access](https://aws.amazon.com/console/)

2. **AWS CLI**: Install and configure AWS CLI with your credentials
   - [Install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
   - [Configure AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html)

   ```bash
   aws configure
   ```

3. **Bedrock Model Access**: Enable access to Amazon Bedrock Anthropic Claude 4.0 models in your AWS region
   - Navigate to [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock/)
   - Go to "Model access" and request access to:
     - Anthropic Claude 4.0 Sonnet model
     - Anthropic Claude 3.5 Haiku model
   - [Amazon Bedrock Model Access Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)

4. **Supported Regions**: This solution is currently tested and supported in the following AWS regions:

   | Region Code   | Region Name          | Status      |
   |---------------|----------------------|-------------|
   | `us-east-1`   | US East (N. Virginia)| ✅ Supported |
   | `us-west-2`   | US West (Oregon)     | ✅ Supported |

   > **Note**: To deploy in other regions, you'll need to update the DynamoDB prefix list mappings in `cloudformation/vpc-stack.yaml`. See the [VPC Stack documentation](cloudformation/vpc-stack.yaml) for details.

## Deployment Steps

> [!NOTE]
> This script automates deployment of resources in your AWS Account, please refer [deployed resources](#deployed-resources) to understand the resources that will be created.

```bash
# Make it executable
chmod +x deploy.sh

./deploy.sh --help
# Or customize the model
./deploy.sh --model global.anthropic.claude-sonnet-4-20250514-v1:0 --region us-west-2 --env dev
```

### Deployed Resources

The deployment creates the following CloudFormation stacks and AWS resources:

<details>
<summary><b>0. S3 Bucket</b> (Created by <code>deploy.sh</code>)</summary>

- **1 S3 Bucket** with auto-generated name (`customersupportvpc-*` prefix)
- **Versioning Enabled** for CloudFormation template version control
- **Purpose**: Hosts all CloudFormation nested stack templates
- **Lifecycle**: Can be deleted after successful deployment if templates won't be updated

</details>

<details>
<summary><b>1. VPC Stack</b> (<code>vpc-stack.yaml</code>)</summary>

- **1 VPC** with DNS support enabled
- **4 Private Subnets** across 3 availability zones
- **1 Route Table** for private subnets
- **13 VPC Endpoints** (Interface & Gateway):
  - Bedrock Runtime & AgentCore
  - ECR (API & Docker)
  - CloudWatch Logs & Monitoring
  - DynamoDB Gateway Endpoint
  - S3 Gateway Endpoint
  - Secrets Manager
  - RDS Data API
  - KMS
  - SSM Parameter Store
  - X-Ray
- **3 Security Groups** (VPC Endpoints, Agent Runtime, MCP Runtime)
- **1 KMS Key** for VPC Flow Logs encryption
- **1 CloudWatch Log Group** for VPC Flow Logs

</details>

<details>
<summary><b>2. Cognito Stack</b> (<code>cognito-m2m-stack.yaml</code>)</summary>

- **1 Cognito User Pool** for M2M authentication
- **1 User Pool Domain** for OAuth endpoints
- **1 Resource Server** with custom scopes (read, write, gateway, agent)
- **3 App Clients** (Gateway, Agent, MCP) with client credentials flow
- **3 Secrets Manager Secrets** for client configurations
- **1 KMS Key** for Secrets Manager encryption
- **1 Lambda Function** to retrieve and store client secrets
- **3 Custom Resources** to update client secrets

</details>

<details>
<summary><b>3. Aurora PostgreSQL Stack</b> (<code>aurora-postgres-stack.yaml</code>)</summary>

- **1 Aurora PostgreSQL Cluster** with RDS Data API enabled
- **1 Aurora Instance** (db.r5.large)
- **1 DB Subnet Group** across 2 subnets
- **1 KMS Key** for database encryption
- **2 Security Groups** (Aurora, Lambda)
- **1 S3 Bucket** for Lambda layer artifacts
- **1 CodeBuild Project** for psycopg2 layer build
- **1 Lambda Layer** (psycopg2)
- **2 Lambda Functions** (layer builder, mock data loader)
- **Sample Data**: Users, Products, Orders tables with mock records

</details>

<details>
<summary><b>4. DynamoDB Stack</b> (<code>dynamodb-stack.yaml</code>)</summary>

- **2 DynamoDB Tables**:
  - Reviews table (with 3 GSIs: product, customer, rating)
  - Products table (with 4 GSIs: category, name, price, stock)
- **1 KMS Key** for DynamoDB encryption
- **1 Lambda Function** for data population
- **2 SSM Parameters** for table names
- **Sample Data**: 5 reviews and 5 products

</details>

<details>
<summary><b>5. MCP Server Stack</b> (<code>mcp-server-stack.yaml</code>)</summary>

- **1 ECR Repository** for MCP Docker images
- **1 Bedrock AgentCore MCP Runtime**
- **1 CodeBuild Project** for Docker image builds
- **1 Lambda Function** for build orchestration
- **1 Lambda Function** for ECR image notifications
- **1 EventBridge Rule** for automated updates
- **1 OAuth2 Credential Provider** for MCP authentication
- **3 IAM Roles** (Runtime Execution, CodeBuild, Lambda)

</details>

<details>
<summary><b>6. Gateway Stack</b> (<code>gateway-stack.yaml</code>)</summary>

- **1 Bedrock AgentCore Gateway** with MCP protocol
- **1 Gateway Target** (Lambda integration)
- **1 Lambda Function** for customer support tools (warranty check, profile lookup)
- **1 Lambda Function** for gateway management
- **1 Lambda Function** for data population
- **2 DynamoDB Tables**:
  - Warranty table (encrypted with KMS)
  - Customer Profile table (with 2 GSIs: email, phone)
- **1 KMS Key** for DynamoDB encryption
- **1 OAuth2 Credential Provider** for Gateway authentication
- **3 SSM Parameters** (gateway ID, ARN, URL)
- **3 IAM Roles** (Gateway, Lambda, Management)
- **Sample Data**: 5 warranties and 5 customer profiles

</details>

<details>
<summary><b>7. Agent Server Stack</b> (<code>agent-server-stack.yaml</code>)</summary>

- **1 ECR Repository** for Agent Docker images
- **1 Bedrock AgentCore Agent Runtime** with HTTP protocol
- **1 CodeBuild Project** for Agent Docker builds
- **2 Lambda Functions** (build orchestration, ECR notifications)
- **1 EventBridge Rule** for automated updates
- **1 OAuth2 Credential Provider** for Agent authentication
- **4 IAM Roles** (Runtime Execution, CodeBuild, Lambda)
- **Environment Variables**: Model ID, MCP ARN, Gateway Provider, Aurora credentials

</details>

## Testing

After deployment, you can test the system using the provided test scripts:

### Test Agent Runtime

Test the Agent Runtime by sending prompts directly:

```bash
python test/connect_agent.py --prompt "Get me customer name of customer id CUST001" --stack-name customer-support-vpc
```

**Parameters:**

- `--prompt` (required): The prompt/question to send to the agent
- `--stack-name` (optional): CloudFormation parent stack name (default: `customer-support-vpc`)
- `--verbose` / `-v` (optional): Enable verbose logging
- `--debug` (optional): Enable debug logging

**Example queries:**

```bash
# Query customer information
python test/connect_agent.py --prompt "Get me customer name of customer id CUST001"

# Check warranty status
python test/connect_agent.py --prompt "Check warranty status for serial number LAPTOP001A1B2C"

# Get product reviews
python test/connect_agent.py --prompt "Show me reviews for product id 1"
```

### Test MCP Server

Test the MCP DynamoDB server and list available tools:

```bash
python test/connect_mcp.py --stack-name customer-support-vpc
```

**Parameters:**

- `--stack-name` (optional): CloudFormation parent stack name (default: `customer-support-vpc`)
- `--verbose` / `-v` (optional): Enable verbose logging
- `--debug` (optional): Enable debug logging

This script will:

1. Connect to the MCP server
2. List all available tools (get_reviews, get_products, etc.)
3. Run test queries against the DynamoDB tables

## Streamlit

Run the Streamlit web interface for interactive customer support:

```bash
# Install dependencies
uv sync

# Run the app (uses default stack name: customer-support-vpc)
uv run streamlit run app.py --server.port 8501

# Or with a custom stack name
uv run streamlit run app.py --server.port 8501 -- --stack-name=customer-support-vpc
```

**Parameters:**

- `--stack-name` (optional): CloudFormation parent stack name (default: `customer-support-vpc`)

The app will automatically:

1. Retrieve the agent configuration from CloudFormation
2. Set up OAuth2 authentication via Cognito
3. Provide an interactive chat interface

> [!NOTE]
> The Streamlit app must run on port 8501 for OAuth2 callback to work properly.

## Sample Queries

### Customer Profile & Purchase History

**Query**: *"Can you provide a complete profile for customer CUST001 including their purchase history and support details?"*
**Expected Response**: Complete customer view with personal details, VIP tier status, $3,250.99 lifetime value, purchase history including laptop and coffee mug orders, and product reviews.

### Product Information & Customer Feedback

**Query**: *"Tell me about the Laptop Pro product including customer reviews, inventory status, and warranty information."*
**Expected Response**: Product specifications, average customer rating, review summaries, current stock levels across warehouses, and warranty coverage details.

### Customer Support Case Analysis

**Query**: *"What can you tell me about Bob Johnson's account and any issues he might have had with his recent purchases?"*
**Expected Response**: VIP customer profile, business account holder status, multiple support interactions, recent purchases with shipping status, and positive product feedback.

### Inventory & Purchase Correlation

**Query**: *"Which customers have purchased laptops and what do they think about them? Also check current inventory levels."*
**Expected Response**: John Doe (CUST001) and Jane Smith (CUST002) purchased laptops, with 5-star and 4-star reviews respectively, plus current inventory: 50 units across 3 warehouses.

### Warranty Status & Customer Relationship

**Query**: *"Check the warranty status for laptop serial number LAPTOP001A1B2C and tell me about the customer who owns it."*
**Expected Response**: Extended warranty valid until 2025-08-15, owned by John Doe (Premium tier customer), $3,250.99 lifetime value, who gave the laptop a 5-star review praising its performance.

### Category Analysis & Customer Preferences

**Query**: *"Show me all Electronics category products, their reviews, and which customers prefer this category based on their purchase patterns."*
**Expected Response**: Electronics products (laptops, mice, keyboards, webcams), category breakdown including subcategories, customer review summaries, and customer segments (Premium/VIP customers prefer electronics).

### Comprehensive Customer Journey

**Query**: *"Trace the complete customer journey for Jane Smith from registration to her latest interaction."*
**Expected Response**: Registered March 2023, Gold tier customer, prefers email + phone communication, purchased smartphone and desk chair totaling $1,899.50, left positive reviews, tech enthusiast profile, 1 support case resolved.

### Cross-System Data Validation

**Query**: *"Verify data consistency between systems for customer CUST004 and highlight any discrepancies."*
**Expected Response**: Alice Brown consistent across all systems, Standard tier in DynamoDB matches single purchase in Aurora, USB cable review in FastAPI aligns with customer profile and purchase data.

### Business Intelligence Query

**Query**: *"Which customers are most valuable and what products do they prefer? Include their support engagement levels."*
**Expected Response**: VIP/Premium customers identified (CUST001: $3,250.99, CUST003: $8,750.25), preferred Electronics category, positive review patterns, varying support engagement levels indicating satisfaction.

## Database Schema

### Amazon Aurora PostgreSQL database

The Aurora PostgreSQL database contains three main tables that store user information, product catalog, and order history. These tables are linked to DynamoDB customer profiles via the `customer_id` field.

<details>
<summary><b>Users Table</b></summary>

| Column Name   | Data Type      | Constraints           | Description                                |
|---------------|----------------|-----------------------|--------------------------------------------|
| id            | SERIAL         | PRIMARY KEY           | Auto-incrementing user ID                  |
| customer_id   | VARCHAR(20)    | UNIQUE, NOT NULL      | Links to DynamoDB customer profiles        |
| username      | VARCHAR(50)    | UNIQUE, NOT NULL      | Unique username                            |
| email         | VARCHAR(100)   | UNIQUE, NOT NULL      | User email address                         |
| first_name    | VARCHAR(50)    |                       | User's first name                          |
| last_name     | VARCHAR(50)    |                       | User's last name                           |
| created_at    | TIMESTAMP      | DEFAULT CURRENT_TIMESTAMP | Account creation timestamp          |

**Sample Data:** 5 users (CUST001-CUST005) linked to DynamoDB profiles

</details>

<details>
<summary><b>Products Table</b></summary>

| Column Name     | Data Type      | Constraints           | Description                                |
|-----------------|----------------|-----------------------|--------------------------------------------|
| id              | SERIAL         | PRIMARY KEY           | Auto-incrementing product ID               |
| name            | VARCHAR(100)   | NOT NULL              | Product name                               |
| description     | TEXT           |                       | Product description                        |
| price           | DECIMAL(10,2)  |                       | Product price                              |
| category        | VARCHAR(50)    |                       | Product category                           |
| stock_quantity  | INTEGER        | DEFAULT 0             | Available inventory count                  |
| created_at      | TIMESTAMP      | DEFAULT CURRENT_TIMESTAMP | Product creation timestamp          |

**Sample Data:** 10 products including electronics (laptop, mouse, keyboard, webcam, USB cable) and office supplies (coffee mug, notebook, desk chair, monitor stand, water bottle)

</details>

<details>
<summary><b>Orders Table</b></summary>

| Column Name   | Data Type      | Constraints           | Description                                |
|---------------|----------------|-----------------------|--------------------------------------------|
| id            | SERIAL         | PRIMARY KEY           | Auto-incrementing order ID                 |
| customer_id   | VARCHAR(20)    | FOREIGN KEY → users(customer_id) | References customer             |
| total_amount  | DECIMAL(10,2)  |                       | Order total amount                         |
| status        | VARCHAR(20)    | DEFAULT 'pending'     | Order status (pending/completed/shipped)   |
| order_date    | TIMESTAMP      | DEFAULT CURRENT_TIMESTAMP | Order creation timestamp            |

**Sample Data:** 5 orders with various statuses across different customers

</details>


### Amazon DynamoDB tables (exposed by [DynamoDB MCP Server](./mcp_dynamodb/))

These DynamoDB tables are accessed through the MCP (Model Context Protocol) Server, providing product catalog and customer review data.

<details>
<summary><b>Reviews Table</b></summary>

**Primary Key:**
- `review_id` (String) - HASH

**Attributes:**

| Attribute Name    | Data Type | Description                              |
|-------------------|-----------|------------------------------------------|
| review_id         | String    | Unique review identifier                 |
| product_id        | Number    | Product being reviewed                   |
| customer_id       | String    | Customer who wrote the review            |
| rating            | Number    | Star rating (1-5)                        |
| title             | String    | Review title                             |
| comment           | String    | Review text                              |
| verified_purchase | Boolean   | Whether purchase was verified            |
| created_at        | String    | Review creation timestamp (ISO 8601)     |

**Sample Data:** 5 reviews for products (laptop, mouse, coffee mug, desk chair) with ratings 3-5 stars

</details>

<details>
<summary><b>Products Table</b></summary>

**Primary Key:**
- `product_id` (Number) - HASH

**Attributes:**

| Attribute Name  | Data Type | Description                              |
|-----------------|-----------|------------------------------------------|
| product_id      | Number    | Unique product identifier                |
| name            | String    | Product name                             |
| description     | String    | Product description                      |
| price           | Number    | Product price (Decimal)                  |
| category_id     | Number    | Category identifier                      |
| stock_quantity  | Number    | Available inventory count                |
| created_at      | String    | Product creation timestamp (ISO 8601)    |

**Sample Data:** 5 products including Laptop Pro ($1299.99), Wireless Mouse ($29.99), Coffee Mug ($12.99), Desk Chair ($299.99), and USB Cable ($19.99)

</details>

### Amazon DynamoDB tables (exposed by [Amazon Bedrock AgentCore Gateway](./cloudformation/gateway-stack.yaml))

These DynamoDB tables are accessed through the Amazon Bedrock AgentCore Gateway via AWS Lambda functions, providing warranty tracking and customer profile management.

<details>
<summary><b>Warranty Table</b></summary>

**Primary Key:**
- `serial_number` (String) - HASH

**Attributes:**

| Attribute Name    | Data Type | Description                              |
|-------------------|-----------|------------------------------------------|
| serial_number     | String    | Unique product serial number             |
| product_name      | String    | Name of the product                      |
| purchase_date     | String    | Date of purchase (YYYY-MM-DD)            |
| warranty_end_date | String    | Warranty expiration date (YYYY-MM-DD)    |
| warranty_type     | String    | Type (Standard/Extended/Premium)         |
| customer_name     | String    | Name of customer who purchased           |
| coverage_details  | String    | Detailed warranty coverage description   |

**Sample Data:** 5 warranty records for various products (laptop, phone, tablet, watch, camera) with different warranty types and expiration dates

</details>

<details>
<summary><b>Customer Profile Table</b></summary>

**Primary Key:**
- `customer_id` (String) - HASH

**Attributes:**

| Attribute Name              | Data Type | Description                              |
|-----------------------------|-----------|------------------------------------------|
| customer_id                 | String    | Unique customer identifier (CUST###)     |
| first_name                  | String    | Customer's first name                    |
| last_name                   | String    | Customer's last name                     |
| email                       | String    | Customer email address                   |
| phone                       | String    | Customer phone number                    |
| address                     | Map       | Address object (street, city, state, zip, country) |
| date_of_birth               | String    | Date of birth (YYYY-MM-DD)               |
| registration_date           | String    | Account registration date (YYYY-MM-DD)   |
| tier                        | String    | Customer tier (Standard/Gold/Premium/VIP)|
| communication_preferences   | Map       | Communication preferences (email, sms, phone) |
| support_cases_count         | Number    | Total number of support cases            |
| total_purchases             | Number    | Total number of purchases                |
| lifetime_value              | Number    | Total customer lifetime value (Decimal)  |
| notes                       | String    | Additional customer notes                |

**Sample Data:** 5 customer profiles (CUST001-CUST005) with tiers ranging from Standard to VIP, linked to Aurora PostgreSQL users table via `customer_id`

</details>

### Cross-System Data Relationships

The system integrates data across Aurora PostgreSQL and DynamoDB tables using consistent identifiers:

**Customer Data Integration:**

- `customer_id` (CUST###) links Aurora `users` table with DynamoDB `Customer Profile` table
- Aurora `orders.customer_id` references `users.customer_id` for purchase history
- DynamoDB `Reviews.customer_id` links back to Aurora users for review attribution
- Enables 360° customer view combining transactional, profile, and feedback data

**Product Data Integration:**

- Product data exists in both Aurora `products` table and DynamoDB `Products` table
- Cross-referenced via `product_id` and name matching
- DynamoDB `Reviews.product_id` links to both Aurora and DynamoDB product records
- Aurora tracks inventory and orders; DynamoDB tracks reviews and catalog metadata

**Warranty & Support Integration:**

- DynamoDB `Warranty` table uses `customer_name` and `product_name` for cross-system validation
- Links warranty records with customer profiles and product information
- Enables comprehensive support case management across all data sources

## Cleanup

To remove the deployed resources, use the provided cleanup script:

```bash
# Make it executable
chmod +x cleanup.sh

./cleanup.sh --help

# Delete all stacks except VPC
./cleanup.sh --delete-s3  --region us-west-2

```

> [!WARNING]
> Amazon Bedrock AgentCore Runtime creates [ENIs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html) in the VPC. These ENIs take ~8 hours to be automatically removed by the service. Please manually delete the VPC stack after the ENIs are removed.

```bash
./cleanup.sh --delete-vpc  --region us-west-2
```
