# Device Management Chat Application

A FastAPI-based chat application that interfaces with AWS Bedrock AgentCore runtime to provide a user-friendly web interface for the Device Management system. The application features real-time chat, AWS Cognito authentication, and Docker deployment.

## Features

- **Real-time Chat Interface**: WebSocket-based streaming responses from the Device Management Agent
- **AWS Cognito Authentication**: Secure user authentication and session management
- **Responsive Design**: Works on desktop and mobile devices
- **Docker Support**: Easy deployment with Docker Compose
- **Session Management**: Maintains conversation context across interactions
- **Streaming Response Handling**: Processes and displays real-time agent responses

## Architecture

```
├── main.py                 # FastAPI application with WebSocket endpoints
├── auth.py                 # AWS Cognito authentication module
├── templates/              # HTML templates
│   ├── chat.html          # Main chat interface
│   ├── login.html         # Cognito OAuth login page
│   └── simple_login.html  # Simple authentication form
├── static/                 # Static assets
│   ├── css/styles.css     # Application styling
│   ├── js/                # JavaScript files
│   └── img/aws-logo.svg   # AWS branding
├── Dockerfile             # Container configuration
├── docker-compose.yml     # Multi-container orchestration
└── requirements.txt       # Python dependencies
```

## Prerequisites

- **Python 3.12** (recommended)
- **AWS CLI** configured with appropriate credentials
- **Docker & Docker Compose** (for containerized deployment)
- **AWS Bedrock AgentCore** access
- **AWS Cognito User Pool** (for authentication)

## Environment Configuration

Create a `.env` file based on `.env.example`:

```bash
# AWS Configuration
AWS_REGION=us-west-2

# Agent Runtime ARN
AGENT_ARN=arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/your-agent-name

# Cognito Authentication (Optional)
COGNITO_DOMAIN=your-domain.auth.us-west-2.amazoncognito.com
COGNITO_CLIENT_ID=your-client-id
COGNITO_CLIENT_SECRET=your-client-secret
COGNITO_REDIRECT_URI=http://localhost:5001/auth/callback
COGNITO_LOGOUT_URI=http://localhost:5001/logout
COGNITO_USER_POOL_ID=us-west-2_YourPoolId
```

## Installation & Setup

### Option 1: Docker Deployment (Recommended)

1. **Clone and navigate to the project**:
   ```bash
   cd frontend
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

3. **Build and run with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

4. **Access the application**:
   - Open http://localhost:5001
   - Login with your credentials
   - Start chatting with the Device Management Agent

### Option 2: Local Development

1. **Setup Python environment**:
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   # Development server with auto-reload
   uvicorn main:app --host 0.0.0.0 --port 5001 --reload
   ```

### Option 3: Automated Setup

Use the provided setup script:
```bash
chmod +x setup_and_run.sh
./setup_and_run.sh
```

## Key Files Description

### Core Application Files

- **`main.py`**: Main FastAPI application with WebSocket endpoints, streaming response handling, and session management
- **`auth.py`**: AWS Cognito integration for user authentication and authorization

### Configuration Files

- **`requirements.txt`**: Python package dependencies including FastAPI, boto3, WebSockets
- **`Dockerfile`**: Container image configuration for Python 3.12 slim
- **`docker-compose.yml`**: Multi-container orchestration with volume mounts for AWS credentials
- **`.env.example`**: Template for environment variables

### Utilities & Scripts

- **`setup_and_run.sh`**: Automated setup and deployment script

### Frontend Assets

- **`templates/chat.html`**: Main chat interface with WebSocket integration
- **`templates/login.html`**: Cognito OAuth login page
- **`templates/simple_login.html`**: Alternative simple login form
- **`static/css/styles.css`**: Application styling and responsive design
- **`static/img/aws-logo.svg`**: AWS branding assets

## Usage Examples

Once the application is running, you can interact with the Device Management system:

### Device Management Commands
- **"List all devices"** - Display all devices in the system
- **"Show settings for device DEV001"** - Get specific device configuration
- **"List WiFi networks for Living Room Router"** - Show available networks
- **"Update WiFi SSID to MyNewNetwork on device DEV001"** - Modify device settings
- **"Show device status for DG-100005"** - Check device connectivity and status

### System Information
- **"Show device statistics"** - Get system overview
- **"List devices by status"** - Filter devices by connection status
- **"Show firmware versions"** - Display firmware information across devices

## API Endpoints

### WebSocket Endpoints
- **`/ws/{client_id}`**: Real-time chat communication with streaming responses

### HTTP Endpoints
- **`GET /`**: Main chat interface (requires authentication)
- **`GET /simple-login`**: Simple authentication form
- **`POST /simple-login`**: Process simple login
- **`GET /auth/login`**: Initiate Cognito OAuth flow
- **`GET /auth/callback`**: Handle Cognito OAuth callback
- **`GET /logout`**: User logout and session cleanup

## Troubleshooting

### Common Issues

1. **Agent Connection Errors**:
   - Verify AGENT_ARN is correct in `.env`
   - Check AWS credentials and permissions
   - Ensure Bedrock AgentCore access

2. **Authentication Issues**:
   - Verify Cognito configuration in `.env`
   - Check redirect URIs match Cognito settings
   - Validate user pool and client configuration

3. **Docker Issues**:
   ```bash
   docker-compose logs --tail=50
   ```
   - Check container logs for errors
   - Verify AWS credentials mount
   - Ensure port 5001 is available

4. **Streaming Response Problems**:
   - Check WebSocket connection in browser dev tools
   - Verify agent response format
   - Review parsing logic in `main.py`

### Debug Mode

Enable debug logging by setting:
```bash
export PYTHONPATH=.
export LOG_LEVEL=DEBUG
```

## Security Considerations

- **AWS Credentials**: Never commit credentials to version control
- **Session Security**: Uses secure random session keys
- **CORS Configuration**: Configured for development (adjust for production)
- **Authentication**: Supports both Cognito OAuth and simple auth modes

## Development

### Adding New Features

1. **Backend Changes**: Modify `main.py` for new endpoints or WebSocket handlers
2. **Frontend Changes**: Update templates and static files
3. **Authentication**: Extend `auth.py` for additional auth providers
4. **Testing**: Add tests to verify new functionality

### Deployment

For production deployment:

1. **Update CORS settings** in `main.py`
2. **Configure proper SSL/TLS** certificates
3. **Set production environment variables**
4. **Use production-grade WSGI server** (e.g., Gunicorn)
5. **Implement proper logging and monitoring**

## Support

For issues and questions:
- Check the troubleshooting section above
- Review application logs: `docker-compose logs`
- Verify AWS permissions and configuration

## License

This project is part of the AWS Device Management system samples.
