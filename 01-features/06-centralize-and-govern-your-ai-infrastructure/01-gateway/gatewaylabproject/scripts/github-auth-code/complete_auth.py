"""Complete the authorization code flow for implicit sync target.

Starts a local callback server, opens the authorization URL,
and calls CompleteResourceTokenAuth after the user authorizes.

This is only needed for Method 1 (implicit sync) targets.

Usage:
    uv run python scripts/github-auth-code/complete_auth.py <authorization-url> <user-id>
"""

import os
import sys
import webbrowser

import boto3

AUTH_CODE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "01-attach-targets",
        "mcp",
        "mcp-servers",
        "01-configure-auth",
        "authorization-code-flow",
    )
)
sys.path.insert(0, os.path.join(AUTH_CODE_DIR, "utils"))


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: uv run python scripts/github-auth-code/complete_auth.py <auth-url> <user-id>"
        )
        print("\nGet these values from the deploy_target_implicit.py output.")
        sys.exit(1)

    auth_url = sys.argv[1]
    user_id = sys.argv[2]
    region = boto3.Session().region_name

    try:
        from utils import start_callback_and_open_auth

        start_callback_and_open_auth(auth_url, "user-id", user_id, region)
    except ImportError:
        print("Could not import utils. Opening URL in browser instead.")
        print(f"Authorization URL: {auth_url}")
        print(f"User ID: {user_id}")
        webbrowser.open(auth_url)
        print("\nComplete the authorization in your browser.")
        print("Then call CompleteResourceTokenAuth manually with the session URI.")


if __name__ == "__main__":
    main()
