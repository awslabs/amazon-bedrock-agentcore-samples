"""
Okta-authenticated MCP Server on Amazon Bedrock AgentCore Runtime.

Deploys a FastMCP server (backed by a Bedrock Knowledge Base) to AgentCore
Runtime with Okta JWT validation via customJWTAuthorizer.  The invoke step
performs an Authorization Code + PKCE flow against Okta, then sends MCP
JSON-RPC messages with the resulting Bearer token.

Architecture:
    1. MCP server container runs on AgentCore Runtime
    2. AgentCore validates inbound JWTs against Okta's OIDC discovery endpoint
    3. On success, the request reaches the FastMCP container which calls
       Bedrock RetrieveAndGenerate for knowledge-base answers

Usage:
    python okta_mcp_runtime.py                # deploy + invoke
    python okta_mcp_runtime.py --invoke       # invoke only (from saved config)
    python okta_mcp_runtime.py --cleanup      # tear down all resources

Prerequisites:
    - AWS CLI configured with appropriate permissions
    - Docker with buildx support
    - Okta Custom Authorization Server configured (see OKTA_SETUP.md)
    - An existing Bedrock Knowledge Base
    - pip install -r requirements.txt requests

Environment variables:
    OKTA_DOMAIN           - e.g. dev-12345678.okta.com
    OKTA_AUTH_SERVER_ID   - Custom Authorization Server ID
    OKTA_CLIENT_ID        - Native Application client ID
    OKTA_AUDIENCE         - Audience configured on the auth server (e.g. api://my-mcp)
    KNOWLEDGE_BASE_ID     - Bedrock Knowledge Base ID
    KB_REGION             - Region where the Knowledge Base lives
    BEDROCK_MODEL_ARN     - Model ARN or inference-profile ARN
"""

import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import socketserver
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import webbrowser

import boto3
import requests as http_requests
from boto3.session import Session

# ── Configuration ─────────────────────────────────────────────────────────────

RUNTIME_NAME = f"okta_kb_mcp_{int(time.time()) % 100000}"
CONFIG_FILE = "okta_mcp_config.json"
CALLBACK_PORT = 8090

session = Session()
REGION = session.region_name or "us-west-2"
ACCOUNT_ID = session.client("sts").get_caller_identity()["Account"]

print(f"Region:  {REGION}")
print(f"Account: {ACCOUNT_ID}")


# ── Okta helpers ──────────────────────────────────────────────────────────────


