# SRE Agent - Multi-Agent Site Reliability Engineering Assistant

## Overview

The SRE Agent is a multi-agent system for Site Reliability Engineers that helps investigate infrastructure issues. Built on the Model Context Protocol (MCP) and powered by Amazon Nova and Anthropic Claude models (Claude can be accessed through Amazon Bedrock or directly through Anthropic), this system uses specialized AI agents that collaborate to investigate issues, analyze logs, monitor performance metrics, and execute operational procedures. The AgentCore Gateway provides access to data sources and systems available as MCP tools.

### Use case details
| Information         | Details                                                                                                                             |
|---------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| Use case type       | conversational                                                                                                                      |
| Agent type          | Multi-agent                                                                                                                         |
| Use case components | Tools (MCP-based), observability (logs, metrics), operational runbooks                                                             |
| Use case vertical   | DevOps/SRE                                                                                                                          |
| Example complexity  | Advanced                                                                                                                            |
| SDK used            | Amazon Bedrock AgentCore SDK, LangGraph, MCP                                                                                       |

### Use case Architecture 

```mermaid
graph TB
    subgraph "User Interface"
        U["🧑‍💻 SRE Engineer"]
        CLI["Command Line Interface"]
        U -->|"Natural Language Query"| CLI
    end

    subgraph "SRE Agent Core"
        SUP["🧭 Supervisor Agent<br/>Orchestration & Routing"]
        K8S["☸️ Kubernetes Agent<br/>Infrastructure Operations"]
        LOG["📊 Logs Agent<br/>Log Analysis & Search"]
        MET["📈 Metrics Agent<br/>Performance Monitoring"]
        RUN["📖 Runbooks Agent<br/>Operational Procedures"]
        
        CLI -->|"Query"| SUP
        SUP -->|"Route"| K8S
        SUP -->|"Route"| LOG
        SUP -->|"Route"| MET
        SUP -->|"Route"| RUN
    end

    subgraph "AgentCore Gateway"
        GW["🌉 AgentCore Gateway<br/>MCP Protocol Handler"]
        AUTH["🔐 Authentication<br/>Token Management"]
        HEALTH["❤️ Health Monitor<br/>Circuit Breaker"]
        
        subgraph "Infrastructure APIs"
            DK8S["Kubernetes API<br/>:8011"]
            DLOG["Logs API<br/>:8012"]
            DMET["Metrics API<br/>:8013"]
            DRUN["Runbooks API<br/>:8014"]
        end
        
        K8S -.->|"MCP"| GW
        LOG -.->|"MCP"| GW
        MET -.->|"MCP"| GW
        RUN -.->|"MCP"| GW
        
        GW --> AUTH
        GW --> HEALTH
        GW --> DK8S
        GW --> DLOG
        GW --> DMET
        GW --> DRUN
    end

    subgraph "Amazon Bedrock"
        CLAUDE["Claude 4 Sonnet<br/>Large Language Model"]
        SUP -.->|"LLM Calls"| CLAUDE
        K8S -.->|"LLM Calls"| CLAUDE
        LOG -.->|"LLM Calls"| CLAUDE
        MET -.->|"LLM Calls"| CLAUDE
        RUN -.->|"LLM Calls"| CLAUDE
    end

    classDef agent fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef gateway fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef api fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef bedrock fill:#fff3e0,stroke:#e65100,stroke-width:2px
    
    class SUP,K8S,LOG,MET,RUN agent
    class GW,AUTH,HEALTH gateway
    class DK8S,DLOG,DMET,DRUN api
    class CLAUDE bedrock
```

### Use case key Features

- **Multi-Agent Orchestration**: Specialized agents collaborate on infrastructure investigations with real-time streaming
- **Conversational Interface**: Single-query investigations and interactive multi-turn conversations with context preservation
- **MCP-based Integration**: AgentCore Gateway provides secure API access with authentication and health monitoring
- **Specialized Agents**: Four domain-specific agents for Kubernetes, logs, metrics, and operational procedures
- **Documentation and Reporting**: Markdown reports generated for each investigation with audit trail

## Detailed Documentation

For comprehensive information about the SRE Agent system, please refer to the following detailed documentation:

- **[Specialized Agents](docs/specialized-agents.md)** - Detailed capabilities of each of the four specialized agents
- **[System Components](docs/system-components.md)** - In-depth architecture and component explanations
- **[Configuration](docs/configuration.md)** - Complete configuration guides for environment variables, agents, and gateway
- **[Demo Environment](docs/demo-environment.md)** - Demo scenarios, data customization, and testing setup
- **[Example Use Cases](docs/example-use-cases.md)** - Detailed walkthroughs and interactive troubleshooting examples
- **[Deployment and Security](docs/deployment-and-security.md)** - Sample deployment information and security considerations
- **[Verification](docs/verification.md)** - Ground truth verification and report validation
- **[Development](docs/development.md)** - Testing, code quality, and contribution guidelines

## Prerequisites

> **⚠️ IMPORTANT:** Amazon Bedrock AgentCore Gateway **only works with HTTPS endpoints**. You must have valid SSL certificates for your backend servers.

