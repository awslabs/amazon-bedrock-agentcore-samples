#!/usr/bin/env python3
"""
MCP Client using Standard OAuth Flow with AWS Cognito

This script provides multiple OAuth authentication methods for connecting to
MCP servers through AWS AgentCore Runtime.
"""

import asyncio
import os
import webbrowser
from urllib.parse import parse_qs, urlparse, urlencode, urljoin
import boto3
import httpx

from mcp import ClientSession
from mcp.client.auth import TokenStorage, OAuthClientProvider, OAuthTokenError
from mcp.client.streamable_http import streamablehttp_client, MCP_PROTOCOL_VERSION
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken, OAuthClientMetadata
import logging
from pydantic import ValidationError
from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

# For native SDK OAuth support
try:
    from pydantic import AnyUrl
except ImportError:
    print("⚠️  pydantic not available - native SDK mode will be limited")
    AnyUrl = str  # Fallback for systems without pydantic

# Try to load .env files automatically
try:
    from dotenv import load_dotenv

    # Try multiple .env file names
    for env_file in [".env.local", ".env"]:
        if os.path.exists(env_file):
            load_dotenv(env_file)
            print(f"📁 Loaded environment from {env_file}")
            break
except ImportError:
    # dotenv not available, user needs to manually load environment
    print(
        "💡 Hint: Install python-dotenv for automatic .env file loading: pip install python-dotenv"
    )
    print("   Or manually load environment: source .env.local")


