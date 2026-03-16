# Property Booking Agent (Strands Implementation)

This agent provides property booking and reservation management capabilities for real estate properties. It's built with the Strands Agents framework and can be deployed to Bedrock AgentCore.

## Features

- **Create Bookings**: Book properties with customer details and lease information
- **Check Booking Status**: View details of existing bookings
- **Cancel Bookings**: Cancel reservations with optional reason
- **List Customer Bookings**: View all bookings for a specific customer
- **Mock Database**: Uses in-memory booking database for demonstration
- **Multi-turn Conversations**: Handles user queries naturally through conversation
- **A2A Protocol**: Standard agent-to-agent communication support
- **Streaming Responses**: Real-time streaming for better user experience
- **Dual Deployment**: Run locally for development or deploy to AgentCore for production
- **Error Handling**: Comprehensive error handling and logging

## Prerequisites

- Python 3.9 or higher
- AWS credentials configured (for Bedrock model access)
- Required Python packages (see requirements.txt)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy the example environment file and configure:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Configuration

The agent can be configured using environment variables:

- `AGENT_NAME`: Name of the agent (default: "Property Booking Agent")
- `AGENT_DESCRIPTION`: Description of the agent
- `AGENT_HOST`: Host to bind the A2A server (default: "0.0.0.0")
- `AGENT_PORT`: Port for the A2A server (default: 5001)
- `AGENT_VERSION`: Agent version (default: "1.0.0")
- `MODEL_ID`: Bedrock model ID (default: "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0")
- `AWS_REGION`: AWS region (default: "us-east-1")

## Local Development

### Option 1: Use the Run Script (Recommended)

```bash
./run_local.sh
```

This script will:
- Create a virtual environment if needed
- Install dependencies
- Copy .env.example to .env if needed
- Start the agent

### Option 2: Run with A2A Server

```bash
python agent_agentcore.py
```

The agent will start an A2A server and be available at:
- **A2A endpoint**: http://localhost:5001
- **Agent card**: http://localhost:5001/.well-known/agent.json

### Option 3: Test the Agent Directly

```bash
python agent.py
```

## Available Tools

### 1. create_booking

Create a booking reservation for a property.

**Parameters:**
- `property_id` (required): The property ID to book (e.g., 'PROP001')
- `customer_name` (required): Full name of the customer
- `customer_email` (required): Email address of the customer
- `customer_phone` (required): Phone number of the customer
- `move_in_date` (required): Desired move-in date in YYYY-MM-DD format
- `lease_duration_months` (optional): Length of lease in months (default: 12)

**Returns:**
- Booking confirmation with details including booking ID, financial information, and next steps

### 2. check_booking_status

Check the status of an existing booking.

**Parameters:**
- `booking_id` (required): The booking ID to check (e.g., 'BOOK-ABC12345')

**Returns:**
- Booking status report with all details

### 3. cancel_booking

Cancel an existing booking.

**Parameters:**
- `booking_id` (required): The booking ID to cancel (e.g., 'BOOK-ABC12345')
- `reason` (optional): Optional reason for cancellation

**Returns:**
- Cancellation confirmation with refund information

### 4. list_customer_bookings

List all bookings for a specific customer.

**Parameters:**
- `customer_email` (required): Email address of the customer

**Returns:**
- List of customer's bookings with summary information

## Usage Examples

### Example Queries

- "Book property PROP001 for John Smith, email john@example.com, phone 555-1234, move-in date 2025-03-01"
- "Check the status of booking BOOK-ABC12345"
- "Cancel booking BOOK-ABC12345 because plans changed"
- "Show all bookings for john@example.com"
- "I want to book PROP003 starting April 15th 2025"

### Python SDK Usage

```python
from agent import create_property_booking_agent

agent = create_property_booking_agent()
response = agent("Book property PROP001 for John Smith, email john@example.com, phone 555-1234, move-in date 2025-03-01")
print(response)
```

### A2A Protocol Usage

```bash
curl -X POST http://localhost:5001/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "Book property PROP001"}]
    }
  }'
```

## Booking Workflow

1. **Search Properties**: Use Property Search Agent to find suitable properties
2. **Create Booking**: Use this agent to book the selected property
3. **Receive Confirmation**: Get booking ID and financial details
4. **Check Status**: Monitor booking status anytime
5. **Cancel if Needed**: Cancel bookings with refund processing

## Financial Details

When creating a booking, the agent calculates:

