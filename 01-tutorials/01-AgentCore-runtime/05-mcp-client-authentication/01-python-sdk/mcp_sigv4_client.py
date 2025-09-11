#!/usr/bin/env python3
"""
MCP Client for AWS AgentCore using SigV4 Authentication

This script uses AWS SigV4 authentication (the default for AgentCore)
instead of JWT/OAuth tokens.
"""

import argparse
import asyncio
import boto3
import os
import sys
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import httpx

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class HTTPXSigV4Auth(httpx.Auth):
    """HTTPX authentication handler for AWS SigV4."""

    def __init__(self, credentials, service: str, region: str):
        self.credentials = credentials
        self.service = service
        self.region = region

    def auth_flow(self, request: httpx.Request):
        """Implement the authentication flow for SigV4."""

        # For HTTPX, we need to read the actual content that will be sent
        # HTTPX may not have populated request.content yet, so we need to trigger content preparation
        if hasattr(request, "read"):
            try:
                # Try to read the content if it's available
                body = request.read()
            except Exception:
                # Fallback to manual content handling
                body = self._get_request_body(request)
        else:
            body = self._get_request_body(request)

        # Create botocore AWS request with exact same data
        aws_request = AWSRequest(
            method=request.method, url=str(request.url), data=body, headers={}
        )

        # Use only minimal essential headers required for SigV4
        # AWS SigV4 requires Host header and any headers that will actually be sent
        essential_headers = {"Host": request.url.host}

        # Add Content-Type and Content-Length for POST requests
        if request.method == "POST" and body:
            essential_headers["Content-Type"] = "application/json"
            essential_headers["Content-Length"] = str(len(body))

        # Set headers on AWS request
        for name, value in essential_headers.items():
            aws_request.headers[name] = value

        # Calculate and set content hash - required for bedrock-agentcore
        import hashlib

        content_hash = hashlib.sha256(body).hexdigest()
        aws_request.headers["X-Amz-Content-Sha256"] = content_hash

        # Sign the request
        signer = SigV4Auth(self.credentials, self.service, self.region)
        signer.add_auth(aws_request)

        # Update the HTTPX request with all signed headers
        for name, value in aws_request.headers.items():
            request.headers[name] = value

        yield request

    def _get_request_body(self, request: httpx.Request) -> bytes:
        """Extract request body content for signing."""
        body = b""

        # Check for content attribute first
        if hasattr(request, "content") and request.content is not None:
            if isinstance(request.content, bytes):
                body = request.content
            elif isinstance(request.content, str):
                body = request.content.encode("utf-8")
            else:
                # For other types (like dict), serialize to JSON
                import json

                body = json.dumps(request.content).encode("utf-8")

        # If no content, check if there's a stream
        elif hasattr(request, "stream") and request.stream is not None:
            # For streaming content, we need to read it
            if hasattr(request.stream, "__iter__"):
                try:
                    body = b"".join(request.stream)
                except Exception:
                    # If we can't read stream, assume empty body
                    body = b""

        return body