def _require_okta_env() -> dict:
    """Validate and return Okta-related environment variables."""
    required = {
        "OKTA_DOMAIN": os.environ.get("OKTA_DOMAIN"),
        "OKTA_AUTH_SERVER_ID": os.environ.get("OKTA_AUTH_SERVER_ID"),
        "OKTA_CLIENT_ID": os.environ.get("OKTA_CLIENT_ID"),
        "OKTA_AUDIENCE": os.environ.get("OKTA_AUDIENCE"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")
    return required


def _require_kb_env() -> dict:
    """Validate and return Knowledge Base environment variables."""
    required = {
        "KNOWLEDGE_BASE_ID": os.environ.get("KNOWLEDGE_BASE_ID"),
        "KB_REGION": os.environ.get("KB_REGION"),
        "BEDROCK_MODEL_ARN": os.environ.get("BEDROCK_MODEL_ARN"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")
    return required


def _discovery_url(domain: str, auth_server_id: str) -> str:
    return f"https://{domain}/oauth2/{auth_server_id}/.well-known/openid-configuration"


# ── Config persistence ────────────────────────────────────────────────────────


def _save_config(updates: dict) -> None:
    """Merge updates into the config file."""
    try:
        with open(CONFIG_FILE) as f:
            existing = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing = {}
    existing.update(updates)
    with open(CONFIG_FILE, "w") as f:
        json.dump(existing, f, indent=2)


def _load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return json.load(f)


# ── IAM ───────────────────────────────────────────────────────────────────────


def create_execution_role(kb_env: dict) -> str:
    """Create an IAM execution role for the AgentCore MCP Runtime."""
    role_name = f"agentcore-okta-mcp-{ACCOUNT_ID}-role"
    iam = boto3.client("iam", region_name=REGION)

    trust_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {"aws:SourceAccount": ACCOUNT_ID}
                    },
                }
            ],
        }
    )

    try:
        role = iam.create_role(
            RoleName=role_name, AssumeRolePolicyDocument=trust_policy
        )
        role_arn = role["Role"]["Arn"]
        print(f"  Created IAM role: {role_name}")
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = iam.get_role(RoleName=role_name)["Role"]["Arn"]
        print(f"  Reusing IAM role: {role_name}")

    kb_region = kb_env["KB_REGION"]
    kb_id = kb_env["KNOWLEDGE_BASE_ID"]

    policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:RetrieveAndGenerate",
                        "bedrock:Retrieve",
                    ],
                    "Resource": (
                        f"arn:aws:bedrock:{kb_region}:{ACCOUNT_ID}"
                        f":knowledge-base/{kb_id}"
                    ),
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                        "bedrock:GetInferenceProfile",
                    ],
                    "Resource": [
                        f"arn:aws:bedrock:{kb_region}::foundation-model/*",
                        f"arn:aws:bedrock:{kb_region}:{ACCOUNT_ID}:inference-profile/*",
                        "arn:aws:bedrock:*::foundation-model/*",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": "arn:aws:logs:*:*:*",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "xray:PutTraceSegments",
                        "xray:PutTelemetryRecords",
                    ],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": ["ecr:GetAuthorizationToken"],
                    "Resource": "*",
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ecr:BatchGetImage",
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchCheckLayerAvailability",
                    ],
                    "Resource": (
                        f"arn:aws:ecr:{REGION}:{ACCOUNT_ID}"
                        ":repository/agentcore-okta-mcp*"
                    ),
                },
            ],
        }
    )

    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="agentcore-okta-mcp-policy",
        PolicyDocument=policy,
    )

    _save_config({"role_name": role_name, "role_arn": role_arn})
    print("  Waiting for IAM role propagation...")
    time.sleep(15)
    return role_arn


# ── ECR + Docker ──────────────────────────────────────────────────────────────


def ensure_ecr_repository(repo_name: str) -> str:
    """Create the ECR repository if it doesn't exist; return its URI base."""
    ecr = boto3.client("ecr", region_name=REGION)
    try:
        ecr.create_repository(repositoryName=repo_name)
        print(f"  Created ECR repo: {repo_name}")
    except ecr.exceptions.RepositoryAlreadyExistsException:
        pass
    _save_config({"ecr_repo": repo_name})
    return f"{ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/{repo_name}"


def build_and_push_image(repo_name: str, image_tag: str) -> str:
    """Build a linux/arm64 image from this directory and push to ECR."""
    repo_uri_base = ensure_ecr_repository(repo_name)
    image_uri = f"{repo_uri_base}:{image_tag}"

    print(f"  Logging in to ECR ({REGION})...")
    ecr = boto3.client("ecr", region_name=REGION)
    auth_data = ecr.get_authorization_token()["authorizationData"][0]
    proxy_endpoint = auth_data["proxyEndpoint"]
    decoded = base64.b64decode(auth_data["authorizationToken"]).decode("utf-8")
    _user, password = decoded.split(":", 1)

    login = subprocess.run(
        [
            "docker",
            "login",
            "--username",
            "AWS",
            "--password-stdin",
            proxy_endpoint,
        ],
        input=password.encode(),
        capture_output=True,
        check=False,
    )
    if login.returncode != 0:
        raise RuntimeError(
            f"docker login failed: {login.stderr.decode().strip()}"
        )

    src_dir = os.path.dirname(os.path.abspath(__file__))
    print("  Building image (linux/arm64)...")
    result = subprocess.run(
        [
            "docker",
            "buildx",
            "build",
            "--platform",
            "linux/arm64",
            "-t",
            image_uri,
            "-f",
            os.path.join(src_dir, "Dockerfile"),
            "--push",
            src_dir,
        ],
        capture_output=False,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "docker buildx build failed. "
            "Ensure Docker daemon is running and 'docker buildx' is available."
        )
    print(f"  Pushed image → {image_uri}")
    return image_uri


