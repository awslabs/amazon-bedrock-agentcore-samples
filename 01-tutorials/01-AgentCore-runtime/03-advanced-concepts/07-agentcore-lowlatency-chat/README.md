# AgentCore Warmup Demo

A demonstration application showcasing how pre-emptive warmup of AgentCore runtime reduces latency in agentic chatbots.
AgentCore Runtime can deploy agent code using code deployment or container deployment.
When AgentCore Runtime receives the first invocation, it allocates a new VM. In case of container deployment there are 10 VM in a warm pool, and up to 10 new sessions are served from that pool, with sub-second cold starts. From the 11th session, new VMs must be allocated, the container downloaded and started. This will make the cold start longer and dependent on the size of the container.
For code deployment, AgentCore Runtime manages a larger pool of instances and only pushes the agent code. This ensure a more consistent startup time and higher session per second limit, but the cold start will be around 2-3 seconds.

For agentic chat applications, a low TTFT is paramount for a good user experience. This sample show a pattern to pre-emptively warmup agent core instances so that when the user actually send the message to the agent, the VM has already been initialized.

## Features

- **Normal Mode**: Agent invoked only when user sends messages (cold start latency)
- **Optimized Mode**: Agent pre-warmed with ping request on session creation (reduced latency)
- Real-time latency tracking and comparison
- Cognito authentication integration
- React + TypeScript frontend with Tailwind CSS
- Express backend serving configuration

## Setup

1. Install dependencies:

```bash
pnpm install
```

2. Run `uvx --from bedrock-agentcore-starter-toolkit agentcore identity setup-cognito`

3. Run `uxv --from bedrock-agentcore-starter-toolkit agentcore configure`

- Select the `agent/main.py` as agent code.
- Give a name to your agent
- You can choose code deploy or container deployment to test both strategies. For container deployment, see what happens up to 10 sessions, and what happens on the 11th session.
- Setup OAuth authorization
  - use the discovery url and clientId from the `.agentcore_identity_cognito_user.json` file under the `runtime` section

4. Run `uxv --from bedrock-agentcore-starter-toolkit agentcore deploy`

5. Start the development server:

```bash
pnpm dev
```

This will start:

- Express server on http://localhost:3001
- Vite dev server on http://localhost:3000

## How It Works

### Normal Mode

- Agent is invoked with `{"prompt": "user_message"}` only when user presses Enter
- Experiences cold start latency on first invocation

### Optimized Mode

- Agent is pre-warmed with `{"ping": "now"}` when session is created
- Subsequent invocations have reduced latency due to warm runtime
- Warmup happens automatically when accessing chat or creating new session

## Architecture

- **Backend** (`server/index.js`): Express server that reads AgentCore configuration and exposes it via `/config.json`
- **Frontend** (`src/`): React + TypeScript application with:
  - Cognito authentication
  - Agent invocation with session management
  - Latency tracking and visualization
  - Mode comparison UI

## Configuration

The app reads configuration from:

- `.bedrock_agentcore.yaml`: Agent configuration including ARN and region
- `.agentcore_identity_cognito_user.json`: Cognito authentication credentials
