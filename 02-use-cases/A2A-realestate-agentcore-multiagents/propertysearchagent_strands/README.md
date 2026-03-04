# Property Search Agent (Strands Implementation)

This agent provides real estate property search capabilities with filtering options. It's built with the Strands Agents framework and can be deployed to Bedrock AgentCore.

## Features

- **Property Search**: Search properties by location, price range, type, and bedrooms
- **Property Details**: Get detailed information about specific properties
- **Mock Database**: Uses in-memory property database for demonstration
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

- `AGENT_NAME`: Name of the agent (default: "Property Search Agent")
- `AGENT_DESCRIPTION`: Description of the agent
- `AGENT_HOST`: Host to bind the A2A server (default: "0.0.0.0")
- `AGENT_PORT`: Port for the A2A server (default: 5002)
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
- **A2A endpoint**: http://localhost:5002
- **Agent card**: http://localhost:5002/.well-known/agent.json

### Option 3: Test the Agent Directly

```bash
python agent.py
```

## Available Tools

### 1. search_properties

Search for properties based on criteria.

**Parameters:**
- `location` (optional): City or area to search in (e.g., 'New York', 'Austin')
- `min_price` (optional): Minimum monthly rent/price
- `max_price` (optional): Maximum monthly rent/price
- `property_type` (optional): Type of property ('apartment', 'house', 'condo')
- `min_bedrooms` (optional): Minimum number of bedrooms
- `max_bedrooms` (optional): Maximum number of bedrooms

**Returns:**
- Formatted list of matching properties with key details

### 2. get_property_details

Get detailed information about a specific property.

**Parameters:**
- `property_id` (required): The unique identifier of the property (e.g., 'PROP001')

**Returns:**
- Comprehensive property information including specifications and amenities

## Mock Property Database

The agent includes 8 sample properties across various locations:

1. **PROP001**: Modern Downtown Apartment - New York, NY ($3,500/month)
2. **PROP002**: Cozy Suburban House - Austin, TX ($2,800/month)
3. **PROP003**: Luxury Penthouse - San Francisco, CA ($8,500/month)
4. **PROP004**: Charming Studio Downtown - Boston, MA ($1,800/month)
5. **PROP005**: Beachfront Villa - Miami, FL ($12,000/month)
6. **PROP006**: Mountain Cabin Retreat - Denver, CO ($2,200/month) - Not Available
7. **PROP007**: Urban Loft - Seattle, WA ($3,200/month)
8. **PROP008**: Family Home with Yard - Portland, OR ($3,000/month)

## Usage Examples

### Example Queries

- "Show me apartments in New York under $4000"
- "Find houses with at least 3 bedrooms"
- "Search for properties in Austin between $2000 and $3000"
- "Show me the details of PROP003"
- "What luxury properties do you have?"

### Python SDK Usage

```python
from agent import create_property_search_agent

agent = create_property_search_agent()
response = agent("Show me apartments in New York under $4000")
print(response)
```

### A2A Protocol Usage

```bash
curl -X POST http://localhost:5002/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "Show me apartments in New York"}]
    }
  }'
```

## AgentCore Deployment

### Prerequisites

- Install AgentCore CLI: `pip install bedrock-agentcore-starter-toolkit`
- Configure AWS credentials

### Deployment Steps

#### Option 1: Use Deployment Script (Recommended)

```bash
# From samples/python directory
./deploy_to_agentcore.sh property-search
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
agentcore invoke --prompt "Show me apartments in New York"
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
  - Defines search_properties and get_property_details tools
  - Creates Strands Agent instance
  - Includes mock property database

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
Tool Execution (search_properties or get_property_details)
     ↓
Mock Database Query
     ↓
Response Formatting
     ↓
Return to User
```

## Error Handling

The agent handles various error scenarios:

- Property not found
- No properties matching criteria
- Invalid property IDs
- Missing parameters
- Network errors

All errors are logged and user-friendly error messages are returned.

## Testing

### Test with CLI Client

```bash
# From the samples/python directory
python cli_client.py http://localhost:5002
```

### Test with curl

```bash
# Get agent card
curl http://localhost:5002/.well-known/agent.json

# Search properties
curl -X POST http://localhost:5002/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "Show me properties in New York"}]
    }
  }'
```

## Integration with Property Booking Agent

This agent works seamlessly with the Property Booking Agent:

1. User searches for properties with this agent
2. User finds a property they like (e.g., PROP001)
3. User switches to Property Booking Agent to create a booking
4. Property Booking Agent uses the property ID to complete the booking

## Troubleshooting

### Agent Won't Start

**Solutions:**
- Check Python version: `python --version` (should be 3.9+)
- Verify AWS credentials: `aws sts get-caller-identity`
- Check port availability: `lsof -i :5002`
- Review logs for specific errors

### Port Already in Use

**Solutions:**
- Check what's using the port: `lsof -i :5002`
- Kill the process or change port in .env
- Use a different port: `AGENT_PORT=5012`

## Related Documentation

- [Main README](../../README.md) - Project overview
- [Local Development Guide](../../LOCAL_DEVELOPMENT.md) - Detailed local setup
- [AgentCore Deployment Guide](../../AGENTCORE_DEPLOYMENT.md) - Production deployment
- [Property Booking Agent](../propertybookingagent_strands/README.md) - Companion agent

## Resources

- [Strands Agents Documentation](https://github.com/awslabs/strands-agents)
- [A2A Protocol Specification](https://github.com/awslabs/a2a-python)
- [Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)

---

**Last Updated**: 2025-01-10
