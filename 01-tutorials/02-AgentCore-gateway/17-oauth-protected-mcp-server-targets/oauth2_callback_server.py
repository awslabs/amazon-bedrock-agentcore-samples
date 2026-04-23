#!/usr/bin/env python3
"""
OAuth callback server for 3LO session binding.

Handles the OAuth redirect after user consents on an upstream provider (GitHub, Atlassian).
Calls complete_resource_token_auth to bind the 3LO token to the user's identity in the
AgentCore token vault.

Usage:
    python3 oauth2_callback_server.py <region> <port> <jwt_file>
"""
import http.server
import urllib.parse
import json
import os
import sys

PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
REGION = sys.argv[1] if len(sys.argv) > 1 else "us-west-2"
JWT_FILE = sys.argv[3] if len(sys.argv) > 3 else "/tmp/gateway-jwt"

import boto3
client = boto3.client("bedrock-agentcore", region_name=REGION)

SUCCESS_HTML = """<html><body style="font-family:system-ui;text-align:center;padding:60px;background:#f0fdf4">
<div style="display:inline-block;padding:40px 60px;border-radius:12px;background:white;box-shadow:0 2px 12px rgba(0,0,0,0.1);max-width:600px;text-align:left">
<h1 style="color:#16a34a;margin-bottom:8px;text-align:center">&#x2714; Session Binding Complete</h1>
<p style="color:#444;font-size:14px;line-height:1.6"><strong>What happened:</strong> You authorized the application to access your account on the upstream provider. The callback server called <code>complete-resource-token-auth</code> to bind the provider's access token to your user identity in the AgentCore token vault.</p>
<p style="color:#444;font-size:14px;line-height:1.6"><strong>What's next:</strong> The tool call will now succeed on retry. The gateway will automatically inject your provider token on subsequent requests.</p>
<p style="color:#999;font-size:13px;text-align:center;margin-top:20px">You can close this tab.</p>
</div></body></html>"""

ERROR_HTML = """<html><body style="font-family:system-ui;text-align:center;padding:60px;background:#fef2f2">
<div style="display:inline-block;padding:40px 60px;border-radius:12px;background:white;box-shadow:0 2px 12px rgba(0,0,0,0.1);max-width:600px;text-align:left">
<h1 style="color:#dc2626;margin-bottom:8px;text-align:center">&#x26A0; Session Binding Failed</h1>
<p style="color:#c00;font-size:14px;line-height:1.6"><strong>Error:</strong> {error}</p>
<p style="color:#444;font-size:14px;line-height:1.6"><strong>What's next:</strong> Retry the tool call to get a new elicitation URL.</p>
<p style="color:#999;font-size:13px;text-align:center;margin-top:20px">You can close this tab.</p>
</div></body></html>"""

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        sid = qs.get("session_id", [None])[0]

        if not sid:
            self._respond(200, "<html><body><p>Waiting for callback...</p></body></html>")
            return

        if not os.path.exists(JWT_FILE):
            print(f"[ADMIN] session_id={sid} | Admin authorization complete (console handles binding)", flush=True)
            self._respond(200, """<html><body style="font-family:system-ui;text-align:center;padding:60px;background:#f0fdf4">
<div style="display:inline-block;padding:40px 60px;border-radius:12px;background:white;box-shadow:0 2px 12px rgba(0,0,0,0.1);max-width:600px;text-align:left">
<h1 style="color:#16a34a;margin-bottom:8px;text-align:center">&#x2714; Gateway Target Authorization Complete</h1>
<p style="color:#444;font-size:14px;line-height:1.6"><strong>Flow:</strong> Gateway Admin — Target Creation</p>
<p style="color:#444;font-size:14px;line-height:1.6"><strong>What happened:</strong> You authorized the AgentCore Gateway to connect to the upstream MCP server (e.g., GitHub, Atlassian) during target creation. The OAuth consent was completed successfully.</p>
<p style="color:#444;font-size:14px;line-height:1.6"><strong>What's next:</strong> The gateway target will transition from <code>CREATE_PENDING_AUTH</code> to <code>READY</code> shortly. You can then proceed to test tool calls.</p>
<p style="color:#999;font-size:13px;text-align:center;margin-top:20px">You can close this tab.</p>
</div></body></html>""")
            return

        try:
            with open(JWT_FILE) as f:
                jwt = f.read().strip()
            client.complete_resource_token_auth(
                sessionUri=sid,
                userIdentifier={"userToken": jwt}
            )
            print(f"[OK] session_id={sid} | Binding complete", flush=True)
            self._respond(200, SUCCESS_HTML)
        except Exception as e:
            err = str(e)
            print(f"[ERROR] session_id={sid} | {err}", flush=True)
            self._respond(200, ERROR_HTML.format(error=err))

    def _respond(self, code, html):
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    print(f"Callback server listening on http://127.0.0.1:{PORT}", flush=True)
    with http.server.HTTPServer(("127.0.0.1", PORT), Handler) as s:
        s.serve_forever()
