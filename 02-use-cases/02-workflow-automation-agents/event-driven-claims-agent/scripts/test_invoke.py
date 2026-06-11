#!/usr/bin/env python3
"""Invoke the Claims Agent runtime with JWT auth and display clean streamed output.

Usage:
    python3 scripts/test_invoke.py --region us-west-2
    python3 scripts/test_invoke.py --region us-west-2 --prompt 'Your claim text here'
"""

import argparse
import base64
import json
import sys
import urllib.parse
import urllib.request

import boto3


def get_cognito_token(region: str) -> tuple[str, str]:
    """Get M2M token from Cognito using client_credentials flow."""
    cf = boto3.client("cloudformation", region_name=region)
    outputs = cf.describe_stacks(StackName="ClaimsInfraStack")["Stacks"][0]["Outputs"]
    output_map = {o["OutputKey"]: o["OutputValue"] for o in outputs}

    user_pool_id = output_map["UserPoolId"]
    client_id = output_map["UserPoolClientId"]
    runtime_arn = output_map.get("RuntimeArn", "")

    cognito = boto3.client("cognito-idp", region_name=region)
    client_info = cognito.describe_user_pool_client(UserPoolId=user_pool_id, ClientId=client_id)
    cs = client_info["UserPoolClient"]["ClientSecret"]

    pool_info = cognito.describe_user_pool(UserPoolId=user_pool_id)
    domain = pool_info["UserPool"].get("Domain", "")
    token_endpoint = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"

    creds = base64.b64encode(f"{client_id}:{cs}".encode()).decode()
    data = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "scope": "agentcore/invoke",
        }
    ).encode()

    req = urllib.request.Request(
        token_endpoint,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {creds}",
        },
    )

    if not token_endpoint.startswith("https://"):
        raise ValueError(f"Only HTTPS URLs are permitted: {token_endpoint}")
    with urllib.request.urlopen(req) as resp:  # nosec B310
        token_data = json.loads(resp.read())

    return token_data["access_token"], runtime_arn


def invoke_and_stream(token: str, runtime_arn: str, region: str, prompt: str):
    """Invoke the agent and stream clean formatted output to terminal."""
    escaped_arn = urllib.parse.quote(runtime_arn, safe="")
    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations"

    payload = json.dumps({"prompt": prompt}).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    print("\033[90m━━━ Agent Response ━━━\033[0m\n")

    try:
        if not url.startswith("https://"):
            raise ValueError(f"Only HTTPS URLs are permitted: {url}")
        with urllib.request.urlopen(req, timeout=180) as resp:  # nosec B310
            for line in resp:
                decoded = line.decode("utf-8").strip()
                if not decoded:
                    continue

                if decoded.startswith("data: "):
                    chunk = decoded[6:]
                    # JSON-unescape quoted strings
                    if chunk.startswith('"') and chunk.endswith('"'):
                        try:
                            chunk = json.loads(chunk)
                        except json.JSONDecodeError:
                            chunk = chunk[1:-1]
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                elif decoded.startswith("{") and "error" in decoded:
                    try:
                        err = json.loads(decoded)
                        print(f"\n\033[91m❌ Error: {err.get('error', decoded)}\033[0m")
                    except json.JSONDecodeError:
                        print(f"\n\033[91m❌ {decoded}\033[0m")

        print("\n\n\033[90m━━━━━━━━━━━━━━━━━━━━━\033[0m")

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"\n\033[91m❌ HTTP {e.code}: {body}\033[0m")


def main():
    parser = argparse.ArgumentParser(description="Invoke Claims Agent with JWT")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument(
        "--prompt",
        default="I need to file a claim. My policy is POL-12345. Fender bender yesterday, $2000 damage.",
    )
    args = parser.parse_args()

    print("\033[90m🔑 Authenticating...\033[0m")
    token, runtime_arn = get_cognito_token(args.region)
    print(f"\033[90m✅ Connected to {runtime_arn.split('/')[-1]}\033[0m")
    print(f"\033[90m📝 {args.prompt}\033[0m\n")

    invoke_and_stream(token, runtime_arn, args.region, args.prompt)


if __name__ == "__main__":
    main()
