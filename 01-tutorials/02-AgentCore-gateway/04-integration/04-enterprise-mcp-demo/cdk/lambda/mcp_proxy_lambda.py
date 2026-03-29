"""
MCP OAuth Proxy Lambda - Handles OAuth metadata, callback interception, token proxying, and MCP forwarding.

This Lambda function replaces the local mcp_oauth_proxy.py script, enabling serverless deployment.
"""

import json
import os
import time
import base64
import urllib.request
import urllib.parse
import urllib.error
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import boto3

# Configuration from environment variables
GATEWAY_URL = os.environ.get("GATEWAY_URL", "")
COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN", "")
CLIENT_ID = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")


def sign_request(request):
    """Sign an HTTP request with AWS SigV4."""
    session = boto3.Session()
    credentials = session.get_credentials()
    region = session.region_name or "us-east-1"

    aws_request = AWSRequest(
        method=request.get_method(),
        url=request.get_full_url(),
        data=request.data,
        headers=request.headers,
    )
    SigV4Auth(credentials, "bedrock-agentcore", region).add_auth(aws_request)

    # Update original request headers
    for key, value in aws_request.headers.items():
        request.add_header(key, value)


def lambda_handler(event, context):
    """Main Lambda handler - routes requests based on path."""
    print(f"Event: {json.dumps(event)}")

    # Support both ALB and API Gateway v2 (HTTP API) events
    # ALB uses: path, httpMethod
    # HTTP API uses: rawPath, requestContext.http.method
    path = event.get("path") or event.get("rawPath", "/")
    method = event.get("httpMethod") or event.get("requestContext", {}).get(
        "http", {}
    ).get("method", "GET")

    print(f"Method: {method}, Path: {path}")

    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {"Allow": "OPTIONS, GET, POST"},
            "body": "",
        }
    # Route to appropriate handler
    if path == "/ping":
        return handle_ping(event)
    elif path.startswith("/.well-known/oauth-authorization-server"):
        return handle_oauth_metadata(event)
    elif (
        path == "/.well-known/oauth-protected-resource"
        or path == "/.well-known/oauth-protected-resource/mcp"
    ):
        return handle_protected_resource_metadata(event)
    elif path == "/authorize":
        return handle_authorize(event)
    elif path == "/callback":
        return handle_callback(event)
    elif path == "/token" and method == "POST":
        return handle_token(event)
    elif path == "/register" and method == "POST":
        return handle_dcr(event)
    elif path == "/mcp":
        return proxy_to_gateway(event)
    else:
        return {"statusCode": 404, "body": json.dumps({"error": "Not found"})}


