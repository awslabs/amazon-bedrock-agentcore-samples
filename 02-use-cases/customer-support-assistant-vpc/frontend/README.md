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

This is a single-page React application built with Vite and Tailwind CSS. The application uses AWS Amplify for authentication with AWS Cognito OAuth2, and communicates directly with AWS Bedrock AgentCore for chat functionality. Configuration is loaded from environment variables at build time.

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ and npm
- Customer Support VPC CloudFormation stack deployed
- Environment variables configured (see Configuration section)

### Installation

```bash
# Install dependencies
npm install
```

### Development

```bash
# Start development server on port 5173
npm run dev
```

Then open your browser to: **http://localhost:5173**

### Production Build

```bash
# Build the React application
npm run build

# Preview production build
npm start
```

Then open your browser to: **http://localhost:4173**

## 📦 Project Structure

```
frontend/
├── src/
│   ├── components/          # React components
│   │   ├── ui/             # shadcn/ui base components
│   │   ├── ChatContainer.tsx
│   │   ├── ChatInput.tsx
│   │   ├── ChatMessage.tsx
│   │   └── ...
│   ├── hooks/              # Custom React hooks (useChat)
│   ├── services/           # API services (AWS SDK, Chat)
│   ├── types/              # TypeScript types
│   ├── utils.ts            # Utility functions
│   ├── amplifyconfiguration.ts  # Amplify/Cognito config
│   └── App.jsx             # Main app component
├── package.json
├── tailwind.config.js
└── vite.config.js
```

## 🛠 Development Scripts

```bash
# Run frontend dev server (port 5173)
npm run dev

# Build for production
npm run build

# Start production preview server
npm start

# Preview production build
npm run preview
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

### Environment Variables

Create a `.env` file in the frontend directory with the following variables:

```bash
# AWS Region
VITE_AWS_REGION=us-west-2

# Cognito Configuration
VITE_COGNITO_DOMAIN=your-cognito-domain.auth.us-west-2.amazoncognito.com
VITE_COGNITO_USER_POOL_ID=us-west-2_XXXXXXXXX
VITE_COGNITO_USER_POOL_CLIENT_ID=your-client-id

# Bedrock Agent Configuration
VITE_AGENT_ARN=arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/your-runtime-id
```

You can obtain these values from your CloudFormation stack outputs and SSM Parameter Store.

## 🐛 Troubleshooting

### Blank page or loading forever

1. Check browser console for errors
2. Verify all required environment variables are set in `.env` file
3. Ensure Cognito configuration is correct
4. Verify the Agent ARN is valid

### Authentication Issues

Ensure Cognito redirect URI is configured correctly in your Cognito User Pool:
- Development: `http://localhost:5173/`
- Production: Your production URL

### Missing Configuration Error

Verify all required environment variables are set:

```bash
# Check your .env file contains:
VITE_AWS_REGION
VITE_COGNITO_DOMAIN
VITE_COGNITO_USER_POOL_ID
VITE_COGNITO_USER_POOL_CLIENT_ID
VITE_AGENT_ARN
```

### Build Errors

```bash
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
```

## 📝 License

For educational and experimental purposes only.
