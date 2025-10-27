"""
Sample OAuth2 Callback Server for Authorization Code flow ( 3LO ) with Amazon Bedrock AgentCore Identity

This module implements a local callback server that handles OAuth2 3-legged (3LO) authentication flows
for AgentCore Identity. It serves as an intermediary between the user's browser, external OAuth providers
(like Google, Github etc), and the AgentCore Identity service.

Key Components:
- FastAPI server running on localhost:9090
- Handles OAuth2 callback redirects from external providers
- Manages user token storage and session completion with proper session isolation
- Provides health check endpoint for readiness verification

Usage Context:
This server is used in conjunction with agents running on AgentCore Runtime that need to access external resources
(like Google Calendar, Github repos) on behalf of authenticated users. The typical flow involves:
1. Agent requests access to external resource
2. User is redirected to OAuth provider for consent
3. Provider redirects back to this callback server
4. Server completes the authentication flow with AgentCore Identity

"""

import time
import uuid
import uvicorn
import logging
import argparse
import requests
import threading

from datetime import timedelta, datetime
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from bedrock_agentcore.services.identity import IdentityClient, UserTokenIdentifier

# Configuration constants for the OAuth2 callback server
OAUTH2_CALLBACK_SERVER_PORT = 9090  # Port where the callback server listens
PING_ENDPOINT = "/ping"  # Health check endpoint
OAUTH2_CALLBACK_ENDPOINT = "/oauth2/callback"  # OAuth2 callback endpoint for provider redirects
USER_IDENTIFIER_ENDPOINT = "/userIdentifier/token"  # Endpoint to store user token identifiers

# Session timeout in minutes
SESSION_TIMEOUT_MINUTES = 30

logger = logging.getLogger(__name__)


