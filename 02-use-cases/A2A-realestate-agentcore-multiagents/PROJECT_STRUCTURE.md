# Project Structure

Clean, organized structure for the Real Estate Multi-Agent System.

## Directory Tree

```
A2A-realestate-agents/
│
├── 📄 README.md                          # Main documentation
├── 📄 QUICKSTART.md                      # Quick start guide
├── 📄 DEPLOYMENT_GUIDE.md                # Detailed deployment guide
├── 📄 PROJECT_STRUCTURE.md               # This file
│
├── 🔧 .gitignore                         # Git ignore rules
├── 🔧 requirements.txt                   # Python dependencies
│
├── 🚀 start-backend.sh                   # Start backend server
├── 🚀 start-ui.sh                        # Start React UI
│
├── 📊 deployment_info.json               # Agent deployment info (generated)
├── 📊 cognito_config.json                # Cognito OAuth config (generated)
│
├── 🐍 setup_cognito_automated.py         # Setup Cognito OAuth
├── 🐍 deploy_agents_with_oauth.py        # Deploy all agents
├── 🐍 get_fresh_token.py                 # Generate OAuth tokens
│
├── 🧪 test_coordinator_quick.py          # Quick coordinator test
│
├── 📁 ui/                                # React TypeScript UI
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatMessage.tsx           # Message component
│   │   │   └── ChatMessage.css
│   │   ├── services/
│   │   │   └── api.ts                    # API client
│   │   ├── App.tsx                       # Main app
│   │   ├── App.css
│   │   ├── index.tsx
│   │   ├── index.css
│   │   └── react-app-env.d.ts
│   ├── package.json
│   ├── tsconfig.json
│   └── .gitignore
│
├── 📁 ui-backend/                        # Flask API Server
│   ├── server.py                         # Backend API
│   └── requirements.txt
│
├── 📁 realestate_coordinator/            # Coordinator Agent
│   ├── agent.py                          # Main agent logic
│   ├── agent_agentcore.py                # AgentCore entry point
│   ├── .bedrock_agentcore.yaml           # AgentCore config
│   └── requirements.txt
│
├── 📁 propertysearchagent_strands/       # Property Search Agent
│   ├── agent.py                          # Search logic
│   ├── agent_agentcore.py                # AgentCore entry point
│   ├── .bedrock_agentcore.yaml           # AgentCore config
│   └── requirements.txt
│
├── 📁 propertybookingagent_strands/      # Property Booking Agent
│   ├── agent.py                          # Booking logic
│   ├── agent_agentcore.py                # AgentCore entry point
│   ├── .bedrock_agentcore.yaml           # AgentCore config
│   └── requirements.txt
│
└── 📁 common/                            # Shared utilities
    └── utils/
        └── logging_config.py             # Logging configuration
```

## File Descriptions

### Documentation
- **README.md**: Complete project documentation with architecture, setup, and usage
- **QUICKSTART.md**: Get started in 5 minutes
- **DEPLOYMENT_GUIDE.md**: Detailed deployment and production guide
- **PROJECT_STRUCTURE.md**: This file - project organization

### Configuration
- **.gitignore**: Excludes tokens, cache, logs, and build artifacts
- **requirements.txt**: Core Python dependencies
- **deployment_info.json**: Generated during deployment, contains agent ARNs
- **cognito_config.json**: Generated during Cognito setup

### Scripts
- **start-backend.sh**: Starts Flask API server on port 5000
- **start-ui.sh**: Starts React dev server on port 3000
- **setup_cognito_automated.py**: Creates Cognito User Pool with OAuth
- **deploy_agents_with_oauth.py**: Deploys all agents to AgentCore
- **get_fresh_token.py**: Generates fresh OAuth access tokens

### Tests
- **test_coordinator_quick.py**: Quick test of coordinator with sub-agents

### UI Application
- **ui/**: Modern React TypeScript application
  - Professional chat interface
  - Real-time communication with backend
  - Markdown support for rich responses
  - Responsive design
  - Connection status indicator

### Backend API
- **ui-backend/**: Flask REST API server
  - OAuth token management
  - Request proxying to coordinator
  - Automatic token refresh
  - CORS enabled for local development

### Agents
- **realestate_coordinator/**: Orchestrator agent
  - Coordinates sub-agents using A2A protocol
  - Natural language understanding
  - Tool calling for search and booking

- **propertysearchagent_strands/**: Property search specialist
  - Search by location, price, type, bedrooms
  - Returns formatted property listings

- **propertybookingagent_strands/**: Booking specialist
  - Create property bookings
  - Check booking status
  - List user bookings

### Common
- **common/**: Shared utilities
  - Structured logging configuration
  - Reusable helper functions

## Key Files by Purpose

### For Deployment
1. `setup_cognito_automated.py` - First time OAuth setup
2. `deploy_agents_with_oauth.py` - Deploy agents to AWS
3. `deployment_info.json` - Stores deployment details

### For Running Locally
1. `start-backend.sh` - Start API server
2. `start-ui.sh` - Start web interface
3. `get_fresh_token.py` - Refresh OAuth token

### For Testing
1. `test_coordinator_quick.py` - Quick validation

### For Development
1. `ui/src/App.tsx` - Main UI component
2. `ui-backend/server.py` - Backend API
3. `realestate_coordinator/agent.py` - Coordinator logic
4. `propertysearchagent_strands/agent.py` - Search logic
5. `propertybookingagent_strands/agent.py` - Booking logic

## Generated Files (Not in Git)

These files are generated during setup/runtime:

```
.bearer_token                 # OAuth access token
bearer_token.json             # Token with metadata
venv/                         # Python virtual environment
ui/node_modules/              # Node.js dependencies
ui/build/                     # Production build
**/__pycache__/               # Python bytecode cache
*.pyc, *.pyo                  # Compiled Python files
*.log                         # Log files
```

## Dependencies

### Python Packages
- **strands**: Agent framework
- **flask**: Web framework for backend
- **flask-cors**: CORS support
- **boto3**: AWS SDK
- **requests**: HTTP client
- **a2a**: Agent-to-Agent protocol library

### Node.js Packages
- **react**: UI framework
- **typescript**: Type safety
- **axios**: HTTP client
- **react-markdown**: Markdown rendering

## Ports Used

- **3000**: React development server (UI)
- **5000**: Flask API server (Backend)
- **9000**: AgentCore agents (when running locally)

## AWS Resources Created

- **Cognito User Pool**: OAuth authentication
- **AgentCore Runtimes**: 3 agents deployed
- **ECR Repositories**: Container images for agents
- **IAM Roles**: Execution roles for agents
- **CloudWatch Logs**: Agent logs

## Clean Architecture

The project follows clean architecture principles:

1. **Separation of Concerns**: UI, Backend, Agents are independent
2. **Single Responsibility**: Each agent has one specific purpose
3. **Dependency Injection**: Configuration via environment/files
4. **Testability**: Each component can be tested independently
5. **Scalability**: Agents scale independently on AgentCore

## Next Steps

1. **Customize Agents**: Modify agent logic in `agent.py` files
2. **Enhance UI**: Add features in `ui/src/`
3. **Add Agents**: Create new specialized agents
4. **Production Deploy**: Follow DEPLOYMENT_GUIDE.md
5. **Monitor**: Use CloudWatch for logs and metrics

---

**Last Updated:** November 2025
