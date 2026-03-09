#!/usr/bin/env python3
"""
Simplified Strands Client using AgentCore SDK

This client uses the official bedrock_agentcore.runtime.AgentCoreRuntimeClient
for cleaner, more maintainable WebSocket URL generation.
"""
import argparse
import os
import sys
import webbrowser
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from bedrock_agentcore.runtime import AgentCoreRuntimeClient


class StrandsClientHandler(BaseHTTPRequestHandler):
    """HTTP request handler that serves the Strands client"""

    # Class variables to store connection details
    websocket_url = None
    session_id = None
    is_presigned = False
    is_local = False

    # Store config for regenerating URLs
    runtime_arn = None
    region = None
    endpoint_name = None
    voice_id = None
    expires = None

    def log_message(self, format, *args):
        """Override to provide cleaner logging"""
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)

        if parsed_path.path == "/" or parsed_path.path == "/index.html":
            self.serve_client_page()
        elif parsed_path.path == "/api/connection":
            self.serve_connection_info()
        else:
            self.send_error(404, "File not found")

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)

        if parsed_path.path == "/api/regenerate":
            self.regenerate_url()
        elif parsed_path.path == "/api/generate-url":
            self.generate_url()
        else:
            self.send_error(404, "Endpoint not found")

    def serve_client_page(self):
        """Serve the HTML client with pre-configured connection"""
        try:
            # Read the HTML template from the original client folder
            html_path = os.path.join(
                os.path.dirname(__file__), 
                "./client.html"
            )
            with open(html_path, "r") as f:
                html_content = f.read()

            # Inject the WebSocket URL if provided
            if self.websocket_url:
                html_content = html_content.replace(
                    'id="presignedUrl" placeholder="wss://endpoint/runtimes/arn/ws?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...&X-Amz-Signature=..."',
                    f'id="presignedUrl" placeholder="wss://endpoint/runtimes/arn/ws?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...&X-Amz-Signature=..." value="{self.websocket_url}"',
                )

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", len(html_content.encode()))
            self.end_headers()
            self.wfile.write(html_content.encode())

        except FileNotFoundError:
            self.send_error(404, "strands-client.html not found")
        except Exception as e:
            self.send_error(500, f"Internal server error: {str(e)}")

    def serve_connection_info(self):
        """Serve the connection information as JSON"""
        response = {
            "websocket_url": self.websocket_url or "",
            "session_id": self.session_id,
            "is_presigned": self.is_presigned,
            "is_local": self.is_local,
            "can_regenerate": self.runtime_arn is not None,
            "status": "ok" if self.websocket_url else "no_connection",
        }

        response_json = json.dumps(response, indent=2)

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", len(response_json.encode()))
        self.end_headers()
        self.wfile.write(response_json.encode())

    def generate_url(self):
        """Generate a new presigned URL with a fresh session ID"""
        try:
            if not self.runtime_arn:
                error_response = {
                    "status": "error",
                    "message": "Cannot generate URL - not using presigned URL mode",
                }
                response_json = json.dumps(error_response)
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.send_header("Content-Length", len(response_json.encode()))
                self.end_headers()
                self.wfile.write(response_json.encode())
                return

            # Read the session_id and voice_id from the request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            request_data = json.loads(body) if body else {}
            session_id = request_data.get('session_id')
            voice_id = request_data.get('voice_id', self.voice_id)

            if not session_id:
                error_response = {
                    "status": "error",
                    "message": "session_id is required in request body",
                }
                response_json = json.dumps(error_response)
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.send_header("Content-Length", len(response_json.encode()))
                self.end_headers()
                self.wfile.write(response_json.encode())
                return

            # Use AgentCore SDK to generate presigned URL
            # custom_headers become query parameters signed into the URL by SigV4
            client = AgentCoreRuntimeClient(region=self.region)
            new_url = client.generate_presigned_url(
                runtime_arn=self.runtime_arn,
                session_id=session_id,
                endpoint_name=self.endpoint_name,
                custom_headers={
                    'X-Amzn-Bedrock-AgentCore-Runtime-Custom-VoiceId': voice_id
                },
                expires=self.expires
            )

            # Update the class variables
            StrandsClientHandler.websocket_url = new_url
            StrandsClientHandler.session_id = session_id

            response = {
                "status": "ok",
                "websocket_url": new_url,
                "session_id": session_id,
                "expires_in": self.expires,
                "message": "URL generated successfully",
            }

            response_json = json.dumps(response, indent=2)

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(response_json.encode()))
            self.end_headers()
            self.wfile.write(response_json.encode())
            print(f"🔐 Presigned URL: {new_url}")
            print(f"✅ Generated presigned URL for session {session_id} with voice '{voice_id}' (expires in {self.expires} seconds)")

        except Exception as e:
            import traceback
            error_response = {"status": "error", "message": str(e), "traceback": traceback.format_exc()}
            response_json = json.dumps(error_response)
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(response_json.encode()))
            self.end_headers()
            self.wfile.write(response_json.encode())

    def regenerate_url(self):
        """Regenerate the presigned URL using AgentCore SDK"""
        try:
            if not self.runtime_arn:
                error_response = {
                    "status": "error",
                    "message": "Cannot regenerate URL - not using presigned URL mode",
                }
                response_json = json.dumps(error_response)
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.send_header("Content-Length", len(response_json.encode()))
                self.end_headers()
                self.wfile.write(response_json.encode())
                return

            # Use AgentCore SDK to generate presigned URL
            client = AgentCoreRuntimeClient(region=self.region)
            #added session_id as a custom header to overcome a bug. Remove it when fixed , 'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': self.session_id
            new_url = client.generate_presigned_url(
                runtime_arn=self.runtime_arn,
                session_id=self.session_id,
                endpoint_name=self.endpoint_name,
                custom_headers={'voice_id': self.voice_id},
                expires=self.expires
            )

            # Update the class variable
            StrandsClientHandler.websocket_url = new_url

            response = {
                "status": "ok",
                "websocket_url": new_url,
                "expires_in": self.expires,
                "message": "URL regenerated successfully",
            }

            response_json = json.dumps(response, indent=2)

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(response_json.encode()))
            self.end_headers()
            self.wfile.write(response_json.encode())

            print(f"✅ Regenerated presigned URL (expires in {self.expires} seconds)")

        except Exception as e:
            error_response = {"status": "error", "message": str(e)}
            response_json = json.dumps(error_response)
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(response_json.encode()))
            self.end_headers()
            self.wfile.write(response_json.encode())


