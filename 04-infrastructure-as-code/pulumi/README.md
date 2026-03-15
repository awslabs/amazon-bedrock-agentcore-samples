# Pulumi Samples for Amazon Bedrock AgentCore

Deploy Amazon Bedrock AgentCore resources using Pulumi TypeScript.

## Prerequisites

1. **Pulumi CLI** - [Install Pulumi](https://www.pulumi.com/docs/install/)
2. **Node.js 18+** and **npm**
3. **AWS CLI** installed and configured
4. **Python 3.11+** for test scripts
5. **Pulumi Account** (or another [state backend](https://www.pulumi.com/docs/iac/concepts/state-and-backends/))

### Authentication

Pulumi supports multiple AWS authentication methods. The recommended approach is [Pulumi ESC with AWS OIDC](https://www.pulumi.com/docs/esc/environments/configuring-oidc/aws/) for short-lived credentials.

See [AWS provider configuration](https://www.pulumi.com/registry/packages/aws/installation-configuration/) for all options.

## Samples

| Sample                                                                     | Description                                              | Deployment Time |
| :------------------------------------------------------------------------- | :------------------------------------------------------- | :-------------- |
| [basic-runtime](./typescript/basic-runtime/)                               | Simple Strands agent on AgentCore                        | ~8-12 min       |
| [mcp-server-agentcore-runtime](./typescript/mcp-server-agentcore-runtime/) | MCP server with Cognito JWT auth                         | ~8-12 min       |
| [multi-agent-runtime](./typescript/multi-agent-runtime/)                   | Two-agent system with A2A communication                  | ~15-20 min      |
| [end-to-end-weather-agent](./typescript/end-to-end-weather-agent/)         | Weather agent with Browser, Code Interpreter, and Memory | ~8-12 min       |

## Quick Start

Each sample follows the same workflow:

```bash
cd typescript/<sample-name>

# Install dependencies
npm install

# Log in to Pulumi
pulumi login

# Create or select a stack
pulumi stack init dev

# (Optional) Add ESC environment for AWS credentials
pulumi config env add <esc-project>/<esc-environment> -s dev --yes

# Set AWS region
pulumi config set aws:region us-east-1 -s dev

# Preview and deploy
pulumi preview -s dev
pulumi up -s dev

# Run tests
python test_*.py "$(pulumi stack output agentRuntimeArn -s dev)"

# Clean up
pulumi destroy -s dev
```

See each sample's README for configuration options, outputs, and testing instructions.
