# Shopping Agent Overview

AI-powered concierge agent with shopping assistance capabilities, built with AWS Bedrock AgentCore, Amplify, and React.

The shopping assistant specializes in all shop-related queries including reviews research, feature information, and personalized recommendations based on user profile. It compares items, gives you prices, shows reviews, and ensures that all items are aligned with user preferences and constraints.

## Use Case Details
| Information         | Details                                                      |
|---------------------|--------------------------------------------------------------|
| Use case type       | Agentic Payments                                             |
| Agent type          | Multi-agent                                                  |
| Use case components | Tools (MCP-based), observability (logs, metrics)             |
| Use case vertical   | FSI                                                          |
| Example complexity  | Advanced                                                     |
| SDK used            | Strands, MCP                                                 |

## Features

- **Shopping Assistant** - Product search and recommendations (requires SERP API integration)
- **Cart & Payment** - Cart management with Visa tokenization support (feature flag enabled)
- **Conversation Memory** - Persistent chat history across sessions
- **Real-time Streaming** - Live agent responses with tool usage indicators
- **Secure Authentication** - AWS Cognito with JWT-based auth

## Getting Started

For complete deployment instructions, prerequisites, troubleshooting, and configuration, see the **[Deployment Guide](DEPLOYMENT.md)**.

### Quick Deploy
[Go to the Development Guide section](./DEPLOYMENT.md#Quick_Start)

## Project Structure

```
sample-concierge-agent/
├── amplify/                    # AWS Amplify backend (Cognito, DynamoDB, GraphQL)
├── concierge_agent/           # Agent code and Docker container
│   ├── Dockerfile
│   └── code/                  # Python agent implementation
├── infrastructure/            # CDK infrastructure for agent deployment
├── documents/                 # Knowledge base documents
├── web-ui/                    # React frontend application
└── scripts/                   # Deployment and setup scripts
```

## Documentation

- **[Deployment Guide](DEPLOYMENT.md)** - Complete deployment instructions, prerequisites, and troubleshooting
- **[Visa Local Setup](docs/VISA_LOCAL_SETUP.md)** - Setup for real Visa API testing
- **[Infrastructure README](infrastructure/README.md)** - CDK infrastructure details
- **[Frontend Mock Mode](FRONTEND_MOCK_MODE.md)** - Test UI without backend
- **[Visa Documentation](visa-documentation/README.md)** - Visa APIs documentation

## Data Flow
![shopping data flow](docs/shopping_data_flow.png)

## Architecture
![shopping arch](docs/Shopping_Agent_VISA.png)

## Demo
![Shopping Agent Demo](docs/demo.gif)

## Configuration

For detailed configuration including:
- API Keys (SERP API, Visa API)
- Visa Payment Integration (Mock vs Real)
- Local Development Setup
- Environment Variables
- Cleanup Instructions

See the **[Deployment Guide](DEPLOYMENT.md)**.

> [!NOTE]
> This project is provided as a sample implementation for educational purposes, it is NOT PRODUCTION READY.
>  Please ensure compliance with your organization's policies and AWS service terms.