# ── Deploy Runtime ────────────────────────────────────────────────────────────


def deploy_runtime(
    name: str,
    role_arn: str,
    image_uri: str,
    authorizer_config: dict,
    env_vars: dict,
) -> dict:
    """Create an AgentCore MCP Runtime and wait for READY."""
    control = boto3.client("bedrock-agentcore-control", region_name=REGION)

    response = None
    last_err = None
    for attempt in range(5):
        try:
            response = control.create_agent_runtime(
                agentRuntimeName=name,
                agentRuntimeArtifact={
                    "containerConfiguration": {"containerUri": image_uri}
                },
                roleArn=role_arn,
                networkConfiguration={"networkMode": "PUBLIC"},
                authorizerConfiguration=authorizer_config,
                protocolConfiguration={"serverProtocol": "MCP"},
                environmentVariables=env_vars,
            )
            break
        except control.exceptions.ValidationException as exc:
            if "Role validation failed" not in str(exc):
                raise
            last_err = exc
            wait = min(5 * (2**attempt), 30)
            print(
                f"  Role not yet propagated; retrying in {wait}s "
                f"(attempt {attempt + 1}/5)"
            )
            time.sleep(wait)

    if response is None:
        raise RuntimeError(f"Role validation kept failing: {last_err}")

    runtime_id = response["agentRuntimeId"]
    runtime_arn = response["agentRuntimeArn"]
    print(f"  Created runtime: {name} (ID: {runtime_id})")

    print("  Waiting for READY...")
    while True:
        status = control.get_agent_runtime(agentRuntimeId=runtime_id).get(
            "status", "UNKNOWN"
        )
        print(f"    Status: {status}")
        if status == "READY":
            break
        if status in ("CREATE_FAILED", "DELETE_FAILED", "UPDATE_FAILED"):
            raise RuntimeError(f"Runtime failed: {status}")
        time.sleep(15)

    endpoint_url = (
        f"https://bedrock-agentcore.{REGION}.amazonaws.com"
        f"/runtimes/{urllib.parse.quote(runtime_arn, safe='')}/invocations"
        "?qualifier=DEFAULT"
    )

    _save_config(
        {
            "runtime_name": name,
            "runtime_id": runtime_id,
            "runtime_arn": runtime_arn,
            "endpoint_url": endpoint_url,
            "region": REGION,
        }
    )

    return {
        "id": runtime_id,
        "arn": runtime_arn,
        "endpoint_url": endpoint_url,
    }


# ── PKCE OAuth Flow ──────────────────────────────────────────────────────────


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)


