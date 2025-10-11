#!/usr/bin/python
from boto3.session import Session
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse
import base64
import boto3
import hashlib
import json
import logging
import os
import requests
import sys
import threading
import time
import urllib
import webbrowser
import yaml

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    ssm = boto3.client("ssm")

    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)

    return response["Parameter"]["Value"]


def read_config(file_path: str) -> Dict[str, Any]:
    """
    Read configuration from a file path. Supports JSON, YAML, and YML formats.

    Args:
        file_path (str): Path to the configuration file

    Returns:
        Dict[str, Any]: Configuration data as a dictionary

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file format is not supported or invalid
        yaml.YAMLError: If YAML parsing fails
        json.JSONDecodeError: If JSON parsing fails
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    # Get file extension to determine format
    _, ext = os.path.splitext(file_path.lower())

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            if ext == ".json":
                return json.load(file)
            elif ext in [".yaml", ".yml"]:
                return yaml.safe_load(file)
            else:
                # Try to auto-detect format by attempting JSON first, then YAML
                content = file.read()
                file.seek(0)

                # Try JSON first
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # Try YAML
                    try:
                        return yaml.safe_load(content)
                    except yaml.YAMLError:
                        raise ValueError(
                            f"Unsupported configuration file format: {ext}. "
                            f"Supported formats: .json, .yaml, .yml"
                        )

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file {file_path}: {e}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file {file_path}: {e}")
    except Exception as e:
        raise ValueError(f"Error reading configuration file {file_path}: {e}")


def get_token_config_path():
    """Get the path to the token config file."""
    return Path.home() / ".bedrock_agent_tokens.json"


def save_access_token(token: str, agent_name: str):
    """Save access token to local config file."""
    config_path = get_token_config_path()

    # Load existing config or create new one
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
    else:
        config = {}

    # Save token for this agent
    import time

    config[agent_name] = {"access_token": token, "timestamp": int(time.time())}

    # Write back to file
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    # Set restrictive permissions (readable only by owner)
    config_path.chmod(0o600)


def load_access_token(agent_name: str) -> Optional[str]:
    """Load access token from local config file."""
    config_path = get_token_config_path()

    if not config_path.exists():
        return None

    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        if agent_name in config and "access_token" in config[agent_name]:
            return config[agent_name]["access_token"]
    except (json.JSONDecodeError, KeyError, IOError):
        pass

    return None


def generate_pkce_pair():
    code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode("utf-8").rstrip("=")
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .decode("utf-8")
        .rstrip("=")
    )
    return code_verifier, code_challenge


class OAuth2CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth2 callback."""

    def __init__(self, callback_result, *args, **kwargs):
        self.callback_result = callback_result
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET request for OAuth2 callback."""
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)

        if "code" in query_params:
            # Success - we got the authorization code
            self.callback_result["code"] = query_params["code"][0]
            self.callback_result["success"] = True

            # Send success response
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
            <html>
                <head><title>Authentication Success</title></head>
                <body>
                    <h1>Authentication Successful!</h1>
                    <p>You can close this window and return to your terminal.</p>
                    <script>setTimeout(() => window.close(), 3000);</script>
                </body>
            </html>
            """)
        elif "error" in query_params:
            # Error occurred
            error = query_params.get("error", ["unknown"])[0]
            error_description = query_params.get("error_description", [""])[0]

            self.callback_result["error"] = error
            self.callback_result["error_description"] = error_description
            self.callback_result["success"] = False

            # Send error response
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"""
            <html>
                <head><title>Authentication Error</title></head>
                <body>
                    <h1>Authentication Failed</h1>
                    <p>Error: {error}</p>
                    <p>Description: {error_description}</p>
                    <p>You can close this window and return to your terminal.</p>
                </body>
            </html>
            """.encode()
            )
        else:
            # Unexpected request
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Invalid Request</h1></body></html>")

    def log_message(self, format, *args):
        """Suppress log messages."""
        pass


def start_oauth_server(port=8080, timeout=300):
    """Start a local HTTP server to handle OAuth2 callback."""
    callback_result = {"success": False, "code": None, "error": None}

    def handler(*args, **kwargs):
        return OAuth2CallbackHandler(callback_result, *args, **kwargs)

    server = HTTPServer(("localhost", port), handler)

    def run_server():
        server.timeout = 1  # Check for shutdown every second
        start_time = time.time()
        while (
            time.time() - start_time < timeout
            and not callback_result["success"]
            and not callback_result["error"]
        ):
            server.handle_request()
        server.server_close()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    return callback_result, server_thread


def get_auth_code_automatically(login_url, port=8080, timeout=300):
    """Automatically get OAuth authorization code using local server."""
    print(f"🚀 Starting local server on port {port} to handle OAuth callback...")

    callback_result, server_thread = start_oauth_server(port, timeout)

    print("🔐 Opening browser for authentication...")
    webbrowser.open(login_url)
    print(f"🔐 Opening URL: {login_url}")

    print("⏳ Waiting for authentication callback...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        if callback_result["success"]:
            print("✅ Authorization code received successfully!")
            return callback_result["code"]
        elif callback_result["error"]:
            print(f"❌ Authentication failed: {callback_result['error']}")
            if callback_result["error_description"]:
                print(f"   Description: {callback_result['error_description']}")
            return None
        time.sleep(0.5)

    print("⏰ Authentication timed out. Please try again.")
    return None


def invoke_endpoint(
    agent_arn: str,
    payload,
    session_id: str,
    bearer_token: Optional[str],
    endpoint_name: str = "DEFAULT",
    stream: bool = True,
) -> Any:
    escaped_arn = urllib.parse.quote(agent_arn, safe="")

    _, region = get_aws_info()

    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations"

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
    }

    try:
        body = json.loads(payload) if isinstance(payload, str) else payload
    except json.JSONDecodeError:
        body = {"payload": payload}

    response = requests.post(
        url,
        params={"qualifier": endpoint_name},
        headers=headers,
        json=body,
        timeout=100,
        stream=stream,
    )

    if not stream:
        print(
            response.content.decode("utf-8").replace("\\n", "\n").replace('"', ""),
            flush=True,
        )
    else:
        last_data = False

        for line in response.iter_lines(chunk_size=1):
            if line:
                line = line.decode("utf-8")
                # print(line)
                if line.startswith("data: "):
                    last_data = True
                    line = line[6:].replace('"', "")
                    # Replace literal \n with actual newlines
                    line = line.replace("\\n", "\n")
                    print(line, end="")
                elif line:
                    if last_data:
                        line = line.replace('"', "")
                        # Replace literal \n with actual newlines
                        line = line.replace("\\n", "\n")
                        print("\n" + line, end="")
                    last_data = False


def get_aws_info():
    """Get AWS account ID and region from boto3 session"""
    try:
        boto_session = Session()

        # Get region
        region = boto_session.region_name
        if not region:
            # Try to get from default session
            region = (
                boto3.DEFAULT_SESSION.region_name if boto3.DEFAULT_SESSION else None
            )
            if not region:
                raise ValueError(
                    "AWS region not configured. Please set AWS_DEFAULT_REGION or configure AWS CLI."
                )

        # Get account ID using STS
        sts = boto_session.client("sts")
        account_id = sts.get_caller_identity()["Account"]

        return account_id, region

    except Exception as e:
        print(f"❌ Error getting AWS info: {e}")
        print(
            "Please ensure AWS credentials are configured (aws configure or environment variables)"
        )
        sys.exit(1)


def get_nested_stack_name(parent_stack_name, logical_resource_id, region):
    """Get the physical resource ID (stack name) of a nested stack"""
    try:
        cfn = boto3.client("cloudformation", region_name=region)
        response = cfn.describe_stack_resource(
            StackName=parent_stack_name, LogicalResourceId=logical_resource_id
        )

        physical_resource_id = response["StackResourceDetail"]["PhysicalResourceId"]
        # Physical resource ID for nested stacks is the full stack ARN
        # Extract just the stack name from the ARN
        # Format: arn:aws:cloudformation:region:account:stack/stack-name/guid
        stack_name = physical_resource_id.split("/")[-2]
        return stack_name

    except Exception as e:
        print(f"❌ Error getting nested stack name: {e}")
        sys.exit(1)


def get_stack_output(stack_name, output_key, region):
    """Get CloudFormation stack output value"""
    try:
        cfn = boto3.client("cloudformation", region_name=region)
        response = cfn.describe_stacks(StackName=stack_name)

        if not response["Stacks"]:
            raise ValueError(f"Stack '{stack_name}' not found")

        stack = response["Stacks"][0]
        outputs = stack.get("Outputs", [])

        for output in outputs:
            if output["OutputKey"] == output_key:
                return output["OutputValue"]

        raise ValueError(f"Output '{output_key}' not found in stack '{stack_name}'")

    except Exception as e:
        print(f"❌ Error getting stack output: {e}")
        sys.exit(1)