class SessionStore:
    """
    Thread-safe session store for managing user token identifiers.
    
    This class provides session isolation by storing user tokens with unique session IDs
    and automatic cleanup of expired sessions to prevent memory leaks.
    """
    
    def __init__(self, timeout_minutes: int = SESSION_TIMEOUT_MINUTES):
        self._sessions: Dict[str, Dict] = {}
        self._lock = threading.RLock()
        self._timeout_minutes = timeout_minutes
    
    def create_session(self, user_token_identifier: UserTokenIdentifier) -> str:
        """
        Create a new session with a unique session ID.
        
        Args:
            user_token_identifier: User token identifier to store
            
        Returns:
            str: Unique session ID
        """
        session_id = str(uuid.uuid4())
        
        with self._lock:
            self._sessions[session_id] = {
                'user_token_identifier': user_token_identifier,
                'created_at': datetime.now(),
                'expires_at': datetime.now() + timedelta(minutes=self._timeout_minutes)
            }
            
        # Clean up expired sessions
        self._cleanup_expired_sessions()
        
        logger.info(f"Created session for user authentication")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[UserTokenIdentifier]:
        """
        Retrieve user token identifier for a given session ID.
        
        Args:
            session_id: Session ID to look up
            
        Returns:
            UserTokenIdentifier if session exists and is valid, None otherwise
        """
        with self._lock:
            session_data = self._sessions.get(session_id)
            
            if not session_data:
                logger.warning(f"Session not found")
                return None
            
            # Check if session has expired
            if datetime.now() > session_data['expires_at']:
                logger.warning(f"Session has expired")
                del self._sessions[session_id]
                return None
            
            return session_data['user_token_identifier']
    
    def remove_session(self, session_id: str) -> bool:
        """
        Remove a session after successful OAuth completion.
        
        Args:
            session_id: Session ID to remove
            
        Returns:
            bool: True if session was removed, False if not found
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"Removed session after successful OAuth completion")
                return True
            return False
    
    def _cleanup_expired_sessions(self):
        """Clean up expired sessions to prevent memory leaks."""
        current_time = datetime.now()
        expired_sessions = []
        
        with self._lock:
            for session_id, session_data in self._sessions.items():
                if current_time > session_data['expires_at']:
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self._sessions[session_id]
                logger.info(f"Cleaned up expired session.")
    
    def get_session_count(self) -> int:
        """Get the current number of active sessions."""
        with self._lock:
            return len(self._sessions)


class OAuth2CallbackServer:
    """
    OAuth2 Callback Server for handling 3-legged OAuth flows with AgentCore Identity.
    
    This server acts as a local callback endpoint that external OAuth providers (like Google, Github)
    redirect to after user authorization. It manages the completion of the OAuth flow by
    coordinating with AgentCore Identity service.
    
    SECURITY IMPROVEMENT:
    This version implements proper session isolation using a SessionStore to prevent
    race conditions when multiple users authenticate simultaneously.
    """
    
    def __init__(self, region: str):
        """
        Initialize the OAuth2 callback server.
        
        Args:
            region (str): AWS region where AgentCore Identity service is deployed
        """
        # Initialize AgentCore Identity client for the specified region
        self.identity_client = IdentityClient(region=region)
        
        # Initialize session store for proper session isolation
        self.session_store = SessionStore()
        
        # Create FastAPI application instance
        self.app = FastAPI()
        
        # Configure all HTTP routes
        self._setup_routes()

    def _setup_routes(self):
        """
        Configure FastAPI routes for the OAuth2 callback server.
        
        Sets up three endpoints:
        1. POST /userIdentifier/token - Store user token identifier with session isolation
        2. GET /ping - Health check endpoint
        3. GET /oauth2/callback - OAuth2 callback handler for provider redirects
        """
        
        @self.app.post(USER_IDENTIFIER_ENDPOINT)
        async def _store_user_token(request_data: dict):
            """
            Store user token identifier with proper session isolation.
            
            This endpoint creates a unique session for each user's OAuth flow,
            preventing race conditions when multiple users authenticate simultaneously.
            
            Args:
                request_data: Dictionary containing user token information
                                           
            Returns:
                dict: Response containing the session ID for this user's OAuth flow
            """
            user_token = request_data.get("user_token")
            if not user_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing user_token in request",
                )
            
            # Create UserTokenIdentifier from the provided token
            user_token_identifier = UserTokenIdentifier(user_token=user_token)
            session_id = self.session_store.create_session(user_token_identifier)
            
            return {
                "status": "success",
                "session_id": session_id,
                "message": "User token stored with session isolation",
                "active_sessions": self.session_store.get_session_count()
            }

        @self.app.get(PING_ENDPOINT)
        async def _handle_ping():
            """
            Health check endpoint to verify server readiness.
            
            Returns:
                dict: Status response with session information
            """
            return {
                "status": "success",
                "active_sessions": self.session_store.get_session_count()
            }

        @self.app.get(OAUTH2_CALLBACK_ENDPOINT)
        async def _handle_oauth2_callback(session_id: str, user_session: str):
            """
            Handle OAuth2 callback from external providers with session isolation.
            
            This endpoint uses session-based isolation to prevent race conditions
            when multiple users authenticate simultaneously.
            
            Args:
                session_id (str): Session identifier from OAuth provider redirect
                user_session (str): User session ID for session isolation
                
            Returns:
                dict: Success message indicating OAuth flow completion
                
            Raises:
                HTTPException: If session_id is missing or user session not found
            """
            # Validate that session_id parameter is present
            if not session_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing session_id query parameter",
                )

            # Validate that user_session parameter is present
            if not user_session:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing user_session query parameter",
                )

            # Get user token identifier from session store
            user_token_identifier = self.session_store.get_session(user_session)
            
            if not user_token_identifier:
                logger.error(f"User session {user_session[:8]}... not found or expired")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired user session",
                )
            
            # Complete the OAuth flow
            self.identity_client.complete_resource_token_auth(
                session_uri=session_id, user_identifier=user_token_identifier
            )
            
            # Clean up the session after successful completion
            self.session_store.remove_session(user_session)
            
            logger.info(f"OAuth flow completed successfully for session {user_session[:8]}...")

            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>OAuth2 Success</title>
                <style>
                    body {
                        margin: 0;
                        padding: 0;
                        height: 100vh;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        font-family: Arial, sans-serif;
                        background-color: #f5f5f5;
                    }
                    .container {
                        text-align: center;
                        padding: 2rem;
                        background-color: white;
                        border-radius: 8px;
                        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                    }
                    h1 {
                        color: #28a745;
                        margin: 0;
                    }
                    .session-info {
                        margin-top: 1rem;
                        font-size: 0.9em;
                        color: #666;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Completed OAuth2 3LO flow successfully</h1>
                    <div class="session-info">
                        Session isolation: Enabled
                    </div>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html_content, status_code=200)

    def get_app(self) -> FastAPI:
        """
        Get the configured FastAPI application instance.
        
        Returns:
            FastAPI: The configured application with all routes set up
        """
        return self.app


def get_oauth2_callback_url() -> str:
    """
    Generate the full OAuth2 callback URL for external providers.
    
    This URL is registered with external OAuth providers (like Google, Github) as the redirect URI.
    After user authorization, the provider will redirect the user's browser to this URL
    with the session_id parameter.
    
    Returns:
        str: Complete callback URL (e.g., "http://localhost:9090/oauth2/callback")
    
    Usage:
        This URL is typically used when:
        1. Configuring OAuth2 credential providers in AgentCore Identity
        2. Registering redirect URIs with external OAuth providers
        3. Setting up workload identity allowed return URLs
    """
    return f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}{OAUTH2_CALLBACK_ENDPOINT}"


def store_token_in_oauth2_callback_server(user_token_value: str) -> Optional[str]:
    """
    Store user token identifier in the running OAuth2 callback server with session isolation.
    
    This function sends a POST request to the callback server to store the user's
    token identifier before initiating the OAuth flow. The token identifier is
    used to bind the OAuth session to the specific user.
    
    Args:
        user_token_value (str): User token (typically JWT access token from Cognito)
                               used to identify the user in the OAuth flow
    
    Returns:
        Optional[str]: Session ID for the user's OAuth flow
    
    Usage Context:
        Called before starting OAuth flow to ensure the callback server knows
        which user the OAuth session belongs to. This is critical for proper
        session binding in multi-user scenarios.
        
    Example:
        bearer_token = reauthenticate_user(client_id)
        session_id = store_token_in_oauth2_callback_server(bearer_token)
    """
    if not user_token_value:
        logger.error("Ignoring: invalid user_token provided...")
        return None
    
    try:
        response = requests.post(
            f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}{USER_IDENTIFIER_ENDPOINT}",
            json={"user_token": user_token_value},
            timeout=5,
        )
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                if response_data and isinstance(response_data, dict):
                    session_id = response_data.get('session_id')
                    if session_id:
                        logger.info(f"Token stored with session isolation.")
                        return session_id
                    else:
                        logger.error("Server response missing session_id")
                        return None
                else:
                    logger.error("Server returned invalid JSON response")
                    return None
            except ValueError as e:
                logger.error(f"Failed to parse server response as JSON: {e}")
                return None
        else:
            logger.error(f"Failed to store token: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error storing token in callback server: {e}")
        return None


def wait_for_oauth2_server_to_be_ready(
    duration: timedelta = timedelta(seconds=40),
) -> bool:
    """
    Wait for the OAuth2 callback server to become ready and responsive.
    
    This function polls the server's health check endpoint until it responds
    successfully or the timeout is reached. It's essential to ensure the server
    is ready before starting OAuth flows.
    
    Args:
        duration (timedelta): Maximum time to wait for server readiness
                             Defaults to 40 seconds
    
    Returns:
        bool: True if server becomes ready within timeout, False otherwise
    
    Usage Context:
        Called after starting the OAuth2 callback server process to ensure
        it's ready to handle OAuth callbacks before proceeding with agent
        invocations that might trigger OAuth flows.
        
    Example:
        # Start server process
        server_process = subprocess.Popen([...])
        
        # Wait for readiness
        if wait_for_oauth2_server_to_be_ready():
            # Proceed with OAuth-enabled operations
            invoke_agent()
        else:
            # Handle server startup failure
            server_process.terminate()
    """
    logger.info("Waiting for OAuth2 callback server to be ready...")
    timeout_in_seconds = duration.seconds

    start_time = time.time()
    while time.time() - start_time < timeout_in_seconds:
        try:
            # Ping the server's health check endpoint
            response = requests.get(
                f"http://localhost:{OAUTH2_CALLBACK_SERVER_PORT}{PING_ENDPOINT}",
                timeout=2,
            )
            if response.status_code == status.HTTP_200_OK:
                response_data = response.json()
                active_sessions = response_data.get('active_sessions', 0)
                logger.info(f"OAuth2 callback server is ready! Active sessions: {active_sessions}")
                return True
        except requests.exceptions.RequestException:
            # Server not ready yet, continue waiting
            pass

        time.sleep(2)
        elapsed = int(time.time() - start_time)
        
        # Log progress every 10 seconds to show we're still waiting
        if elapsed % 10 == 0 and elapsed > 0:
            logger.info(f"Still waiting... ({elapsed}/{timeout_in_seconds}s)")

    logger.error(
        f"Timeout: OAuth2 callback server not ready after {timeout_in_seconds} seconds"
    )
    return False


def main():
    """
    Main entry point for running the OAuth2 callback server as a standalone application.
    
    Parses command line arguments and starts the FastAPI server using uvicorn.
    The server runs on localhost:9090 and handles OAuth2 callbacks for the specified
    AWS region with proper session isolation.
    
    Command Line Usage:
        python oauth2_callback_server_fixed.py --region us-east-1
        
    The server will run until manually terminated and will handle OAuth2 callbacks
    for any AgentCore agents in the specified region with session isolation enabled.
    """
    parser = argparse.ArgumentParser(description="OAuth2 Callback Server with Session Isolation")
    parser.add_argument(
        "-r", "--region", type=str, required=True, help="AWS Region (e.g. us-east-1)"
    )

    args = parser.parse_args()
    oauth2_callback_server = OAuth2CallbackServer(region=args.region)

    logger.info("Starting OAuth2 callback server with session isolation enabled")
    
    # Start the FastAPI server using uvicorn
    # Server runs on localhost only for security (not exposed externally)
    uvicorn.run(
        oauth2_callback_server.get_app(),
        host="127.0.0.1",
        port=OAUTH2_CALLBACK_SERVER_PORT,
    )


if __name__ == "__main__":
    main()
