# Auto Insurance Platform - Local Prototype

This directory contains a complete local prototype of an auto insurance platform with three main components:

1. **Insurance API**: A FastAPI-based backend service providing insurance-related data and functionality
2. **Local MCP Server**: A Model Context Protocol server that exposes insurance tools to LLMs
3. **Strands Insurance Agent**: An interactive agent that uses Claude 3.7 to interact with the insurance tools

## System Overview

The local prototype demonstrates a complete agent-based architecture for insurance applications:

- **Insurance API** (Port 8001): Core backend service with customer, vehicle, and policy data
- **MCP Server** (Port 8000): Middleware that exposes Insurance API endpoints as MCP tools
- **Strands Agent**: Frontend that uses Claude 3.7 Sonnet to provide a natural language interface

This architecture shows how developers can build LLM-powered applications that interact with structured data services through standardized protocols.

## Components

### 1. Insurance API

A FastAPI application that simulates an auto insurance backend with realistic sample data.

**Key Features:**
- Customer information endpoints
- Vehicle data and safety ratings
- Risk assessment calculations
- Insurance product catalogs and pricing
- Policy management (view, filter, search)

**Sample Data:**
- Customer profiles
- Vehicle specifications
- Credit reports
- Insurance products
- Insurance policies

### 2. Local MCP Server

A Model Context Protocol (MCP) server that provides access to the Insurance API through standardized tools.

**Key Tools:**
- `get_customer_info`: Retrieve customer details
- `get_vehicle_info`: Get vehicle specifications
- `get_insurance_quote`: Generate insurance quotes
- `get_vehicle_safety`: Access safety ratings
- `get_all_policies`: View all policies
- `get_policy_by_id`: Retrieve specific policy details
- `get_customer_policies`: Find policies by customer ID

### 3. Strands Insurance Agent

An interactive agent built with Anthropic's Strands framework that connects to the MCP server.

**Key Features:**
- Natural language interaction with insurance tools
- Conversation history and context persistence
- AWS Bedrock integration for Claude 3.7 Sonnet
- Comprehensive error handling and response formatting

### 4. Streamlit Dashboard

A visualization and testing interface for the entire insurance platform system.

**Key Features:**
- System status monitoring
- API endpoint testing
- MCP tool execution
- Agent chat simulation
- System architecture visualization
- Interactive data exploration

## Setup Instructions

### Prerequisites

- Python 3.10+
- AWS account with Bedrock access to Claude 3.7 Sonnet
- Node.js and npm (for the MCP Inspector)
- uv package manager (recommended)

### 1. Insurance API Setup

```bash
# Navigate to the Insurance API directory
cd local_insurance_api

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the API server
python -m uvicorn server:app --port 8001
```

The Insurance API will be available at `http://localhost:8001`.

### 2. MCP Server Setup

```bash
# Navigate to the MCP Server directory
cd local_mcp_server

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the MCP server with HTTP transport
python server.py --http
```

The MCP server will be available at `http://localhost:8000/mcp`.

### 3. Strands Agent Setup

```bash
# Navigate to the Strands Agent directory
cd local_strands_insurance_agent

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure AWS credentials
Configure credentials using [link](https://strandsagents.com/latest/documentation/docs/user-guide/quickstart/#configuring-credentials)

# Start the interactive agent
python interactive_insurance_agent.py
```


## Testing with MCP Inspector

You can test the MCP server directly using the MCP Inspector tool:

```bash
# Install and start the MCP Inspector
npx @modelcontextprotocol/inspector
```

This will open the MCP Inspector in your browser. Connect to `http://localhost:8000/mcp` to explore and test the available tools.

## Example Usage

### Insurance API Endpoints

```bash
# Get all policies
curl http://localhost:8001/policies

# Get a specific policy
curl http://localhost:8001/policies/policy-001

# Get a customer's policies
curl http://localhost:8001/customer/cust-001/policies

# Get insurance products
curl -X POST http://localhost:8001/insurance_products \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Strands Agent Queries

```
You: What information do you have about customer cust-001?
Agent: [Returns detailed information about John Smith]

You: What kind of car does he have?
Agent: [Uses context to provide vehicle information]

You: Can you give me a quote for a 2023 Toyota RAV4?
Agent: [Generates a quote based on customer profile]
```

## Valid Test Data

Use these values for testing:

- Customer IDs: `cust-001`, `cust-002`, `cust-003`
- Vehicle Makes: `Toyota`, `Honda`, `Ford`
- Vehicle Models: `Camry`, `Civic`, `F-150`
- Vehicle Years: Any year between 2010-2023
- Policy IDs: `policy-001`, `policy-002`, `policy-003`

## Directory Structure

```
local_prototype/
├── local_insurance_api/            # Core backend service
│   ├── data/                 # Sample data files
│   ├── routes/               # API endpoints
│   ├── services/             # Business logic
│   ├── app.py                # Application initialization
│   └── server.py             # Entry point
├── local_mcp_server/        # MCP server implementation
│   ├── tools/                # MCP tool definitions
│   ├── config.py             # Server configuration
│   └── server.py             # Entry point
└── local_strands_insurance_agent/  # Interactive agent
    └── interactive_insurance_agent.py  # Agent implementation
```

## Architecture Diagram

```
┌───────────────────┐      ┌───────────────────┐      ┌───────────────────┐
│                   │      │                   │      │                   │
│  Strands Agent    │◄────►│  MCP Server       │◄────►│  Insurance API    │
│  (Claude 3.7)     │      │  (Model Context   │      │  (FastAPI)        │
│                   │      │   Protocol)       │      │                   │
└───────────────────┘      └───────────────────┘      └───────────────────┘
       ▲                                                      ▲
       │                                                      │
       │                                                      │
       ▼                                                      ▼
┌───────────────────┐                               ┌───────────────────┐
│                   │                               │                   │
│  User             │                               │  Sample Data      │
│  (Console)        │                               │  (JSON Files)     │
│                   │                               │                   │
└───────────────────┘                               └───────────────────┘
```

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   - Error: "Address already in use"
   - Solution: Kill the process using the port or specify a different port

2. **Connection Refused**
   - Error: "Connection refused" when connecting to services
   - Solution: Make sure all three components are running

3. **AWS Authentication Issues**
   - Error: "Could not connect to the endpoint URL"
   - Solution: Check your AWS credentials and region

## Next Steps

For production deployment, see the `agentcore_app` directory which demonstrates how to deploy this architecture to AWS using AgentCore.

## 📝 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](../../../LICENSE) file for details.


## Note

This local prototype demonstrates how a developer can build an agentic application with:
- FastAPI backend service
- Model Context Protocol (MCP) server
- Anthropic's Strands agent framework
- Claude 3.7 Sonnet LLM