def main():
    parser = argparse.ArgumentParser(
        description="Start web service for Strands WebSocket client (using AgentCore SDK)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local WebSocket server (no authentication)
  python client.py --ws-url ws://localhost:8080/ws
  
  # AWS Bedrock with presigned URL (using AgentCore SDK)
  python client.py --runtime-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/RUNTIMEID
  
  # With custom session ID
  python client.py --runtime-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/RUNTIMEID \\
    --session-id my-conversation-123
  
  # Specify custom port
  python client.py --runtime-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/RUNTIMEID --port 8080
""",
    )

    parser.add_argument(
        "--runtime-arn",
        help="Runtime ARN for AWS Bedrock connection (e.g., arn:aws:bedrock-agentcore:region:account:runtime/id)",
    )

    parser.add_argument(
        "--ws-url",
        help="WebSocket server URL for local connections (e.g., ws://localhost:8080/ws)",
    )

    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION", "us-east-1"),
        help="AWS region (default: us-east-1, from AWS_REGION env var)",
    )

    parser.add_argument(
        "--endpoint-name",
        default="DEFAULT",
        help="Runtime endpoint name (default: DEFAULT)",
    )

    parser.add_argument(
        "--voice-id",
        default="alloy",
        help="Voice ID to use for OpenAI (e.g., 'alloy', 'echo', 'shimmer'). Default: alloy"
    )

    parser.add_argument(
        "--session-id",
        help="Session ID for conversation continuity (auto-generated if not provided)"
    )

    parser.add_argument(
        "--expires",
        type=int,
        default=300,
        help="URL expiration time in seconds for presigned URLs (default: 300 = 5 minutes, max: 300)",
    )

    parser.add_argument(
        "--port", type=int, default=8000, help="Web server port (default: 8000)"
    )

    parser.add_argument(
        "--no-browser", action="store_true", help="Do not automatically open browser"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.runtime_arn and not args.ws_url:
        parser.error("Either --runtime-arn or --ws-url must be specified")

    if args.runtime_arn and args.ws_url:
        parser.error("Cannot specify both --runtime-arn and --ws-url")

    # Extract region from runtime ARN if provided
    if args.runtime_arn:
        arn_parts = args.runtime_arn.split(":")
        if len(arn_parts) >= 4:
            arn_region = arn_parts[3]
            if arn_region and arn_region != args.region:
                args.region = arn_region

    print("=" * 70)
    print("🎙️ Strands Client Web Service (AgentCore SDK)")
    print("=" * 70)

    websocket_url = None
    session_id = args.session_id
    is_presigned = False
    is_local = False

    try:
        # Configure for AWS Bedrock (URL will be generated on-demand)
        if args.runtime_arn:
            print(f"🔑 Runtime ARN: {args.runtime_arn}")
            print(f"🌍 Region: {args.region}")
            print(f"🤖 Model: OpenAI Realtime API")
            print(f"🔗 Endpoint: {args.endpoint_name}")
            print()
            print("💡 Presigned URL will be generated when you click 'Start Conversation' and expires after 5 mins")
            
            is_presigned = True

        # Use provided WebSocket URL for local connections
        else:
            voice_id = args.voice_id
            
            # Add voice_id to the URL if not already present
            if '?' in args.ws_url:
                websocket_url = f"{args.ws_url}&voice_id={voice_id}"
            else:
                websocket_url = f"{args.ws_url}?voice_id={voice_id}"
            
            print(f"🔗 WebSocket URL: {websocket_url}")
            print(f"🤖 Model: OpenAI Realtime API")
            print(f"🎙️ Voice ID: {voice_id}")
            print("💡 Using local WebSocket connection (no authentication)")
            is_local = True

        print(f"🌐 Web Server Port: {args.port}")
        print()

        # Set connection details in the handler class
        StrandsClientHandler.websocket_url = websocket_url
        StrandsClientHandler.session_id = session_id
        StrandsClientHandler.is_presigned = is_presigned
        StrandsClientHandler.is_local = is_local

        # Store config for generating URLs
        if args.runtime_arn:
            StrandsClientHandler.runtime_arn = args.runtime_arn
            StrandsClientHandler.region = args.region
            StrandsClientHandler.endpoint_name = args.endpoint_name
            StrandsClientHandler.voice_id = args.voice_id
            StrandsClientHandler.expires = args.expires

        # Start web server
        server_address = ("", args.port)
        httpd = HTTPServer(server_address, StrandsClientHandler)

        server_url = f"http://localhost:{args.port}"

        print("=" * 70)
        print("🌐 Web Server Started")
        print("=" * 70)
        print(f"📍 Server URL: {server_url}")
        print(f"🔗 Client Page: {server_url}/")
        print(f"📊 API Endpoint: {server_url}/api/connection")
        print()
        if is_presigned:
            print("💡 Click 'Start Conversation' to generate a fresh presigned URL")
        else:
            print("💡 The WebSocket URL is pre-populated in the client")
        print("💡 Press Ctrl+C to stop the server")
        print("=" * 70)
        print()

        # Open browser automatically
        if not args.no_browser:
            print("🌐 Opening browser...")
            webbrowser.open(server_url)
            print()

        # Start serving
        httpd.serve_forever()

    except KeyboardInterrupt:
        print("\n\n👋 Shutting down server...")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
