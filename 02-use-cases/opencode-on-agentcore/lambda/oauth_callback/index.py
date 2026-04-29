# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""OAuth2 callback handler for AgentCore Identity 3LO flow."""

import json
import os
import urllib.request
import urllib.error
import botocore.session
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


REGION = os.environ.get("AWS_REGION", "us-east-1")


def handler(event, context):
    params = event.get("queryStringParameters") or {}
    session_id = params.get("session_id", "")
    state = params.get("state", "")

    print(f"Callback received: session_id={session_id}, state={state}")

    if not session_id:
        return _html(400, "Missing session_id parameter")

    user_id = ""
    if state:
        try:
            state_data = json.loads(state)
            user_id = state_data.get("user_id", "")
        except (json.JSONDecodeError, TypeError):
            user_id = state

    if not user_id:
        return _html(400, "Missing user identity in state parameter")

    try:
        session = botocore.session.get_session()
        credentials = session.get_credentials().get_frozen_credentials()

        url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/identities/CompleteResourceTokenAuth"
        body = json.dumps({
            "sessionUri": session_id,
            "userIdentifier": {"userId": user_id},
        })

        print(f"Calling {url} with body: {body}")

        aws_request = AWSRequest(method="POST", url=url, data=body, headers={
            "Content-Type": "application/json",
        })
        SigV4Auth(credentials, "bedrock-agentcore", REGION).add_auth(aws_request)

        req = urllib.request.Request(url, data=body.encode(), method="POST")
        for key, val in aws_request.headers.items():
            req.add_header(key, val)

        with urllib.request.urlopen(req) as resp:
            response_body = resp.read().decode()
            print(f"Success: {resp.status} {response_body}")

    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else "no body"
        print(f"HTTP {e.code}: {error_body}")
        print(f"Headers: {dict(e.headers)}")
        return _html(e.code, f"Authorization failed: HTTP {e.code} — {error_body}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        return _html(500, f"Authorization failed: {e}")

    return _html(200, "Authorization complete. You can close this tab and return to your MCP client.")


def _html(status_code, message):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "text/html; charset=utf-8"},
        "body": f"""<html>
<head><meta charset="utf-8"><title>OpenCode on AgentCore</title></head>
<body style="font-family:system-ui;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;">
<div style="text-align:center;"><h2>{message}</h2></div>
</body></html>""",
    }
