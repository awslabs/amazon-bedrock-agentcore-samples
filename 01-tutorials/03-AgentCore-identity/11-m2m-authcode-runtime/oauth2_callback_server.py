"""
Local OAuth2 callback server for the 3-legged (authorization code) flow.

This server handles the OAuth2 redirect from Google (or any IdP) after the user
grants consent. It performs OAuth2 session binding with AgentCore Identity, which
ensures the access token is securely associated with the authenticated user.

See: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/oauth2-authorization-url-session-binding.html

Usage:
    # Start the server (runs on http://localhost:9090)
    python oauth2_callback_server.py --region us-west-2

    # Store user token before invoking the agent (so session binding can verify user identity)
    python oauth2_callback_server.py --store-token <bearer_token>

    # Get the public callback URL (works in both local and SageMaker environments)
    python oauth2_callback_server.py --get-url
"""

import argparse
import json
import os
import sys
import time
import threading

import boto3
import requests

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, PlainTextResponse
    import uvicorn
except ImportError:
    raise SystemExit(
        "fastapi and uvicorn are required.\n"
        "Install with: pip install -r requirements.txt"
    )

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 9090
_user_token_store: dict = {}


def get_oauth2_callback_url() -> str:
    """Return the publicly accessible callback URL for this server."""
    # SageMaker Studio environment
    sagemaker_domain = os.environ.get("SAGEMAKER_STUDIO_DOMAIN_ID", "")
    if sagemaker_domain:
        sm_app_url = os.environ.get("STUDIO_APP_URL", "")
        if sm_app_url:
            return f"{sm_app_url.rstrip('/')}/proxy/9090/oauth2/callback"

    # Default: local
    return f"http://localhost:{SERVER_PORT}/oauth2/callback"


def store_token_in_oauth2_callback_server(bearer_token: str) -> bool:
    """Store the user's bearer token in the callback server before invoking the agent."""
    try:
        resp = requests.post(
            f"http://localhost:{SERVER_PORT}/userIdentifier/token",
            json={"token": bearer_token},
            timeout=5,
        )
        return resp.status_code == 200
    except requests.ConnectionError:
        return False


def wait_for_oauth2_server_to_be_ready(timeout: int = 30) -> bool:
    """Poll the /ping endpoint until the callback server is ready."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(f"http://localhost:{SERVER_PORT}/ping", timeout=2)
            if resp.status_code == 200:
                return True
        except requests.ConnectionError:
            time.sleep(1)
    return False


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="AgentCore OAuth2 Callback Server")


@app.get("/ping")
async def ping():
    return PlainTextResponse("ok")


@app.post("/userIdentifier/token")
async def store_token(request: Request):
    """Store the user's Cognito bearer token for session binding validation."""
    body = await request.json()
    _user_token_store["token"] = body.get("token", "")
    return JSONResponse({"status": "ok"})


@app.get("/oauth2/callback")
async def oauth2_callback(request: Request):
    """
    Handle the OAuth2 redirect from Google (or any IdP).

    AgentCore Identity redirects here with a `session_id` parameter after the
    user grants consent. We then call CompleteResourceTokenAuth to bind the
    OAuth session to the authenticated user.
    """
    session_id = request.query_params.get("session_id", "")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    if not session_id:
        return PlainTextResponse("Missing session_id parameter", status_code=400)

    user_token = _user_token_store.get("token", "")
    if not user_token:
        return PlainTextResponse(
            "No user token stored. Call /userIdentifier/token first.", status_code=400
        )

    # Complete the OAuth2 session binding
    try:
        client = boto3.client("bedrock-agentcore-control", region_name=region)
        client.complete_resource_token_auth(
            sessionId=session_id,
            userToken=user_token,
        )
        return PlainTextResponse(
            "Authorization complete! You can close this tab and return to your agent.",
            status_code=200,
        )
    except Exception as exc:
        return PlainTextResponse(
            f"Error completing auth: {exc}", status_code=500
        )


def run_server(region: str):
    os.environ["AWS_DEFAULT_REGION"] = region
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="warning")


def main():
    parser = argparse.ArgumentParser(description="AgentCore OAuth2 Callback Server")
    parser.add_argument("--region", default=None, help="AWS region")
    parser.add_argument("--store-token", metavar="TOKEN", help="Store a bearer token and exit")
    parser.add_argument("--get-url", action="store_true", help="Print callback URL and exit")
    args = parser.parse_args()

    if args.get_url:
        print(get_oauth2_callback_url())
        return

    if args.store_token:
        ok = store_token_in_oauth2_callback_server(args.store_token)
        print("Token stored." if ok else "Error: server not running.")
        return

    region = args.region or boto3.session.Session().region_name or "us-east-1"
    print(f"Starting OAuth2 callback server on http://localhost:{SERVER_PORT}")
    print(f"Callback URL: {get_oauth2_callback_url()}")
    run_server(region)


if __name__ == "__main__":
    main()