- **Monthly Rent**: Based on property price
- **Security Deposit**: Typically 2 months rent
- **Total Lease Cost**: Monthly rent × lease duration
- **Payment Timeline**: Deposit due within 48 hours

## AgentCore Deployment

### Prerequisites

- Install AgentCore CLI: `pip install bedrock-agentcore-starter-toolkit`
- Configure AWS credentials

### Deployment Steps

#### Option 1: Use Deployment Script (Recommended)

```bash
# From samples/python directory
./deploy_to_agentcore.sh property-booking
```

#### Option 2: Manual Deployment

1. **Configure the Agent**

```bash
agentcore configure agent_agentcore.py
```

2. **Launch to AgentCore**

```bash
agentcore launch
```

3. **Test the Deployed Agent**

```bash
agentcore invoke --prompt "Check status of booking BOOK-TEST123"
```

### Managing Deployed Agent

```bash
# Check status
agentcore status

# View logs
agentcore logs --tail 50

# Update agent after code changes
agentcore update

# Delete agent
agentcore delete
```

## Architecture

### File Structure

- **agent.py**: Core agent implementation with tools
  - Defines all booking management tools
  - Creates Strands Agent instance
  - Includes mock booking database

- **agent_agentcore.py**: AgentCore entrypoint wrapper
  - Wraps agent with BedrockAgentCoreApp
  - Provides @app.entrypoint handler for AgentCore
  - Includes local testing mode with A2A server

- **agentcore.yaml**: AgentCore configuration
  - Defines runtime settings
  - Specifies dependencies
  - Configures environment variables

- **requirements.txt**: Python dependencies

### Agent Flow

```
User Request
     ↓
A2A Server (agent_agentcore.py)
     ↓
Strands Agent (agent.py)
     ↓
Tool Execution (create_booking, check_booking_status, etc.)
     ↓
Mock Database Operation
     ↓
Response Formatting
     ↓
Return to User
```

## Error Handling

The agent handles various error scenarios:

- Property not found or unavailable
- Invalid booking IDs
- Invalid date formats
- Past move-in dates
- Already cancelled bookings
- Missing required parameters
- Network errors

All errors are logged and user-friendly error messages are returned.

## Testing

### Test with CLI Client

```bash
# From the samples/python directory
python cli_client.py http://localhost:5001
```

### Test with curl

```bash
# Get agent card
curl http://localhost:5001/.well-known/agent.json

# Create a booking
curl -X POST http://localhost:5001/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "Book property PROP001 for test"}]
    }
  }'
```

## Integration with Property Search Agent

This agent works seamlessly with the Property Search Agent:

1. **Search Phase**: User uses Property Search Agent to browse properties
2. **Selection**: User identifies property ID (e.g., PROP001)
3. **Booking Phase**: User switches to this agent to create booking
4. **Confirmation**: Booking is confirmed with all details
5. **Management**: User can check status or cancel as needed

## Mock Data

The agent uses mock data for demonstration:

- **Available Properties**: PROP001-PROP005, PROP007-PROP008
- **Unavailable**: PROP006
- **Booking IDs**: Generated as BOOK-XXXXXXXX
- **Database**: In-memory storage (resets on restart)

## Date Format

All dates must be in **YYYY-MM-DD** format:
- Valid: "2025-03-15", "2025-12-01"
- Invalid: "03/15/2025", "15-03-2025"

## Troubleshooting

### Agent Won't Start

**Solutions:**
- Check Python version: `python --version` (should be 3.9+)
- Verify AWS credentials: `aws sts get-caller-identity`
- Check port availability: `lsof -i :5001`
- Review logs for specific errors

### Booking Creation Fails

**Solutions:**
- Verify property ID exists and is available
- Check date format is YYYY-MM-DD
- Ensure move-in date is in the future
- Verify all required fields are provided

### Port Already in Use

**Solutions:**
- Check what's using the port: `lsof -i :5001`
- Kill the process or change port in .env
- Use a different port: `AGENT_PORT=5011`

## Related Documentation

- [Main README](../../README.md) - Project overview
- [Local Development Guide](../../LOCAL_DEVELOPMENT.md) - Detailed local setup
- [AgentCore Deployment Guide](../../AGENTCORE_DEPLOYMENT.md) - Production deployment
- [Property Search Agent](../propertysearchagent_strands/README.md) - Companion agent

## Resources

- [Strands Agents Documentation](https://github.com/awslabs/strands-agents)
- [A2A Protocol Specification](https://github.com/awslabs/a2a-python)
- [Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)

---

**Last Updated**: 2025-01-10