class DebugTokenStorage(TokenStorage):
    """Debug token storage with detailed logging."""

    def __init__(self):
        self.tokens: OAuthToken | None = None
        self.client_info: OAuthClientInformationFull | None = None

    async def get_tokens(self) -> OAuthToken | None:
        """Get stored tokens."""
        if self.tokens:
            print(
                f"🔑 Retrieved tokens from storage: access_token={'*' * 20}... (expires: {getattr(self.tokens, 'expires_in', 'unknown')})"
            )
        else:
            print("❌ No tokens in storage")
        return self.tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Store tokens."""
        print(
            f"💾 Storing tokens: access_token={'*' * 20}... (type: {getattr(tokens, 'token_type', 'unknown')})"
        )
        self.tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Get stored client information."""
        if self.client_info:
            print(
                f"ℹ️  Retrieved client info: client_id={getattr(self.client_info, 'client_id', 'unknown')}"
            )
        return self.client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Store client information."""
        print(
            f"💾 Storing client info: client_id={getattr(client_info, 'client_id', 'unknown')}"
        )
        self.client_info = client_info


class OAuth2Handler:
    """Generic OAuth 2.0 handler with well-known endpoint discovery."""

    def __init__(self, discovery_url: str, client_id: str, client_secret: str = None):
        self.discovery_url = discovery_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = "http://localhost:3000"
        self.well_known_config = None

    async def discover_endpoints(self) -> dict:
        """Discover OAuth 2.0 endpoints using well-known configuration."""
        # Use the provided discovery URL directly - no assumptions about path
        well_known_url = self.discovery_url

        print(f"🔍 Discovering OAuth 2.0 endpoints from: {well_known_url}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(well_known_url, timeout=10.0)

                if response.status_code == 200:
                    config = response.json()
                    self.well_known_config = config

                    print("✅ Discovery successful!")
                    print(
                        f"   Authorization endpoint: {config.get('authorization_endpoint', 'Not found')}"
                    )
                    print(
                        f"   Token endpoint: {config.get('token_endpoint', 'Not found')}"
                    )
                    print(f"   Issuer: {config.get('issuer', 'Not found')}")
                    print(
                        f"   Supported scopes: {config.get('scopes_supported', 'Not listed')}"
                    )

                    return config
                else:
                    raise ValueError(f"Discovery failed: HTTP {response.status_code}")

            except Exception as e:
                print(f"❌ OAuth 2.0 discovery failed: {e}")
                print("🔄 Cannot discover endpoints from provided URL")
                print(
                    "💡 Please provide valid discovery URL or configure endpoints manually"
                )
                raise ValueError(f"Discovery failed and no fallback available: {e}")

    async def get_authorization_url(self) -> str:
        """Generate the authorization URL using discovered endpoints."""
        if not self.well_known_config:
            await self.discover_endpoints()

        auth_endpoint = self.well_known_config.get("authorization_endpoint")
        if not auth_endpoint:
            raise ValueError(
                "No authorization endpoint found in OAuth 2.0 configuration"
            )

        # Use standard OpenID Connect scopes, but allow override for specific providers
        default_scope = "openid email profile"

        # Special handling for AWS Cognito
        if (
            "cognito-idp" in self.discovery_url.lower()
            or "cognito" in self.discovery_url.lower()
            or "amazoncognito" in self.discovery_url.lower()
        ):
            default_scope = "openid email aws.cognito.signin.user.admin"
            print("🔧 Detected AWS Cognito - using Cognito-specific scopes")

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": default_scope,
            "state": "random_state_12345",  # In production, use a secure random state
        }

        auth_url = f"{auth_endpoint}?{urlencode(params)}"
        return auth_url

    async def exchange_code_for_tokens(self, authorization_code: str) -> dict:
        """Exchange authorization code for tokens using discovered endpoints."""
        if not self.well_known_config:
            await self.discover_endpoints()

        token_endpoint = self.well_known_config.get("token_endpoint")
        if not token_endpoint:
            raise ValueError("No token endpoint found in OAuth 2.0 configuration")

        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        print("🔄 Exchanging authorization code for tokens...")
        print(f"   Token endpoint: {token_endpoint}")
        print(f"   Authorization code: {authorization_code[:20]}...")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(token_endpoint, data=data, headers=headers)
                print(f"   Response status: {response.status_code}")

                if response.status_code == 200:
                    tokens = response.json()
                    print("✅ Token exchange successful!")
                    print(
                        f"   Access token: {'*' * 20}... (expires_in: {tokens.get('expires_in')})"
                    )
                    print(f"   Token type: {tokens.get('token_type')}")
                    if "refresh_token" in tokens:
                        print(f"   Refresh token: {'*' * 20}...")
                    return tokens
                else:
                    error_text = response.text
                    print("❌ Token exchange failed:")
                    print(f"   Status code: {response.status_code}")
                    print(f"   Error response: {error_text}")
                    raise ValueError(
                        f"Token exchange failed: {response.status_code} - {error_text}"
                    )

            except Exception as e:
                print(f"❌ Network error: {e}")
                raise

    async def get_m2m_token(self) -> dict:
        """Get M2M access token using client_credentials flow."""
        if not self.client_secret:
            raise ValueError("Client secret is required for M2M authentication")

        if not self.well_known_config:
            await self.discover_endpoints()

        token_endpoint = self.well_known_config.get("token_endpoint")
        if not token_endpoint:
            raise ValueError("No token endpoint found in OAuth 2.0 configuration")

        # Use provider-specific scopes
        if (
            "cognito-idp" in self.discovery_url.lower()
            or "cognito" in self.discovery_url.lower()
            or "amazoncognito" in self.discovery_url.lower()
        ):
            # For AWS Cognito M2M, we need resource server scopes (not user pool scopes)
            # Common patterns: 'read', 'write', 'admin', or custom resource server scopes
            # If no resource server is configured, try without scopes or use custom ones
            scope = None  # Try without scope first, Cognito might have default scopes
        else:
            # For generic OAuth providers, use standard scopes
            scope = "openid profile"

        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        # Only add scope if we have one
        if scope:
            data["scope"] = scope

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        print("🤖 Requesting M2M token...")
        print(f"   Token endpoint: {token_endpoint}")
        print(f"   Client ID: {self.client_id}")
        print("   Grant type: client_credentials")
        print(f"   Scope: {scope or 'none (using default)'}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(token_endpoint, data=data, headers=headers)
                print(f"   Response status: {response.status_code}")

                if response.status_code == 200:
                    tokens = response.json()
                    print("✅ M2M token request successful!")
                    print(
                        f"   Access token: {'*' * 20}... (expires_in: {tokens.get('expires_in')} seconds)"
                    )
                    print(f"   Token type: {tokens.get('token_type')}")
                    print(f"   Scope: {tokens.get('scope', 'unknown')}")

                    # Try to decode JWT token to see claims (for debugging)
                    try:
                        import base64
                        import json

                        access_token = tokens["access_token"]
                        # JWT has 3 parts separated by dots: header.payload.signature
                        parts = access_token.split(".")
                        if len(parts) >= 2:
                            # Decode payload (add padding if needed)
                            payload = parts[1]
                            payload += "=" * (4 - len(payload) % 4)  # Add padding
                            decoded = base64.urlsafe_b64decode(payload)
                            claims = json.loads(decoded)
                            print("   Token claims:")
                            print(
                                f"     - aud (audience): {claims.get('aud', 'unknown')}"
                            )
                            print(f"     - scope: {claims.get('scope', 'unknown')}")
                            print(
                                f"     - client_id: {claims.get('client_id', 'unknown')}"
                            )
                            print(
                                f"     - token_use: {claims.get('token_use', 'unknown')}"
                            )
                    except Exception as decode_error:
                        print(
                            f"   (Could not decode token for inspection: {decode_error})"
                        )

                    return tokens
                else:
                    error_text = response.text
                    print("❌ M2M token request failed:")
                    print(f"   Status code: {response.status_code}")
                    print(f"   Error response: {error_text}")
                    raise ValueError(
                        f"M2M token request failed: {response.status_code} - {error_text}"
                    )

            except Exception as e:
                print(f"❌ M2M authentication network error: {e}")
                raise


async def handle_redirect_with_browser(auth_url: str) -> None:
    """Handle OAuth redirect by opening browser automatically."""
    print("\n🌐 Opening browser for authorization...")
    print(f"🔗 Authorization URL: {auth_url}")

    try:
        webbrowser.open(auth_url)
        print("✅ Browser opened, please complete login")
    except Exception:
        print("⚠️  Unable to open browser automatically, please visit manually:")
        print(f"   {auth_url}")

    print("\n📋 After authorization, you will be redirected to: http://localhost:3000")


async def handle_callback_interactive() -> tuple[str, str | None]:
    """Handle OAuth callback by prompting for the callback URL."""
    print(
        "\n📋 After authorization completion, copy the full URL from browser address bar:"
    )
    print("💡 Hint: URL should start with 'http://localhost:3000/?code='")

    while True:
        callback_url = input("\nCallback URL: ").strip()

        if not callback_url:
            print("❌ URL cannot be empty, please try again")
            continue

        try:
            parsed_url = urlparse(callback_url)
            params = parse_qs(parsed_url.query)

            if "code" not in params:
                print("❌ Authorization code not found in URL (missing code parameter)")
                print("💡 Please ensure you copied the complete redirect URL")
                continue

            authorization_code = params["code"][0]
            state = params.get("state", [None])[0]

            print(f"✅ Authorization code parsed: {authorization_code[:20]}...")
            if state:
                print(f"   State parameter: {state}")

            return authorization_code, state

        except Exception as e:
            print(f"❌ URL parsing error: {e}")
            print("💡 Please check URL format")
            continue


async def test_mcp_with_manual_token(mcp_server_url: str, access_token: str):
    """Test MCP connection with manually obtained access token."""
    print("\n🔗 Connecting to MCP server with token...")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        async with streamablehttp_client(mcp_server_url, headers) as (read, write, _):
            print("✅ MCP connection successful!")

            try:
                async with ClientSession(read, write) as session:
                    print("🔄 Initializing session...")

                    try:
                        await session.initialize()
                        print("✅ Session initialization successful!")

                        # List available tools
                        print("🔍 Listing available tools...")
                        tools_result = await session.list_tools()
                        tools = tools_result.tools

                        if tools:
                            print(f"\n📚 Found {len(tools)} tools:")
                            for i, tool in enumerate(tools, 1):
                                print(f"  {i}. {tool.name}")
                                if tool.description:
                                    print(
                                        f"     Description: {tool.description[:100]}..."
                                    )

                            # Check for dynamic tool invocation
                            test_tool_name = os.getenv("MCP_TEST_TOOL_NAME")
                            test_tool_params = os.getenv("MCP_TEST_TOOL_PARAMS")

                            if test_tool_name and test_tool_params:
                                print(
                                    f"\n🔧 Dynamic tool invocation requested: {test_tool_name}"
                                )

                                # Check if the requested tool exists
                                tool_names = [tool.name for tool in tools]
                                if test_tool_name in tool_names:
                                    try:
                                        # Parse the JSON parameters
                                        import json

                                        params = json.loads(test_tool_params)

                                        print(
                                            f"🚀 Invoking tool '{test_tool_name}' with parameters: {params}"
                                        )

                                        # Call the tool
                                        result = await session.call_tool(
                                            test_tool_name, params
                                        )

                                        print("✅ Tool invocation successful!")
                                        print(f"📄 Result: {result}")

                                    except json.JSONDecodeError as je:
                                        print(
                                            f"❌ Invalid JSON in MCP_TEST_TOOL_PARAMS: {je}"
                                        )
                                    except Exception as te:
                                        print(f"❌ Tool invocation failed: {te}")
                                        print(f"   Error type: {type(te).__name__}")
                                        import traceback

                                        print("🔍 Tool invocation error traceback:")
                                        traceback.print_exc()
                                else:
                                    print(
                                        f"❌ Tool '{test_tool_name}' not found in available tools"
                                    )
                                    print(f"   Available tools: {tool_names}")

                        else:
                            print("\n❌ No available tools")

                        return True

                    except Exception as init_error:
                        print(f"❌ Session initialization failed: {init_error}")
                        print(f"   Error type: {type(init_error).__name__}")

                        # Try to get more details
                        import traceback

                        print("🔍 Full error traceback:")
                        traceback.print_exc()
                        return False

            except Exception as session_cleanup_error:
                # Ignore session termination errors (common with servers that don't implement session/end)
                if (
                    "404" in str(session_cleanup_error)
                    or "termination" in str(session_cleanup_error).lower()
                ):
                    print(
                        "ℹ️  Session cleanup skipped (server doesn't support session termination)"
                    )
                else:
                    print(f"⚠️  Session cleanup error: {session_cleanup_error}")
                return True  # Still return success if the main operation worked

    except Exception as e:
        print(f"❌ MCP connection failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback

        print("🔍 Full error traceback:")
        traceback.print_exc()
        return False


def load_config() -> dict:
    """Load configuration from environment variables."""

    # Required configuration
    required_vars = ["OAUTH_DISCOVERY_URL", "OAUTH_CLIENT_ID", "AGENTCORE_RUNTIME_ARN"]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   {var}")
        print("\n💡 Please check .env.example for reference values")
        raise ValueError(f"Missing required environment variables: {missing_vars}")

    config = {
        # OAuth 2.0 Configuration
        "discovery_url": os.getenv("OAUTH_DISCOVERY_URL"),
        "client_id": os.getenv("OAUTH_CLIENT_ID"),
        "client_secret": os.getenv("OAUTH_CLIENT_SECRET"),
        "m2m_scopes": os.getenv("OAUTH_M2M_SCOPES"),
        # AgentCore Runtime Configuration
        "agentcore_runtime_arn": os.getenv("AGENTCORE_RUNTIME_ARN"),
        "agentcore_region": os.getenv("AGENTCORE_REGION", "us-west-2"),
        # Test User Configuration (for quick mode)
        "test_username": os.getenv("OAUTH_TEST_USERNAME"),
        "test_password": os.getenv("OAUTH_TEST_PASSWORD"),
        # AWS Profile
        "aws_profile": os.getenv("AWS_PROFILE", "default"),
    }

    # Auto-detect provider type for better user experience
    if (
        "cognito-idp" in config["discovery_url"].lower()
        or "cognito" in config["discovery_url"].lower()
        or "amazoncognito" in config["discovery_url"].lower()
    ):
        print("🏛️ Detected AWS Cognito OAuth 2.0 provider")
    else:
        print("🔗 Using generic OAuth 2.0 provider")

    # URL encode the ARN for AgentCore
    encoded_arn = (
        config["agentcore_runtime_arn"].replace(":", "%3A").replace("/", "%2F")
    )
    config["mcp_server_url"] = (
        f"https://bedrock-agentcore.{config['agentcore_region']}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    )

    return config


async def test_manual_oauth_flow(config: dict):
    """Test manual OAuth flow with detailed debugging."""
    print("\n🔧 === Manual OAuth Flow - Step-by-step debugging ===")

    oauth_handler = OAuth2Handler(config["discovery_url"], config["client_id"])

    try:
        # 1. Generate authorization URL
        auth_url = await oauth_handler.get_authorization_url()
        await handle_redirect_with_browser(auth_url)

        # 2. Get authorization code
        authorization_code, _ = await handle_callback_interactive()

        # 3. Exchange for tokens
        tokens = await oauth_handler.exchange_code_for_tokens(authorization_code)
        access_token = tokens["access_token"]

        # 4. Test MCP connection
        success = await test_mcp_with_manual_token(
            config["mcp_server_url"], access_token
        )

        if success:
            print("\n🎉 Manual OAuth flow completely successful!")
            print("✅ Access token is valid, MCP server connection normal")
        else:
            print("\n⚠️  OAuth successful but MCP connection failed")

    except Exception as e:
        print(f"❌ Manual OAuth flow failed: {e}")
        import traceback

        traceback.print_exc()


async def test_quick_mode(config: dict):
    """Quick mode using existing test user credentials."""
    print("\n🚀 === Quick Mode - Using existing credentials ===")

    # Check if credentials are available
    if not config["test_username"] or not config["test_password"]:
        print("❌ Quick mode requires test user credentials")
        print("💡 Please set environment variables:")
        print("   export OAUTH_TEST_USERNAME='your_username'")
        print("   export OAUTH_TEST_PASSWORD='your_password'")
        print("\n📝 Or check .env.example for configuration reference")
        return

    # Check if this is AWS Cognito (Quick mode only works with Cognito direct auth)
    if (
        "cognito-idp" not in config["discovery_url"].lower()
        and "cognito" not in config["discovery_url"].lower()
        and "amazoncognito" not in config["discovery_url"].lower()
    ):
        print("❌ Quick mode only works with AWS Cognito providers")
        print("💡 For other OAuth 2.0 providers, use:")
        print("   Mode 1 (Manual): Interactive OAuth flow")
        print("   Mode 3 (M2M): Client credentials flow")
        return

    print("Using test user credentials for quick token retrieval...")

    try:
        # Extract region from discovery URL for Cognito
        # New format: https://cognito-idp.us-west-2.amazonaws.com/us-west-2_UserPoolId/.well-known/openid_configuration
        # Legacy format: https://domain.auth.us-west-2.amazoncognito.com/.well-known/openid_configuration
        import re

        # Try new cognito-idp format first
        region_match = re.search(
            r"cognito-idp\.([^.]+)\.amazonaws\.com", config["discovery_url"]
        )
        if not region_match:
            # Fallback to legacy auth domain format
            region_match = re.search(
                r"\.auth\.([^.]+)\.amazoncognito\.com", config["discovery_url"]
            )

        if not region_match:
            raise ValueError(
                "Cannot extract AWS region from discovery URL. Quick mode only works with AWS Cognito."
            )

        region = region_match.group(1)
        print(f"📍 Extracted AWS region: {region}")

        # Use boto3 for quick token retrieval
        session = boto3.Session(profile_name=config["aws_profile"])
        cognito_client = session.client("cognito-idp", region_name=region)

        response = cognito_client.initiate_auth(
            ClientId=config["client_id"],
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": config["test_username"],
                "PASSWORD": config["test_password"],
            },
        )

        access_token = response["AuthenticationResult"]["AccessToken"]
        print(f"✅ Token retrieval successful: {'*' * 20}...")

        # Test MCP connection
        success = await test_mcp_with_manual_token(
            config["mcp_server_url"], access_token
        )

        if success:
            print("\n🎉 Quick mode completely successful!")
            print(
                "✅ This confirms your Cognito configuration and MCP server are working properly"
            )
        else:
            print("\n⚠️  Token retrieval successful but MCP connection failed")

    except Exception as e:
        print(f"❌ Quick mode failed: {e}")
        print("💡 Please ensure:")
        print(f"   - AWS_PROFILE={config['aws_profile']} points to correct account")
        print(f"   - Test user {config['test_username']} exists with correct password")


async def test_m2m_mode(config: dict):
    """Test M2M (Machine-to-Machine) authentication with client credentials."""
    print("\n🏭 === M2M Mode - Machine-to-machine authentication ===")

    client_secret = config["client_secret"]

    if not client_secret:
        print("🔑 M2M authentication requires client secret")
        print("💡 Set environment variable: export OAUTH_CLIENT_SECRET='your_secret'")
        print("   - Enter manually (not recommended for production)")
        print()

        user_choice = input("Enter client secret manually? (y/N): ").strip().lower()
        if user_choice == "y":
            client_secret = input("Please enter client secret: ").strip()
            if not client_secret:
                print("❌ Client secret cannot be empty")
                return
        else:
            print("❌ No client secret provided, cannot continue M2M authentication")
            print(
                "💡 Hint: You can generate a secret in AWS Cognito console for your client"
            )
            return

    try:
        oauth_handler = OAuth2Handler(
            config["discovery_url"], config["client_id"], client_secret
        )

        # Get M2M token
        tokens = await oauth_handler.get_m2m_token()
        access_token = tokens["access_token"]

        # Test MCP connection
        success = await test_mcp_with_manual_token(
            config["mcp_server_url"], access_token
        )

        if success:
            print("\n🎉 M2M mode completely successful!")
            print(
                "✅ Client credentials authentication working properly, no user interaction required"
            )
            print(
                "🏭 This is the ideal authentication method for service-to-service communication"
            )
            print(f"⏱️  Token validity: {tokens.get('expires_in', 'unknown')} seconds")
        else:
            print("\n⚠️  M2M authentication successful but MCP connection failed")

    except Exception as e:
        print(f"❌ M2M authentication failed: {e}")
        print("\n🔧 Troubleshooting suggestions:")
        print("   1. Ensure Cognito client has client_credentials flow enabled")
        print("   2. Verify client secret is correct")
        print("   3. Check client has appropriate OAuth scopes")
        print("\n📚 Configuration commands:")
        print("   # Enable client_credentials flow (adjust user-pool-id as needed)")
        print(
            f"   AWS_PROFILE={config['aws_profile']} aws cognito-idp update-user-pool-client \\"
        )
        print("     --user-pool-id <your-user-pool-id> \\")
        print(f"     --client-id {config['client_id']} \\")
        print('     --allowed-o-auth-flows "client_credentials" \\')
        print("     --generate-secret")


async def handle_native_sdk_redirect(auth_url: str) -> None:
    """Handle OAuth redirect for native SDK mode."""
    print("\n🌐 Opening browser for authorization (Native SDK)...")
    print(f"🔗 Authorization URL: {auth_url}")

    try:
        webbrowser.open(auth_url)
        print("✅ Browser opened, please complete login")
    except Exception:
        print("⚠️  Unable to open browser automatically, please visit manually:")
        print(f"   {auth_url}")

    print("\n📋 After authorization, you will be redirected to: http://localhost:3000/")


class AgentCoreOAuthClientProvider(OAuthClientProvider):
    """Custom OAuth provider that triggers on 403 (not just 401) for AgentCore compatibility.

    Supports both interactive OAuth flows and M2M (client_credentials) flows with automatic
    token refresh for both modes.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_m2m_mode = False  # Will be set after client info is available

    def _detect_m2m_mode(self) -> bool:
        """Detect if we're in M2M mode based on client_secret availability."""
        return bool(
            self.context.client_info
            and self.context.client_info.client_secret
            and hasattr(self.context, "client_metadata")
            and not hasattr(self.context.client_metadata, "redirect_uris")
            or not self.context.client_metadata.redirect_uris
        )

    def can_refresh_token(self) -> bool:
        """Check if token can be refreshed - supports both interactive and M2M modes."""
        if self.is_m2m_mode:
            # M2M can always "refresh" by re-authenticating with client_credentials
            return bool(
                self.context.client_info
                and self.context.client_info.client_secret
                and self.context.client_info.client_id
            )
        else:
            # Interactive mode uses parent's refresh_token logic
            return super().can_refresh_token()

    async def _get_m2m_token(self) -> httpx.Request:
        """Get M2M access token using client_credentials flow."""
        if not self.context.client_info or not self.context.client_info.client_secret:
            raise OAuthTokenError("Client secret required for M2M authentication")

        # Use discovered token endpoint or fallback
        if self.context.oauth_metadata and self.context.oauth_metadata.token_endpoint:
            token_url = str(self.context.oauth_metadata.token_endpoint)
        else:
            auth_base_url = self.context.get_authorization_base_url(
                self.context.auth_server_url or self.context.server_url
            )
            token_url = urljoin(auth_base_url, "/token")

        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.context.client_info.client_id,
            "client_secret": self.context.client_info.client_secret,
        }

        # Add scope if specified
        if self.context.client_metadata.scope:
            token_data["scope"] = self.context.client_metadata.scope

        # Add resource parameter if conditions are met (RFC 8707)
        if self.context.should_include_resource_param(self.context.protocol_version):
            token_data["resource"] = self.context.get_resource_url()

        # Debug logging for M2M request (sensitive data redacted for security)
        print("🔄 Preparing M2M token request:")
        print(f"   Token endpoint: {token_url}")
        print("   Grant type: client_credentials")
        print("   Client ID: [REDACTED]")
        print("   Client secret: [REDACTED]")
        print("   Scope: [REDACTED]")
        print("   Resource: [REDACTED]")

        return httpx.Request(
            "POST",
            token_url,
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    async def _handle_m2m_token_response(self, response: httpx.Response) -> None:
        """Handle M2M token response with detailed error logging."""
        print(f"🔄 M2M token response: {response.status_code}")

        if response.status_code != 200:
            # Get detailed error information
            try:
                error_body = await response.aread()
                error_text = error_body.decode("utf-8")
                print("❌ M2M token request failed:")
                print(f"   Status code: {response.status_code}")
                print(f"   Error response: {error_text}")

                # Try to parse as JSON for structured error info
                try:
                    import json

                    error_json = json.loads(error_text)
                    if "error" in error_json:
                        print(f"   Error type: {error_json.get('error')}")
                        print(
                            f"   Error description: {error_json.get('error_description', 'N/A')}"
                        )
                except json.JSONDecodeError:
                    print(f"   Raw error (not JSON): {error_text}")

            except Exception as e:
                print(f"   Could not read error response: {e}")

            # Re-raise with original error for parent handling
            raise OAuthTokenError(f"M2M token request failed: {response.status_code}")

        # Success case - delegate to parent for token parsing
        await super()._handle_token_response(response)

    async def _refresh_token(self) -> httpx.Request:
        """Build token refresh request - routes to M2M or interactive flow."""
        if self.is_m2m_mode:
            # For M2M, "refresh" means getting a new token with client_credentials
            return await self._get_m2m_token()
        else:
            # For interactive, use parent's refresh_token flow
            return await super()._refresh_token()

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        """HTTPX auth flow integration with 403 support and M2M mode."""
        async with self.context.lock:
            if not self._initialized:
                await self._initialize()
                # Detect M2M mode after initialization
                self.is_m2m_mode = bool(
                    self.context.client_info and self.context.client_info.client_secret
                )

            # Capture protocol version from request headers
            self.context.protocol_version = request.headers.get(MCP_PROTOCOL_VERSION)

            if not self.context.is_token_valid() and self.context.can_refresh_token():
                # Try to refresh token (routes to appropriate flow based on mode)
                refresh_request = await self._refresh_token()
                refresh_response = yield refresh_request

                if not await self._handle_refresh_response(refresh_response):
                    # Refresh failed, need full re-authentication
                    self._initialized = False

            if self.context.is_token_valid():
                self._add_auth_header(request)

            response = yield request

            # CUSTOM FIX: Trigger OAuth flow on 403 OR 401 (AgentCore returns 403)
            if response.status_code in (401, 403):
                # Perform full OAuth flow (same as original, but triggered on 403 too)
                try:
                    # OAuth flow must be inline due to generator constraints
                    # Step 1: Skip protected resource discovery since we manually configured it

                    # Step 2: Discover OAuth metadata (with fallback for legacy servers)
                    discovery_urls = self._get_discovery_urls()
                    for url in discovery_urls:
                        oauth_metadata_request = self._create_oauth_metadata_request(
                            url
                        )
                        oauth_metadata_response = yield oauth_metadata_request

                        if oauth_metadata_response.status_code == 200:
                            try:
                                await self._handle_oauth_metadata_response(
                                    oauth_metadata_response
                                )
                                break
                            except ValidationError:
                                continue
                        elif (
                            oauth_metadata_response.status_code < 400
                            or oauth_metadata_response.status_code >= 500
                        ):
                            break  # Non-4XX error, stop trying

                    # Step 3: Register client if needed
                    registration_request = await self._register_client()
                    if registration_request:
                        registration_response = yield registration_request
                        await self._handle_registration_response(registration_response)

                    # Step 4: Perform authorization - different for M2M vs interactive
                    if self.is_m2m_mode:
                        # M2M mode: Use client_credentials directly, no browser interaction
                        token_request = await self._get_m2m_token()
                        token_response = yield token_request
                        await self._handle_m2m_token_response(token_response)
                    else:
                        # Interactive mode: Use authorization code flow
                        auth_code, code_verifier = await self._perform_authorization()

                        # Step 5: Exchange authorization code for tokens
                        token_request = await self._exchange_token(
                            auth_code, code_verifier
                        )
                        token_response = yield token_request
                        await self._handle_token_response(token_response)
                except Exception:
                    logger.exception("OAuth flow error")
                    raise

        # Retry with new tokens
        self._add_auth_header(request)
        yield request


async def handle_native_sdk_callback() -> tuple[str, str | None]:
    """Handle OAuth callback for native SDK mode."""
    print(
        "\n📋 After authorization completion, copy the full URL from browser address bar:"
    )
    print("💡 Hint: URL should start with 'http://localhost:3000/?code='")

    while True:
        callback_url = input("\nCallback URL: ").strip()

        if not callback_url:
            print("❌ URL cannot be empty, please try again")
            continue

        try:
            parsed_url = urlparse(callback_url)
            params = parse_qs(parsed_url.query)

            if "code" not in params:
                print("❌ Authorization code not found in URL (missing code parameter)")
                print("💡 Please ensure you copied the complete redirect URL")
                continue

            authorization_code = params["code"][0]
            state = params.get("state", [None])[0]

            print(f"✅ Authorization code parsed: {authorization_code[:20]}...")
            if state:
                print(f"   State parameter: {state}")

            return authorization_code, state

        except Exception as e:
            print(f"❌ URL parsing error: {e}")
            print("💡 Please check URL format")
            continue


async def test_native_sdk_oauth_flow(config: dict):
    """Test native MCP SDK OAuth flow with auto-detection of M2M vs interactive mode."""
    # Detect M2M mode based on client_secret presence
    is_m2m_mode = bool(config.get("client_secret"))

    if is_m2m_mode:
        print("\n🏭 === Native SDK Mode (M2M) - Client Credentials Flow ===")
        print("🔧 Detected client_secret - using M2M authentication")
        print("🚀 No user interaction required - fully automated")

        # Remind user about M2M scopes configuration
        m2m_scopes = config.get("m2m_scopes")
        if m2m_scopes:
            print(f"🎯 Using configured M2M scopes: {m2m_scopes}")
        else:
            print("⚠️  No M2M scopes configured - authentication may fail!")
            print(
                '💡 Add OAUTH_M2M_SCOPES="mcp-server/read mcp-server/write" to .env if needed'
            )
    else:
        print("\n🔐 === Native SDK Mode (Interactive) - Authorization Code Flow ===")
        print("🔧 No client_secret detected - using interactive authentication")
        print("🌐 Browser-based user authentication required")

    try:
        # Prepare redirect URIs (required by constructor but not used in M2M mode)
        redirect_uris = [AnyUrl("http://localhost:3000")]

        # Determine appropriate scopes based on provider and mode
        if (
            "cognito-idp" in config["discovery_url"].lower()
            or "cognito" in config["discovery_url"].lower()
            or "amazoncognito" in config["discovery_url"].lower()
        ):
            if is_m2m_mode:
                # For Cognito M2M, use configured M2M scopes or fallback to None
                scope = config["m2m_scopes"]
                if scope:
                    print(
                        f"🔧 Detected AWS Cognito M2M - using configured scopes: {scope}"
                    )
                else:
                    print(
                        "🔧 Detected AWS Cognito M2M - no scopes configured (may work for some setups)"
                    )
                    print(
                        "💡 Tip: Set OAUTH_M2M_SCOPES in .env if authentication fails"
                    )
            else:
                scope = "openid email aws.cognito.signin.user.admin"
                print(
                    "🔧 Detected AWS Cognito Interactive - using Cognito-specific scopes"
                )
        else:
            if is_m2m_mode:
                # Generic M2M with configured scopes or fallback to None
                scope = config["m2m_scopes"]
                if scope:
                    print(f"🔧 Using configured M2M scopes: {scope}")
                else:
                    print("🔧 Using generic M2M without scopes")
                    print(
                        "💡 Tip: Set OAUTH_M2M_SCOPES in .env if authentication fails"
                    )
            else:
                scope = "openid email profile"
                print("🔧 Using standard OpenID Connect scopes")

        # Note: OAuthClientMetadata enforces interactive OAuth constraints
        # For M2M mode, we use interactive-compatible metadata but override behavior in the provider
        if is_m2m_mode:
            client_name = "MCP AgentCore OAuth Client (Native SDK - M2M)"
            print(
                "   Note: Using interactive-compatible metadata, M2M logic handled in provider"
            )
        else:
            client_name = "MCP AgentCore OAuth Client (Native SDK - Interactive)"

        # Create OAuth client metadata (always use interactive-compatible values)
        client_metadata = OAuthClientMetadata(
            client_name=client_name,
            redirect_uris=redirect_uris,  # Always provide redirect URIs (required by validation)
            grant_types=[
                "authorization_code",
                "refresh_token",
            ],  # Always use interactive grant types
            response_types=["code"],  # Always provide response types
            scope=scope,
        )

        print("📋 Client metadata configured:")
        print(f"   Client name: {client_metadata.client_name}")
        print(f"   Grant types: {client_metadata.grant_types}")
        print(f"   Scope: {client_metadata.scope}")
        if not is_m2m_mode:
            print(
                f"   Redirect URIs: {[str(uri) for uri in client_metadata.redirect_uris]}"
            )

        # Create token storage
        token_storage = DebugTokenStorage()

        # Pre-configure client info to skip registration (AWS Cognito doesn't support dynamic registration)
        print("🔧 Pre-configuring client info to skip registration...")

        # We'll populate the endpoints after OAuth metadata discovery, but set basic info now
        from mcp.shared.auth import OAuthClientInformationFull

        client_info = OAuthClientInformationFull(
            client_id=config["client_id"],
            client_secret=config.get("client_secret"),
            authorization_endpoint="",  # Will be populated during OAuth metadata discovery
            token_endpoint="",  # Will be populated during OAuth metadata discovery
            redirect_uris=redirect_uris,
        )
        await token_storage.set_client_info(client_info)
        print(f"   ✅ Client info pre-configured with ID: {config['client_id']}")
        if is_m2m_mode:
            print("   🔑 Client secret configured for M2M authentication")

        # Create dummy handlers for M2M mode (required by constructor but won't be used)
        async def dummy_redirect_handler(auth_url: str) -> None:
            """Dummy handler for M2M mode - should never be called."""
            print(
                "⚠️  WARNING: Redirect handler called in M2M mode - this shouldn't happen!"
            )

        async def dummy_callback_handler() -> tuple[str, str | None]:
            """Dummy handler for M2M mode - should never be called."""
            print(
                "⚠️  WARNING: Callback handler called in M2M mode - this shouldn't happen!"
            )
            return "", None

        # Choose appropriate handlers based on mode
        if is_m2m_mode:
            redirect_handler = dummy_redirect_handler
            callback_handler = dummy_callback_handler
        else:
            redirect_handler = handle_native_sdk_redirect
            callback_handler = handle_native_sdk_callback

        # Create custom OAuth client provider with 403 support and M2M compatibility
        oauth_auth = AgentCoreOAuthClientProvider(
            server_url=config["mcp_server_url"],  # Use MCP server URL
            client_metadata=client_metadata,
            storage=token_storage,
            redirect_handler=redirect_handler,
            callback_handler=callback_handler,
        )

        print("\n🔧 Manually configuring protected resource metadata...")

        # Fix: Manually set protected resource metadata since AgentCore doesn't provide it
        from mcp.shared.auth import ProtectedResourceMetadata
        from pydantic import AnyUrl as PydanticUrl

        # Extract OAuth server URL from discovery URL
        oauth_server_url = (
            config["discovery_url"]
            .replace("/.well-known/openid_configuration", "")
            .replace("/.well-known/openid-configuration", "")
        )

        # Create protected resource metadata pointing to Cognito
        protected_metadata = ProtectedResourceMetadata(
            resource=PydanticUrl(config["mcp_server_url"]),
            authorization_servers=[PydanticUrl(oauth_server_url)],
        )

        print(f"   Resource: {protected_metadata.resource}")
        print(
            f"   Authorization servers: {[str(s) for s in protected_metadata.authorization_servers]}"
        )

        # Manually inject the metadata into the OAuth context
        oauth_auth.context.protected_resource_metadata = protected_metadata
        oauth_auth.context.auth_server_url = oauth_server_url

        print("\n🔄 Testing native SDK OAuth with custom AgentCore provider...")
        print(f"   MCP Server URL: {config['mcp_server_url']}")
        print(f"   OAuth Server URL: {oauth_server_url}")
        print("   Custom feature: Triggers OAuth flow on 403 (not just 401)")

        # Use the OAuth provider with streamable HTTP client
        async with streamablehttp_client(config["mcp_server_url"], auth=oauth_auth) as (
            read,
            write,
            _,
        ):
            print("✅ MCP connection with native SDK OAuth successful!")

            async with ClientSession(read, write) as session:
                print("🔄 Initializing session...")

                try:
                    await session.initialize()
                    print("✅ Session initialization successful!")

                    # List available tools
                    print("🔍 Listing available tools...")
                    tools_result = await session.list_tools()
                    tools = tools_result.tools

                    if tools:
                        print(f"\n📚 Found {len(tools)} tools:")
                        for i, tool in enumerate(tools, 1):
                            print(f"  {i}. {tool.name}")
                            if tool.description:
                                print(f"     Description: {tool.description[:100]}...")

                        # Check for dynamic tool invocation
                        test_tool_name = os.getenv("MCP_TEST_TOOL_NAME")
                        test_tool_params = os.getenv("MCP_TEST_TOOL_PARAMS")

                        if test_tool_name and test_tool_params:
                            print(
                                f"\n🔧 Dynamic tool invocation requested: {test_tool_name}"
                            )

                            # Check if the requested tool exists
                            tool_names = [tool.name for tool in tools]
                            if test_tool_name in tool_names:
                                try:
                                    # Parse the JSON parameters
                                    import json

                                    params = json.loads(test_tool_params)

                                    print(
                                        f"🚀 Invoking tool '{test_tool_name}' with parameters: {params}"
                                    )

                                    # Call the tool
                                    result = await session.call_tool(
                                        test_tool_name, params
                                    )

                                    print("✅ Tool invocation successful!")
                                    print(f"📄 Result: {result}")

                                except json.JSONDecodeError as je:
                                    print(
                                        f"❌ Invalid JSON in MCP_TEST_TOOL_PARAMS: {je}"
                                    )
                                except Exception as te:
                                    print(f"❌ Tool invocation failed: {te}")
                                    print(f"   Error type: {type(te).__name__}")
                                    import traceback

                                    print("🔍 Tool invocation error traceback:")
                                    traceback.print_exc()
                            else:
                                print(
                                    f"❌ Tool '{test_tool_name}' not found in available tools"
                                )
                                print(f"   Available tools: {tool_names}")

                    else:
                        print("\n❌ No available tools")

                    if is_m2m_mode:
                        print("\n🎉 Native SDK M2M OAuth flow completely successful!")
                        print(
                            "✅ Using official MCP SDK OAuth implementation (M2M mode)"
                        )
                        print("🏭 Client credentials authentication working properly")
                        print("🚀 No user interaction required - fully automated")
                        print("🔄 Automatic token refresh via client_credentials")
                    else:
                        print(
                            "\n🎉 Native SDK Interactive OAuth flow completely successful!"
                        )
                        print(
                            "✅ Using official MCP SDK OAuth implementation (Interactive mode)"
                        )
                        print("🌐 Browser-based authentication completed")
                        print("🔄 Automatic token refresh via refresh_token")

                    print("🔧 Custom AgentCore compatibility (403 → OAuth trigger)")
                    print("🔐 Protected resource metadata configured for cross-domain")
                    print("🚀 Automatic token refresh and session management enabled")

                    return True

                except Exception as init_error:
                    print(f"❌ Session initialization failed: {init_error}")
                    print(f"   Error type: {type(init_error).__name__}")

                    # Try to get more details
                    import traceback

                    print("🔍 Full error traceback:")
                    traceback.print_exc()
                    return False

    except Exception as e:
        print(f"❌ Native SDK OAuth flow failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback

        print("🔍 Full error traceback:")
        traceback.print_exc()

        print("\n🔧 Troubleshooting suggestions:")
        print("   1. Check that client ID and discovery URL are correct")
        if is_m2m_mode:
            print("   2. Verify client_secret is valid and properly configured")
            print("   3. Ensure client_credentials grant is enabled in OAuth provider")
            print("   4. Check that client has appropriate scopes for M2M access")
        else:
            print("   2. Verify redirect URI is configured in OAuth provider")
            print("   3. Complete the OAuth flow in browser when prompted")
            print("   4. Ensure authorization_code grant is enabled")
        print("   5. Ensure AWS credentials are valid for the MCP server")
        print("   6. This implementation handles AgentCore's 403 responses correctly")

        return False


def print_config(config: dict):
    """Print current configuration."""
    print("📋 Configuration:")
    print(f"   OAuth Discovery URL: {config['discovery_url']}")
    print(f"   Client ID: {config['client_id']}")
    print(f"   MCP Server: {config['mcp_server_url']}")
    print(f"   AWS Profile: {config['aws_profile']}")
    print()


async def main():
    """Main function demonstrating OAuth 2.0 flows with any provider."""

    print("Generic OAuth 2.0 MCP Client")
    print("=" * 60)

    # Load configuration
    config = load_config()
    print_config(config)

    # Choose authentication mode
    print("Select OAuth authentication mode:")
    print("1. 🔧 Manual Mode - Manual OAuth flow (step-by-step debugging)")
    print("2. 🚀 Quick Mode - Using existing user credentials")
    print("3. 🏭 M2M Mode - Machine-to-machine authentication (client_credentials)")
    print("4. 🔐 Native SDK Mode - MCP SDK OAuth (Auto-detects M2M vs Interactive)")

    choice = input("\nSelect mode (1/2/3/4) [default: 2]: ").strip() or "2"

    if choice == "1":
        await test_manual_oauth_flow(config)
    elif choice == "2":
        await test_quick_mode(config)
    elif choice == "3":
        await test_m2m_mode(config)
    elif choice == "4":
        await test_native_sdk_oauth_flow(config)
    else:
        print("❌ Invalid selection")


if __name__ == "__main__":
    asyncio.run(main())