def handle_ping(event):
    """Health check endpoint for ALB target group."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"status": "healthy", "service": "mcp-proxy"}),
    }


def handle_oauth_metadata(event):
    """Serve OAuth Authorization Server Metadata (RFC 8414)."""
    api_url = get_api_url(event)

    metadata = {
        "issuer": api_url,
        "authorization_endpoint": f"{api_url}/authorize",
        "token_endpoint": f"{api_url}/token",
        "registration_endpoint": f"{api_url}/register",
        "scopes_supported": ["openid", "profile", "email"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        "code_challenge_methods_supported": ["S256"],
    }

    return json_response(200, metadata)


def handle_protected_resource_metadata(event):
    """Serve OAuth Protected Resource Metadata."""
    api_url = get_api_url(event)

    # Per RFC 9728, the 'resource' must match the URL where clients access the service
    # This should be the ALB endpoint, not the Gateway endpoint
    return json_response(
        200,
        {
            "resource": f"{api_url}/mcp",
            "authorization_servers": [api_url],
            "bearer_methods_supported": ["header"],
        },
    )


def handle_authorize(event):
    """Redirect /authorize to Cognito with callback interception.

    Since Lambda is stateless, we encode the original redirect_uri in the state parameter
    so it survives across Lambda invocations.
    """
    print("=== HANDLE_AUTHORIZE DEBUG ===")
    params = event.get("queryStringParameters", {}) or {}
    print(f"Original params: {json.dumps(params)}")

    # Remove unsupported parameters (Cognito doesn't support 'resource' parameter)
    if "resource" in params:
        print(f"Removing 'resource' parameter: {params['resource']}")
        params.pop("resource", None)

    # Fix scope parameter: convert + to spaces (Cognito expects space-separated scopes)
    if "scope" in params:
        # In URL encoding, + represents a space, so replace + with actual spaces
        params["scope"] = params["scope"].replace("+", " ")
        print(f"Fixed scope parameter: {params['scope']}")

    # Override client_id
    print(f"Original client_id: {params.get('client_id', 'N/A')}")
    params["client_id"] = CLIENT_ID
    print(f"Overridden client_id: {CLIENT_ID}")

    # Encode original redirect_uri and state together in a new state parameter
    original_redirect_uri = params.get("redirect_uri", "")
    original_state = params.get("state", "")

    print(f"Original redirect_uri (URL encoded): {original_redirect_uri}")
    print(f"Original state (URL encoded): {original_state}")

    if original_redirect_uri:
        # URL-decode both state and redirect_uri before storing
        decoded_state = urllib.parse.unquote(original_state)
        decoded_redirect_uri = urllib.parse.unquote(original_redirect_uri)

        print(f"Decoded state: {decoded_state}")
        print(f"Decoded redirect_uri: {decoded_redirect_uri}")

        # Create compound state: base64(json({original_state, original_redirect_uri}))
        compound_state = {
            "state": decoded_state,
            "redirect_uri": decoded_redirect_uri,
        }
        encoded_state = base64.urlsafe_b64encode(
            json.dumps(compound_state).encode()
        ).decode()
        params["state"] = encoded_state

        print(f"Compound state created: {json.dumps(compound_state)}")
        print(f"Encoded state: {encoded_state}")

        # Replace redirect_uri with our callback
        api_url = get_api_url(event)
        params["redirect_uri"] = f"{api_url}/callback"
        print(f"New redirect_uri: {params['redirect_uri']}")

    print(f"Final params being sent to Cognito: {json.dumps(params)}")
    redirect_url = f"{COGNITO_DOMAIN.rstrip('/')}/oauth2/authorize?{urllib.parse.urlencode(params)}"
    print(f"Redirect URL: {redirect_url}")
    print("=== END HANDLE_AUTHORIZE DEBUG ===")

    return {"statusCode": 302, "headers": {"Location": redirect_url}, "body": ""}


def handle_callback(event):
    """Handle OAuth callback from Cognito and forward to VS Code.

    Decodes the compound state parameter to extract original redirect_uri and state.
    """
    params = event.get("queryStringParameters", {}) or {}
    code = params.get("code", "")
    encoded_state = params.get("state", "")
    error = params.get("error", "")

    print("=== HANDLE_CALLBACK DEBUG ===")
    print(f"Code: {code}")
    print(f"State (URL encoded): {encoded_state}")
    print(f"Error: {error}")

    if error:
        return json_response(400, {"error": error})

    # Decode compound state to get original redirect_uri and state
    try:
        # First, URL-decode the state parameter (Cognito sends it URL-encoded)
        encoded_state_clean = urllib.parse.unquote(encoded_state)
        print(f"State (URL decoded): {encoded_state_clean}")

        # Handle any remaining URL encoding issues (spaces become + or %20)
        encoded_state_clean = encoded_state_clean.replace(" ", "+")

        # The state should now be proper base64, no padding needed
        print(f"State (ready for base64 decode): {encoded_state_clean}")
        print(f"State length: {len(encoded_state_clean)}")

        decoded = base64.urlsafe_b64decode(encoded_state_clean).decode()
        print(f"Decoded JSON: {decoded}")

        compound_state = json.loads(decoded)
        original_state = compound_state.get("state", "")
        original_redirect_uri = compound_state.get("redirect_uri", "")

        print(f"Original state: {original_state}")
        print(f"Original redirect_uri: {original_redirect_uri}")
        print("=== END HANDLE_CALLBACK DEBUG ===")
    except Exception as e:
        print(f"Error decoding state: {e}, state={encoded_state}")
        print("=== END HANDLE_CALLBACK DEBUG (ERROR) ===")
        return json_response(400, {"error": "Invalid state parameter"})

    if not original_redirect_uri:
        return json_response(400, {"error": "Missing redirect_uri in state"})

    # Forward to VS Code's callback with original state
    forward_params = urllib.parse.urlencode({"code": code, "state": original_state})
    forward_url = f"{original_redirect_uri}?{forward_params}"

    return {"statusCode": 302, "headers": {"Location": forward_url}, "body": ""}


def handle_token(event):
    """Proxy token requests to Cognito with redirect_uri rewriting."""
    body = event.get("body", "")
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode()

    params = dict(urllib.parse.parse_qsl(body))

    # Override client_id and add secret
    params["client_id"] = CLIENT_ID
    if CLIENT_SECRET:
        params["client_secret"] = CLIENT_SECRET

    # Rewrite redirect_uri
    if "redirect_uri" in params:
        api_url = get_api_url(event)
        params["redirect_uri"] = f"{api_url}/callback"

    token_url = f"{COGNITO_DOMAIN.rstrip('/')}/oauth2/token"
    data = urllib.parse.urlencode(params).encode()

    req = urllib.request.Request(token_url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            token_data = json.loads(resp.read().decode())
            if "created_at" not in token_data:
                token_data["created_at"] = int(time.time() * 1000)
            return json_response(200, token_data)
    except urllib.error.HTTPError as e:
        return json_response(e.code, {"error": e.read().decode()})


def handle_dcr(event):
    """Handle Dynamic Client Registration - return pre-registered client_id."""
    return json_response(
        200,
        {
            "client_id": CLIENT_ID,
            "client_name": "VS Code Copilot MCP Client",
            "grant_types": ["authorization_code", "refresh_token"],
            "redirect_uris": [f"{get_api_url(event)}/callback"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
    )


def proxy_to_gateway(event):
    """Forward MCP requests to AgentCore Gateway."""
    print("proxy_to_gateway")
    path = event.get("path", "/")
    method = event.get("httpMethod") or event.get("requestContext", {}).get(
        "http", {}
    ).get("method", "GET")
    headers = event.get("headers", {})
    body = event.get("body", "")
    print(f"Proxying to gateway - Method: {method}, Path: {path}")
    print(f"Headers: {json.dumps(headers)}")
    if event.get("isBase64Encoded") and body:
        body = base64.b64decode(body)

    # target_url = f"{GATEWAY_URL.rstrip('/mcp')}{path}" if path != "/" else GATEWAY_URL
    target_url = GATEWAY_URL
    # Build request headers
    req_headers = {
        "Content-Type": headers.get("content-type", "application/json"),
        "Accept": headers.get("accept", "application/json"),
    }

    # Forward MCP headers
    for h in ["mcp-protocol-version", "mcp-session-id"]:
        if headers.get(h):
            req_headers[h.title()] = headers[h]

    print(json.dumps(req_headers))
    try:
        if method == "POST" and body:
            data = body.encode() if isinstance(body, str) else body
            req = urllib.request.Request(target_url, data=data, method="POST")
        else:
            req = urllib.request.Request(target_url, method=method)

        for k, v in req_headers.items():
            req.add_header(k, v)

        # This code is here in case ACG will support 3LO outbound with IAM auth in the future
        if os.environ.get("GATEWAY_AUTH", None) == "IAM":
            # Extract the userId from the inbound authorization token
            auth = headers.get("authorization")
            if auth:
                token = auth.split(" ")[1]
                user_id = json.loads(base64.b64decode(token.split(".")[1]))["sub"]
                req.add_header("X-Amzn-Bedrock-AgentCore-Runtime-User-Id", user_id)
            sign_request(req)
        else:
            # Forward auth header
            auth = headers.get("authorization")
            if auth:
                req.add_header("Authorization", auth)

        print(
            "{}\n{}\r\n{}\r\n\r\n{}".format(
                "-----------START-----------",
                (req.method or "GET") + " " + req.full_url,
                "\r\n".join("{}: {}".format(k, v) for k, v in req.headers.items()),
                req.data,
            )
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            resp_body = resp.read().decode()
            print(resp_body)
            print(resp.headers)
            resp_headers = {
                "Content-Type": resp.headers.get("Content-Type", "application/json")
            }

            # Forward session ID
            session_id = resp.headers.get("Mcp-Session-Id")
            if session_id:
                resp_headers["Mcp-Session-Id"] = session_id

            # Rewrite Gateway URLs in WWW-Authenticate header to use ALB endpoint
            www_auth = resp.headers.get("WWW-Authenticate")
            if www_auth:
                api_url = get_api_url(event)
                # Replace any Gateway URL references with ALB URL
                # Use removesuffix or string slicing to properly remove /mcp suffix
                gateway_base = (
                    GATEWAY_URL[:-4] if GATEWAY_URL.endswith("/mcp") else GATEWAY_URL
                )
                www_auth_rewritten = www_auth.replace(gateway_base, api_url)
                resp_headers["WWW-Authenticate"] = www_auth_rewritten
                print(f"Rewrote WWW-Authenticate: {www_auth} -> {www_auth_rewritten}")

            return {
                "statusCode": resp.status,
                "headers": resp_headers,
                "body": resp_body,
            }
    except urllib.error.HTTPError as e:
        error = e.read().decode()
        print(f"Gateway error response: {error}")

        # Rewrite any Gateway URLs in error response body
        api_url = get_api_url(event)
        # Use string slicing to properly remove /mcp suffix
        gateway_base = GATEWAY_URL[:-4] if GATEWAY_URL.endswith("/mcp") else GATEWAY_URL
        error_rewritten = error.replace(gateway_base, api_url)
        if error != error_rewritten:
            print("Rewrote Gateway URL in error body")

        resp_headers = {"Content-Type": "application/json"}

        # Rewrite WWW-Authenticate header if present
        www_auth = e.headers.get("WWW-Authenticate")
        if www_auth:
            www_auth_rewritten = www_auth.replace(gateway_base, api_url)
            resp_headers["WWW-Authenticate"] = www_auth_rewritten
            print(
                f"Rewrote WWW-Authenticate in error: {www_auth} -> {www_auth_rewritten}"
            )

        return {
            "statusCode": e.code,
            "headers": resp_headers,
            "body": error_rewritten,
        }
    except Exception as e:
        return json_response(502, {"error": {"code": -32603, "message": str(e)}})


def is_elicitation(data):
    """Check if response is a 3LO elicitation."""
    if not isinstance(data, dict):
        return False
    error = data.get("error", {})
    return isinstance(error, dict) and error.get("code") == -32042


def get_api_url(event):
    """Extract API URL from event (supports both ALB and API Gateway)."""
    # For ALB, use Host header
    headers = event.get("headers", {})
    host = headers.get("host") or headers.get("Host")
    if host:
        # ALB passes the actual domain in Host header
        return f"https://{host}"

    # Fallback to API Gateway format
    ctx = event.get("requestContext", {})
    domain = ctx.get("domainName", "")
    stage = ctx.get("stage", "")
    if domain and stage and stage != "$default":
        return f"https://{domain}/{stage}"
    elif domain:
        return f"https://{domain}"
    return "http://localhost"


def json_response(status_code, body):
    """Create JSON response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }
