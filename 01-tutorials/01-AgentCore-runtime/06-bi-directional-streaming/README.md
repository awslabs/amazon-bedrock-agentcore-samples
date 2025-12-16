# Amazon Bedrock AgentCore - Bidirectional WebSocket Samples

This repository contains sample implementations demonstrating bidirectional WebSocket communication with Amazon Bedrock AgentCore:

- **Sonic** - Native Amazon Nova Sonic Python WebSocket implementation deployed directly to AgentCore. Provides full control over the Nova Sonic protocol with direct event handling. Includes a web client for testing real-time audio conversations with voice selection and interruption support.

- **Strands** - High-level framework implementation using the Strands BidiAgent for simplified real-time audio conversations. Built on top of Nova Sonic with automatic session management, tool integration, and a streamlined API. Perfect for rapid prototyping and production applications that benefit from framework abstractions.

- **Echo** - Simple echo server for testing WebSocket connectivity and authentication without AI features.

All samples use a unified setup and cleanup process through the root `setup.sh` and `cleanup.sh` scripts.

## Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.12+
- Docker (for building custom agent images)
- AWS Account ID

---

## Sonic Sample - Native Nova Sonic 2 Implementation

This sample deploys a **native Amazon Nova Sonic 2 Python WebSocket server** directly to AgentCore. It provides full control over the Nova Sonic protocol with direct event handling, giving you complete visibility into session management, audio streaming, and response generation.

**Architecture:** 

![AgentCore Sonic Architecture](./images/agentcore-sonic-architecture.png)

**Best for:** Production applications requiring real-time audio conversations with fine-grained control over session management and event handling.

### Setup

```bash
# Required
export ACCOUNT_ID=your_aws_account_id

# Optional - customize these or use defaults
export AWS_REGION=us-east-1
export IAM_ROLE_NAME=WebSocketSonicAgentRole
export ECR_REPO_NAME=agentcore_sonic_images
export AGENT_NAME=websocket_sonic_agent

# AWS Authentication (choose one method):

# Method 1: Using AWS Profile (recommended)
# Set AWS_PROFILE environment variable OR ensure your default profile has proper access
export AWS_PROFILE=your_profile_name

# Method 2: Using AWS credentials directly
# export AWS_ACCESS_KEY_ID=your_access_key
# export AWS_SECRET_ACCESS_KEY=your_secret_key
# export AWS_SESSION_TOKEN=your_session_token  # Optional, for temporary credentials

# Run setup
./setup.sh sonic
```

### Run the Client

**Option 1: Using the start script (recommended)**
```bash
./start_client.sh sonic
```

**Option 2: Manual start**
```bash
# Export environment variables (from setup output)
export AWS_REGION="us-east-1"

# AWS Authentication (choose one method):
# Set AWS_PROFILE environment variable OR ensure your default profile has proper access
export AWS_PROFILE=your_profile_name
# OR
# export AWS_ACCESS_KEY_ID=your_access_key
# export AWS_SECRET_ACCESS_KEY=your_secret_key
# export AWS_SESSION_TOKEN=your_session_token  # Optional

# Start the web client
python sonic/client/client.py --runtime-arn "<agent-arn-from-setup>"
```

The web client will:
1. Open automatically in your browser
2. Request microphone access
3. Enable real-time audio conversation with the AI

### Features

- **Real-time audio streaming** - Speak naturally and get immediate responses
- **Voice selection** - Choose from multiple voices across different languages (English, French, Italian, German, Spanish)
- **Dynamic voice switching** - Change voices during an active conversation
- **Interruption support** - Barge-in capability to interrupt the assistant mid-response
- **Tool integration** - Includes a sample `getDateTool` that responds to questions like "What time is it?" or "What day is today?"
- **Web-based UI** - No installation required, works in any modern browser
- **Session management** - Automatic session handling and audio buffering
- **Event logging** - See all WebSocket events in real-time with filtering capability
### Sample Tool: getDateTool