class SigV4AgentCoreMCPClient:
    """MCP client for AWS AgentCore using SigV4 authentication."""

    def __init__(
        self, agent_arn: str, region: str = "us-west-2", profile_name: str = None
    ):
        self.agent_arn = agent_arn
        self.region = region
        # Use the specified profile (defaulting to 'default' if none specified)
        self.session = boto3.Session(profile_name=profile_name or "default")
        self.credentials = self.session.get_credentials()

    def get_mcp_url(self) -> str:
        """Generate the proper MCP URL for AgentCore."""
        # Use the full ARN in the URL path as per AWS documentation
        # URL encode the ARN for safe inclusion in URL path
        encoded_arn = self.agent_arn.replace(":", "%3A").replace("/", "%2F")
        return f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

    def get_auth_handler(self) -> HTTPXSigV4Auth:
        """Create SigV4 auth handler."""
        return HTTPXSigV4Auth(self.credentials, "bedrock-agentcore", self.region)

    async def test_simple_http_auth(self):
        """Test simple HTTP request with SigV4 auth first."""
        mcp_url = self.get_mcp_url()

        print(f"🧪 Testing simple HTTP auth to: {mcp_url}")

        # Create SigV4 auth handler
        auth = self.get_auth_handler()

        # Simple test payload
        test_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"roots": {"listChanged": False}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }

        # Debug: Try with no auth first
        print("🔍 Testing without auth first...")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    mcp_url,
                    json=test_payload,
                    headers={"Accept": "application/json, text/event-stream"},
                    timeout=30.0,
                )
                print(
                    f"No auth response: {response.status_code} - {response.text[:100]}..."
                )
            except Exception as e:
                print(f"No auth test failed: {e}")

        print("🔍 Testing with SigV4 auth...")
        async with httpx.AsyncClient(auth=auth) as client:
            try:
                response = await client.post(
                    mcp_url,
                    json=test_payload,
                    headers={"Accept": "application/json, text/event-stream"},
                    timeout=30.0,
                )

                print(f"✅ HTTP Response: {response.status_code}")
                if response.status_code == 200:
                    print(f"✅ Response: {response.text[:200]}...")
                    return True
                else:
                    print(f"❌ Error: {response.text}")
                    return False

            except Exception as e:
                print(f"❌ HTTP request failed: {e}")
                return False

    async def test_mcp_connection(self):
        """Test MCP connection with SigV4 authentication using streamablehttp_client."""
        mcp_url = self.get_mcp_url()

        print(f"🔗 Connecting to MCP server: {mcp_url}")
        print("🔑 Using streamablehttp_client with SigV4 auth handler")

        # Create SigV4 auth handler
        auth = self.get_auth_handler()

        # Create headers - let MCP client handle Content-Type
        headers = {"Accept": "application/json, text/event-stream"}

        try:
            async with streamablehttp_client(
                url=mcp_url, headers=headers, auth=auth, timeout=30.0
            ) as (read, write, _):
                print("✅ MCP connection established!")

                async with ClientSession(read, write) as session:
                    print("🔄 Initializing MCP session...")

                    try:
                        # Initialize the session
                        await session.initialize()
                        print("✅ Session initialization successful!")

                        # Note: MCP ClientSession doesn't have a ping method
                        print("📡 MCP session is active and ready")

                        # List available tools
                        print("\n🔍 Listing available tools...")
                        tools_result = await session.list_tools()
                        tools = tools_result.tools

                        if tools:
                            print(f"\n📚 Found {len(tools)} tools:")
                            for i, tool in enumerate(tools, 1):
                                print(f"  {i}. {tool.name}")
                                if tool.description:
                                    description = (
                                        tool.description[:100] + "..."
                                        if len(tool.description) > 100
                                        else tool.description
                                    )
                                    print(f"     Description: {description}")

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
                            print("📭 No tools available on this server")

                        # List available resources
                        print("\n📂 Listing available resources...")
                        try:
                            resources_result = await session.list_resources()
                            resources = resources_result.resources

                            if resources:
                                print(f"\n📁 Found {len(resources)} resources:")
                                for i, resource in enumerate(resources, 1):
                                    print(f"  {i}. {resource.uri}")
                                    if resource.name:
                                        print(f"     Name: {resource.name}")
                                    if resource.description:
                                        description = (
                                            resource.description[:100] + "..."
                                            if len(resource.description) > 100
                                            else resource.description
                                        )
                                        print(f"     Description: {description}")
                            else:
                                print("📭 No resources available on this server")
                        except Exception as e:
                            print(f"⚠️  Could not list resources: {e}")

                        return True

                    except Exception as e:
                        print(f"❌ MCP session error: {e}")
                        import traceback

                        print(f"Session error details: {traceback.format_exc()}")
                        return False

        except Exception as e:
            print(f"❌ MCP connection failed: {e}")
            import traceback

            print(f"Full error details: {traceback.format_exc()}")
            return False


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="MCP Client for AWS AgentCore using SigV4 Authentication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mcp_sigv4_client.py --agent-arn arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/my-agent
  python mcp_sigv4_client.py -a arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/my-agent --region us-east-1
        """,
    )

    parser.add_argument(
        "--agent-arn",
        "-a",
        required=True,
        help="AWS AgentCore runtime/gateway ARN (e.g., arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/my-agent)",
    )

    parser.add_argument(
        "--region", "-r", default="us-west-2", help="AWS region (default: us-west-2)"
    )

    return parser.parse_args()


async def main():
    """Main function to test SigV4 authentication."""

    args = parse_args()

    print("AWS AgentCore MCP Client with SigV4 Authentication")
    print("==================================================")

    # Validate ARN format
    if not args.agent_arn.startswith("arn:aws:bedrock-agentcore:"):
        print(f"❌ Invalid ARN format: {args.agent_arn}")
        print("ARN should start with: arn:aws:bedrock-agentcore:")
        return

    print(f"Agent ARN: {args.agent_arn}")
    print(f"Region: {args.region}")

    # Check AWS credentials using 'default' profile
    try:
        session = boto3.Session(profile_name="default")
        credentials = session.get_credentials()
        if not credentials:
            print("❌ AWS credentials not found!")
            print("Please configure AWS credentials using:")
            print("  aws configure")
            print("  or set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
            return

        # Get caller identity to verify credentials
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        print(f"✓ AWS credentials configured for: {identity.get('Arn', 'Unknown')}")

    except Exception as e:
        print(f"❌ AWS credentials error: {e}")
        return

    # Test simple HTTP auth first
    print("\nTesting simple HTTP authentication...")
    client = SigV4AgentCoreMCPClient(
        args.agent_arn, args.region, profile_name="default"
    )

    http_success = await client.test_simple_http_auth()

    if not http_success:
        print("❌ Simple HTTP auth failed, skipping MCP test")
        return

    # Test the MCP connection with proper SigV4 transport
    print("\nTesting MCP connection with SigV4 authentication...")
    success = await client.test_mcp_connection()

    if success:
        print("\n" + "=" * 50)
        print("✅ MCP connection with SigV4 authentication successful!")
        print("🎉 AgentCore MCP server is accessible and responding correctly.")
        print(
            "You can now use this client pattern to integrate with MCP-enabled applications."
        )
    else:
        print("\n" + "=" * 50)
        print("❌ MCP connection with SigV4 authentication failed")
        print(
            "Please check your AWS credentials, AgentCore ARN, and network connectivity."
        )


if __name__ == "__main__":
    # Check if required packages are available
    try:
        import boto3
        import httpx
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError as e:
        print(f"❌ Required package missing: {e}")
        print("Install with: pip install boto3 httpx mcp")
        sys.exit(1)

    asyncio.run(main())