* Python 3.12+
* `uv` package manager for Python package management
* EC2 Instance (recommended: `t3.xlarge` or larger)
* Valid SSL certificates for HTTPS endpoints
* Either Anthropic API key or AWS credentials configured for Amazon Bedrock
* Updated OpenAPI specifications with your actual domain name

## Use case setup

```bash
# Clone the repository
git clone https://github.com/awslabs/amazon-bedrock-agentcore-samples
cd amazon-bedrock-agentcore-samples/02-use-cases/04-SRE-agent

# Create and activate a virtual environment
uv venv --python 3.12
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the SRE Agent and dependencies
uv pip install -e .

# Configure environment variables
cp .env.example sre_agent/.env
# Edit sre_agent/.env and add your Anthropic API key:
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# Update OpenAPI specifications with your domain
# Replace 'your-backend-domain.com' with your actual domain in all OpenAPI spec files
sed -i 's/your-backend-domain.com/mydomain.com/g' backend/openapi_specs/*.yaml

# Get your EC2 instance private IP for server binding
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" -s)
PRIVATE_IP=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" \
  -s http://169.254.169.254/latest/meta-data/local-ipv4)

# Start the demo backend servers with SSL
cd backend
./scripts/start_demo_backend.sh \
  --host $PRIVATE_IP  \
  --ssl-keyfile /etc/ssl/private/privkey.pem \
  --ssl-certfile /etc/ssl/certs/fullchain.pem
cd ..

# Create and configure the AgentCore Gateway
cd gateway
./create_gateway.sh
./mcp_cmds.sh
cd ..

# Update the gateway URI in agent configuration
GATEWAY_URI=$(cat gateway/.gateway_uri)
sed -i "s|uri: \".*\"|uri: \"$GATEWAY_URI\"|" sre_agent/config/agent_config.yaml

# Copy the gateway access token to your .env file
sed -i '/^GATEWAY_ACCESS_TOKEN=/d' sre_agent/.env
echo "GATEWAY_ACCESS_TOKEN=$(cat gateway/.access_token)" >> sre_agent/.env
```

## Execution instructions

### Single Query Mode
```bash
# Investigate specific pod issues
sre-agent --prompt "Why are the payment-service pods crash looping?"

# Analyze performance degradation
sre-agent --prompt "Investigate high latency in the API gateway over the last hour"

# Search for error patterns
sre-agent --prompt "Find all database connection errors in the last 24 hours"
```

### Interactive Mode
```bash
# Start interactive conversation
sre-agent --interactive

# Available commands in interactive mode:
# /help     - Show available commands
# /agents   - List available specialist agents
# /history  - Show conversation history
# /save     - Save the current conversation
# /clear    - Clear conversation history
# /exit     - Exit the interactive session
```

### Advanced Options
```bash
# Use Amazon Bedrock
sre-agent --provider bedrock --query "Check cluster health"

# Save investigation reports to custom directory
sre-agent --output-dir ./investigations --query "Analyze memory usage trends"

# Use Amazon Bedrock with specific profile
AWS_PROFILE=production sre-agent --provider bedrock --interactive
```

## Managing OpenAPI Specifications

### Important: Domain Configuration for Development vs Git Commits

The OpenAPI specification files in `backend/openapi_specs/` use a placeholder domain `your-backend-domain.com` by default. For development, you'll need to replace this with your actual domain, but **you must revert these changes before committing to git**.

#### For Development Setup
```bash
# Replace placeholder domain with your actual domain
sed -i 's/your-backend-domain.com/your-actual-domain.com/g' backend/openapi_specs/*.yaml
```

#### Before Committing Changes
```bash
# Revert back to placeholder domain before git commit
sed -i 's/your-actual-domain.com/your-backend-domain.com/g' backend/openapi_specs/*.yaml

# Then commit your changes
git add .
git commit -m "Your commit message"
```

#### Pre-commit Hook Protection
A git pre-commit hook is installed that automatically prevents commits of OpenAPI spec files that don't contain the placeholder domain `your-backend-domain.com`. This ensures that custom domain configurations don't accidentally get committed to the repository.

If the pre-commit hook blocks your commit:
1. Check which OpenAPI spec files contain custom domains
2. Use the sed command above to revert them to the placeholder
3. Commit again

## Clean up instructions

```bash
# Stop all demo servers
cd backend
./scripts/stop_demo_backend.sh
cd ..

# Remove virtual environment
deactivate
rm -rf .venv

# Clean up generated files
rm -rf reports/
rm -rf gateway/.gateway_uri gateway/.access_token
rm -rf sre_agent/.env
```

## Disclaimer
The examples provided in this repository are for experimental and educational purposes only. They demonstrate concepts and techniques but are not intended for direct use in production environments. Make sure to have Amazon Bedrock Guardrails in place to protect against [prompt injection](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-injection.html).

**Important Note**: The data in [`backend/data`](backend/data) is synthetically generated, and the backend directory contains stub servers that showcase how a real SRE agent backend could work. In a production environment, these implementations would need to be replaced with real implementations that connect to actual systems, use vector databases, and integrate with other data sources.