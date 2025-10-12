# Customer Support Assistant - React Frontend

> A modern React application for the Customer Support Assistant, featuring real-time chat with AWS Bedrock AgentCore, AWS Cognito OAuth2 authentication, and a sleek dark-themed UI.

## ✨ Features

- **Modern React 19** - Built with the latest React and hooks
- **AWS Cognito OAuth2** - Secure authentication with PKCE flow
- **Real-time Streaming Chat** - Live responses from Bedrock AgentCore
- **Tailwind CSS & shadcn/ui** - Beautiful, responsive UI components
- **Dark Theme** - Professional dark mode interface matching Streamlit design
- **Responsive Design** - Works seamlessly on desktop and mobile
- **Clickable URLs** - Automatic link detection in messages
- **Performance Optimized** - Memoization and efficient re-renders

## 🏗 Architecture

This application consists of two parts:

1. **Express Backend Server** (Port 8501): Handles SSM Parameter Store access and serves configuration API
2. **React Frontend** (Port 5173 in dev): The user interface built with React, Vite, and Tailwind CSS

The backend server fetches AWS configuration from SSM Parameter Store since the browser cannot access AWS services directly without credentials.

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ and npm
- AWS credentials configured (the backend server needs access to SSM Parameter Store)
- Customer Support VPC CloudFormation stack deployed

### Installation

```bash
# Install dependencies
npm install
```

### Development - Option 1: Run Both Servers (Recommended)

```bash
# Start both backend (8501) and frontend (5173) concurrently
npm run dev:full
```

Then open your browser to: **http://localhost:5173**

### Development - Option 2: Run Servers Separately

**Terminal 1 - Backend Server:**
```bash
npm run dev:server  # Runs on port 8501
```

**Terminal 2 - Frontend Dev Server:**
```bash
npm run dev  # Runs on port 5173
```

Then open your browser to: **http://localhost:5173**

### Production Build

```bash
# Build the React application
npm run build

# Start production server (serves both API and static files on port 8501)
npm start
```

Then open your browser to: **http://localhost:8501**

### Custom Stack Name

Pass a custom CloudFormation stack name via URL parameter (include environment suffix):

```
# Dev environment
http://localhost:5173/?stack=customer-support-vpc-dev

# Production environment
http://localhost:5173/?stack=customer-support-vpc-prod

# Custom stack name
http://localhost:5173/?stack=my-custom-stack-test
```

## 📦 Project Structure

```
frontend/
├── server.js               # Express backend server (SSM access)
├── src/
│   ├── components/          # React components
│   │   ├── ui/             # shadcn/ui base components
│   │   ├── ChatContainer.tsx
│   │   ├── ChatInput.tsx
│   │   ├── ChatMessage.tsx
│   │   └── ...
│   ├── hooks/              # Custom React hooks (useAuth, useChat)
│   ├── services/           # API services (AWS SDK, Auth, Chat)
│   ├── lib/                # Utilities
│   ├── types/              # TypeScript types
│   └── App.jsx             # Main app component
├── package.json
├── tailwind.config.js
└── vite.config.js
```

## 🛠 Development Scripts

```bash
# Run both servers concurrently (recommended)
npm run dev:full

# Run backend server only (port 8501)
npm run dev:server

# Run frontend dev server only (port 5173)
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Preview production build
npm run preview

# Lint code
npm run lint
```

## 🎨 Features Comparison with Streamlit App

| Feature | Streamlit | React |
|---------|-----------|-------|
| Framework | Python/Streamlit | React 19/Vite |
| Authentication | Cookie-based | localStorage + React Context |
| Streaming | Server-side generator | Browser Fetch API streams |
| State Management | st.session_state | React hooks + Context |
| Styling | Custom CSS | Tailwind CSS + shadcn/ui |
| Type Safety | Python types | TypeScript ready |

## 🔧 Configuration

### Backend Server API

The Express backend provides these endpoints:

- `GET /api/config?stack={stackName}` - Fetches Cognito configuration from SSM
- `GET /api/health` - Health check endpoint

### Required SSM Parameters

The backend server fetches these parameters:

- `/app/customersupportvpc/agentcore/cognito_domain` - Cognito domain for authentication
- `/app/customersupportvpc/agentcore/web_client_id` - Cognito web client ID

### Environment Variables

Create a `.env` file (optional):

```bash
# AWS Region
AWS_REGION=us-west-2

# Stack name with environment suffix (can also be passed via URL parameter)
# Examples: customer-support-vpc-dev, customer-support-vpc-prod, customer-support-vpc-test
VITE_STACK_NAME=customer-support-vpc-dev
```

Agent configuration is loaded from CloudFormation stack outputs.

## 🐛 Troubleshooting

### Blank page or loading forever

1. Check that the backend server is running on port 8501
2. Verify AWS credentials are configured properly: `aws configure`
3. Check browser console for errors
4. Verify SSM parameters exist in your AWS account

### AWS Credentials Error

Ensure AWS credentials are configured for the backend server:

```bash
aws configure
```

### OAuth Redirect Mismatch

Ensure Cognito redirect URI matches:
- Development: `http://localhost:5173/`
- Production: Your production URL

### Configuration API Error

Verify SSM parameters exist:

```bash
aws ssm get-parameter --name /app/customersupportvpc/agentcore/cognito_domain
aws ssm get-parameter --name /app/customersupportvpc/agentcore/web_client_id
```

### Build Errors

```bash
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
```

## 📝 License

For educational and experimental purposes only.