def acquire_okta_token(okta_env: dict) -> str:
    """Run Authorization Code + PKCE flow; returns an access token."""
    domain = okta_env["OKTA_DOMAIN"]
    auth_server_id = okta_env["OKTA_AUTH_SERVER_ID"]
    client_id = okta_env["OKTA_CLIENT_ID"]

    auth_server = f"https://{domain}/oauth2/{auth_server_id}"
    redirect_uri = f"http://localhost:{CALLBACK_PORT}/callback"

    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    state = secrets.token_urlsafe(16)

    auth_url = f"{auth_server}/v1/authorize?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "scope": "openid profile",
        }
    )

    captured: dict = {}
    code_received = threading.Event()

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            qs = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query
            )
            if "code" in qs:
                captured["code"] = qs["code"][0]
                code_received.set()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK. You can close this tab.")

        def log_message(self, format, *args):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", CALLBACK_PORT), CallbackHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    print("  Opening browser for Okta sign-in...")
    webbrowser.open(auth_url)

    if not code_received.wait(timeout=300):
        srv.shutdown()
        raise SystemExit("Timed out waiting for Okta callback (5 min).")
    srv.shutdown()
    print("  Authorization code received.")

    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": captured["code"],
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        }
    ).encode()

    req = urllib.request.Request(
        f"{auth_server}/v1/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        resp = urllib.request.urlopen(req).read().decode()
    except urllib.error.HTTPError as e:
        print(f"  Token exchange failed: HTTP {e.code}")
        print(f"  {e.read().decode()[:500]}")
        raise SystemExit(1)

    token_resp = json.loads(resp)
    access_token = token_resp["access_token"]

    # Decode and display key claims for verification.
    _, payload_b64, _ = access_token.split(".")
    payload = json.loads(_b64url_decode(payload_b64))
    print("  Token claims:")
    for key in ("iss", "aud", "cid", "client_id", "scp", "sub"):
        print(f"    {key:12s} = {payload.get(key)}")

    return access_token


# ── MCP Invocation ────────────────────────────────────────────────────────────


def _mcp_post(endpoint_url: str, message: dict, token: str = None) -> dict:
    """Send a JSON-RPC message to the MCP endpoint."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    resp = http_requests.post(
        endpoint_url, json=message, headers=headers, timeout=120
    )
    return {"status": resp.status_code, "body": resp.text[:2000]}


def invoke_mcp(endpoint_url: str, okta_env: dict) -> None:
    """Test the MCP server: unauthenticated rejection + authenticated calls."""
    print("\n── Test: Unauthenticated request (expect 401) ──")
    init_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "okta-mcp-test", "version": "1.0"},
        },
    }
    result = _mcp_post(endpoint_url, init_msg)
    print(f"  HTTP {result['status']}")
    if result["status"] == 401:
        print("  Correctly rejected unauthenticated request.")
    else:
        print(f"  Unexpected status. Body: {result['body']}")

    print("\n── Acquiring Okta token ──")
    token = acquire_okta_token(okta_env)

    print("\n── Test: MCP initialize ──")
    result = _mcp_post(endpoint_url, init_msg, token=token)
    print(f"  HTTP {result['status']}")
    print(f"  Body: {result['body'][:500]}")

    print("\n── Test: MCP tools/list ──")
    list_msg = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    result = _mcp_post(endpoint_url, list_msg, token=token)
    print(f"  HTTP {result['status']}")
    print(f"  Body: {result['body'][:500]}")

    print("\n── Test: MCP tools/call (query_knowledge_base) ──")
    call_msg = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "query_knowledge_base",
            "arguments": {"query": "What is this knowledge base about?"},
        },
    }
    result = _mcp_post(endpoint_url, call_msg, token=token)
    print(f"  HTTP {result['status']}")
    print(f"  Body: {result['body'][:1000]}")


# ── Cleanup ───────────────────────────────────────────────────────────────────


def cleanup() -> None:
    """Delete all resources created by the deploy step."""
    try:
        config = _load_config()
    except FileNotFoundError:
        print("  No config file found. Nothing to clean up.")
        return

    region = config.get("region", REGION)
    control = boto3.client("bedrock-agentcore-control", region_name=region)
    iam = boto3.client("iam", region_name=region)
    ecr = boto3.client("ecr", region_name=region)

    # 1. Delete runtime
    runtime_id = config.get("runtime_id")
    if runtime_id:
        try:
            control.delete_agent_runtime(agentRuntimeId=runtime_id)
            print(f"  Deleted runtime: {runtime_id}")
        except Exception as e:
            print(f"  Runtime delete: {e}")

    # 2. Delete IAM role and inline policies
    role_name = config.get("role_name")
    if role_name:
        try:
            for p in iam.list_role_policies(RoleName=role_name)["PolicyNames"]:
                iam.delete_role_policy(RoleName=role_name, PolicyName=p)
            iam.delete_role(RoleName=role_name)
            print(f"  Deleted IAM role: {role_name}")
        except Exception as e:
            print(f"  Role delete: {e}")

    # 3. Delete ECR repository
    ecr_repo = config.get("ecr_repo")
    if ecr_repo:
        try:
            ecr.delete_repository(repositoryName=ecr_repo, force=True)
            print(f"  Deleted ECR repo: {ecr_repo}")
        except Exception as e:
            print(f"  ECR delete: {e}")

    # 4. Remove config file
    try:
        os.remove(CONFIG_FILE)
        print(f"  Removed {CONFIG_FILE}")
    except OSError:
        pass

    print("  Cleanup complete.")


# ── Deploy ────────────────────────────────────────────────────────────────────


def deploy() -> dict:
    """Deploy the Okta-authenticated MCP server to AgentCore Runtime."""
    okta_env = _require_okta_env()
    kb_env = _require_kb_env()

    print("\n═══ Step 1: Create IAM execution role ═══")
    role_arn = create_execution_role(kb_env)

    print("\n═══ Step 2: Build and push container image ═══")
    image_uri = build_and_push_image(
        repo_name="agentcore-okta-mcp",
        image_tag=RUNTIME_NAME,
    )

    print("\n═══ Step 3: Create AgentCore MCP Runtime ═══")
    discovery_url = _discovery_url(
        okta_env["OKTA_DOMAIN"], okta_env["OKTA_AUTH_SERVER_ID"]
    )

    authorizer_config = {
        "customJWTAuthorizer": {
            "discoveryUrl": discovery_url,
            "allowedClients": [okta_env["OKTA_CLIENT_ID"]],
            "allowedAudience": [okta_env["OKTA_AUDIENCE"]],
        }
    }

    runtime_info = deploy_runtime(
        name=RUNTIME_NAME,
        role_arn=role_arn,
        image_uri=image_uri,
        authorizer_config=authorizer_config,
        env_vars={
            "KNOWLEDGE_BASE_ID": kb_env["KNOWLEDGE_BASE_ID"],
            "KB_REGION": kb_env["KB_REGION"],
            "BEDROCK_MODEL_ARN": kb_env["BEDROCK_MODEL_ARN"],
        },
    )

    endpoint_url = runtime_info["endpoint_url"]
    print(f"\n  MCP Endpoint: {endpoint_url}")

    print("\n  Claude Code config snippet (~/.claude.json):")
    client_config = {
        "mcpServers": {
            "knowledge-base": {
                "type": "http",
                "url": endpoint_url,
                "oauth": {
                    "clientId": okta_env["OKTA_CLIENT_ID"],
                    "authServerMetadataUrl": discovery_url,
                    "callbackPort": CALLBACK_PORT,
                },
            }
        }
    }
    print(f"  {json.dumps(client_config, indent=2)}")

    _save_config(
        {
            "okta_domain": okta_env["OKTA_DOMAIN"],
            "okta_auth_server_id": okta_env["OKTA_AUTH_SERVER_ID"],
            "okta_client_id": okta_env["OKTA_CLIENT_ID"],
            "okta_audience": okta_env["OKTA_AUDIENCE"],
        }
    )

    return runtime_info


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Deploy an Okta-authenticated MCP server on AgentCore Runtime"
    )
    parser.add_argument(
        "--invoke",
        action="store_true",
        help="Invoke only (requires previous deploy; reads from config)",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete all deployed resources",
    )
    args = parser.parse_args()

    if args.cleanup:
        print("\n═══ Cleanup ═══")
        cleanup()
        return

    if args.invoke:
        print("\n═══ Invoke (from saved config) ═══")
        config = _load_config()
        okta_env = {
            "OKTA_DOMAIN": config["okta_domain"],
            "OKTA_AUTH_SERVER_ID": config["okta_auth_server_id"],
            "OKTA_CLIENT_ID": config["okta_client_id"],
            "OKTA_AUDIENCE": config["okta_audience"],
        }
        invoke_mcp(config["endpoint_url"], okta_env)
        return

    print("\n═══ Deploy ═══")
    runtime_info = deploy()

    print("\n═══ Invoke ═══")
    okta_env = _require_okta_env()
    invoke_mcp(runtime_info["endpoint_url"], okta_env)

    print("\n═══ Done ═══")
    print("Run 'python okta_mcp_runtime.py --cleanup' to tear down resources.")


if __name__ == "__main__":
    main()