The Sonic implementation includes a working example of tool integration. The `getDateTool` demonstrates how to:
- Define a tool in the client configuration ([`sonic/client/sonic-client.html`](sonic/client/sonic-client.html#L617-L628))
- Send tool configuration during session setup ([`sonic/client/sonic-client.html`](sonic/client/sonic-client.html#L773-L784))
- Handle tool invocations on the server ([`sonic/websocket/s2s_session_manager.py`](sonic/websocket/s2s_session_manager.py#L339-L342))
- Return results back to the conversation flow

**Try it:** Ask questions like "What time is it?" or "What's today's date?" and the assistant will invoke the tool to get the current UTC date and time.

### Cleanup

```bash
./cleanup.sh sonic
```

---

## Strands Sample - Framework-Based Implementation

This sample demonstrates using the **Strands BidiAgent framework** for real-time audio conversations with Amazon Nova Sonic. Strands provides a high-level abstraction that simplifies bidirectional streaming, automatic session management, and tool integration.

**Architecture:**

The Strands implementation uses the BidiAgent framework to handle the complexity of WebSocket communication, audio streaming, and tool orchestration automatically.

**Best for:** Rapid prototyping and production applications that benefit from framework abstractions while maintaining full Nova Sonic capabilities.

### Setup

```bash
# Required
export ACCOUNT_ID=your_aws_account_id

# Optional - customize these or use defaults
export AWS_REGION=us-east-1
export IAM_ROLE_NAME=WebSocketStrandsAgentRole
export ECR_REPO_NAME=agentcore_strands_images
export AGENT_NAME=websocket_strands_agent

# AWS Authentication (choose one method):

# Method 1: Using AWS Profile (recommended)
# Set AWS_PROFILE environment variable OR ensure your default profile has proper access
export AWS_PROFILE=your_profile_name

# Method 2: Using AWS credentials directly
# export AWS_ACCESS_KEY_ID=your_access_key
# export AWS_SECRET_ACCESS_KEY=your_secret_key
# export AWS_SESSION_TOKEN=your_session_token  # Optional, for temporary credentials

# Run setup
./setup.sh strands
```

### Run the Client

**Option 1: Using the start script (recommended)**
```bash
./start_client.sh strands
```

**Option 2: Manual start**
```bash
# Export environment variables (from setup output)
export AWS_REGION="us-east-1"

# AWS Authentication (choose one method):
# Set AWS_PROFILE environment variable OR ensure your default profile has proper access
export AWS_PROFILE=your_profile_name
# OR
# export AWS_ACCESS_KEY_ID=your_access_key
# export AWS_SECRET_ACCESS_KEY=your_secret_key
# export AWS_SESSION_TOKEN=your_session_token  # Optional

# Start the web client
python strands/client/client.py --runtime-arn "<agent-arn-from-setup>"
```

The web client will:
1. Open automatically in your browser
2. Request microphone access
3. Enable real-time audio conversation with the AI

### Sample Tool: Calculator

The Strands implementation includes a calculator tool that demonstrates framework-based tool integration. The tool can perform basic arithmetic operations.

**Try it:** Ask questions like "What is 25 times 4?" or "Calculate 100 divided by 5" and the assistant will use the calculator tool.

### Key Differences from Sonic Sample

- **Abstraction level:** Strands provides higher-level APIs vs. Sonic's direct protocol control
- **Code complexity:** Strands requires less boilerplate for session management
- **Tool integration:** Framework handles tool orchestration automatically
- **Flexibility:** Sonic offers more fine-grained control over events and responses

### Cleanup

```bash
./cleanup.sh strands
```

---

## Echo Sample - WebSocket Testing

A simple echo server for testing WebSocket connectivity and authentication.

### Setup

```bash
# Required
export ACCOUNT_ID=your_aws_account_id

# Optional - customize these or use defaults
export AWS_REGION=us-east-1
export IAM_ROLE_NAME=WebSocketEchoAgentRole
export DOCKER_REPO_NAME=agentcore_echo_images
export AGENT_NAME=websocket_echo_agent

# AWS Authentication (choose one method):

# Method 1: Using AWS Profile (recommended)
# Set AWS_PROFILE environment variable OR ensure your default profile has proper access
export AWS_PROFILE=your_profile_name

# Method 2: Using AWS credentials directly
# export AWS_ACCESS_KEY_ID=your_access_key
# export AWS_SECRET_ACCESS_KEY=your_secret_key
# export AWS_SESSION_TOKEN=your_session_token  # Optional, for temporary credentials

# Run setup
./setup.sh echo
```

### Run the Client

**Option 1: Using the start script (recommended)**
```bash
./start_client.sh echo
```

**Option 2: Manual start**
```bash
# Export environment variables (from setup output)
export AWS_REGION="us-east-1"

# AWS Authentication (choose one method):
# Set AWS_PROFILE environment variable OR ensure your default profile has proper access
export AWS_PROFILE=your_profile_name
# OR
# export AWS_ACCESS_KEY_ID=your_access_key
# export AWS_SECRET_ACCESS_KEY=your_secret_key
# export AWS_SESSION_TOKEN=your_session_token  # Optional

# Test with SigV4 headers authentication
python echo/client/client.py --runtime-arn "<agent-arn-from-setup>" --auth-type headers

# Test with SigV4 query parameters
python echo/client/client.py --runtime-arn "<agent-arn-from-setup>" --auth-type query
```
### Features

- **Simple echo** - Sends a message and verifies the echo response
- **Multiple auth methods** - Test SigV4 headers or query parameters
- **Connection testing** - Verify WebSocket connectivity
- **Minimal dependencies** - Great for debugging

### Expected Output

```
WebSocket connected
Sent: {"msg": "Hello, World! Echo Test"}
Received: {"msg": "Hello, World! Echo Test"}
Echo test PASSED
```

### Cleanup

```bash
./cleanup.sh echo
```

---

## How Deployment Works

The `setup.sh` script automates the complete deployment:

1. **Prerequisites Check** - Validates jq, Python 3, Docker, and AWS CLI are installed
2. **Python Environment** - Creates a virtual environment and installs dependencies
3. **Docker Build & Push** - Builds ARM64 container image and pushes to Amazon ECR
4. **IAM Role** - Creates role with permissions for ECR, CloudWatch, Bedrock, and X-Ray
5. **Agent Runtime** - Deploys the WebSocket server to Bedrock AgentCore
6. **Configuration** - Saves deployment details to `setup_config.json` for cleanup

After deployment, you'll have an ECR repository, IAM role, running agent runtime, and configuration file for easy cleanup.

---

## Files Structure

```
.
├── setup.sh                       # Unified setup script (takes folder parameter)
├── start_client.sh                # Unified client starter (takes folder parameter)
├── cleanup.sh                     # Unified cleanup script (takes folder parameter)
├── requirements.txt               # Python dependencies
├── websocket_helpers.py           # Shared WebSocket utilities (SigV4 auth, presigned URLs)
├── agent_role.json               # IAM role policy template
├── trust_policy.json             # IAM trust policy
│
├── sonic/                        # Sonic sample (native implementation)
│   ├── client/                   # Web-based client
│   │   ├── sonic-client.html     # HTML UI with voice selection
│   │   ├── client.py             # Web server
│   │   └── requirements.txt      # Client dependencies
│   ├── websocket/                # Server implementation
│   │   ├── server.py             # Sonic WebSocket server
│   │   ├── s2s_session_manager.py # Session management
│   │   ├── s2s_events.py         # Event handling
│   │   ├── Dockerfile            # Container definition
│   │   └── requirements.txt      # Server dependencies
│   └── setup_config.json         # Generated by setup.sh
│
├── strands/                      # Strands sample (framework-based)
│   ├── client/                   # Web-based client
│   │   ├── strands-client.html   # HTML UI
│   │   ├── client.py             # Web server
│   │   └── requirements.txt      # Client dependencies
│   ├── websocket/                # Server implementation
│   │   ├── server.py             # Strands BidiAgent server
│   │   ├── Dockerfile            # Container definition
│   │   └── requirements.txt      # Server dependencies
│   └── setup_config.json         # Generated by setup.sh
│
└── echo/                         # Echo sample (testing)
    ├── client/                   # CLI client
    │   └── client.py             # Echo test client
    ├── websocket/                # Server implementation
    │   ├── server.py             # Echo WebSocket server
    │   ├── Dockerfile            # Container definition
    │   └── requirements.txt      # Server dependencies
    └── setup_config.json         # Generated by setup.sh
```

---