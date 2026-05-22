"""
Supabase authentication utilities for AgentCore Identity inbound auth.
Drop-in replacement for the Cognito helpers in ../utils.py.

Prerequisites before calling setup_supabase_auth():
  1. Create a Supabase project at https://supabase.com
  2. Change the JWT signing algorithm to RS256 or ES256:
       Project Settings > API > JWT Settings > JWT Algorithm
     (The default HS256 is symmetric and cannot be validated by AgentCore's
      customJWTAuthorizer, which fetches public keys from the JWKS endpoint.)
  3. Create a user in Supabase Auth (Authentication > Users > Add user),
     or use the sign-up flow and confirm the email.
"""

from supabase import create_client, Client


def setup_supabase_auth(
    supabase_url: str,
    supabase_anon_key: str,
    email: str,
    password: str,
) -> dict:
    """
    Sign in to Supabase and return an auth config dict analogous to
    setup_cognito_user_pool() in utils.py.

    The returned dict contains everything needed to configure the
    AgentCore customJWTAuthorizer and to invoke the agent.

    Args:
        supabase_url:      Your project URL, e.g. https://<ref>.supabase.co
        supabase_anon_key: The public anon key from Project Settings > API
        email:             Email of the Supabase Auth user
        password:          Password of the Supabase Auth user

    Returns:
        {
            "bearer_token":    Supabase JWT access token (valid ~1 hour),
            "refresh_token":   Token to obtain a new access token,
            "discovery_url":   OIDC discovery URL for AgentCore authorizer,
            "supabase_url":    Stored for re-authentication,
            "supabase_anon_key": Stored for re-authentication,
            "email":           Stored for re-authentication,
            "password":        Stored for re-authentication,
        }
    """
    client: Client = create_client(supabase_url, supabase_anon_key)
    response = client.auth.sign_in_with_password({"email": email, "password": password})

    session = response.session
    discovery_url = get_discovery_url(supabase_url)

    print(f"Discovery URL:   {discovery_url}")
    print(f"Bearer Token:    {session.access_token[:60]}...")
    print(f"Token expires:   {session.expires_at}")

    return {
        # aud="authenticated" in Supabase JWTs — use allowedAudience in AgentCore,
        # NOT allowedClients (which checks client_id, absent in direct sign-in tokens)
        "bearer_token": session.access_token,
        "refresh_token": session.refresh_token,
        "discovery_url": discovery_url,
        "email": email,
        "password": password,
        "supabase_url": supabase_url,
        "supabase_anon_key": supabase_anon_key,
    }


def reauthenticate_supabase_user(supabase_config: dict) -> str:
    """
    Obtain a fresh Supabase access token. Supabase tokens expire after ~1 hour.
    Equivalent to reauthenticate_user() from the Cognito utils.

    Args:
        supabase_config: dict returned by setup_supabase_auth()

    Returns:
        New JWT access token string
    """
    client: Client = create_client(
        supabase_config["supabase_url"],
        supabase_config["supabase_anon_key"],
    )
    response = client.auth.sign_in_with_password({
        "email": supabase_config["email"],
        "password": supabase_config["password"],
    })
    return response.session.access_token


def get_discovery_url(supabase_url: str) -> str:
    """Return the OIDC discovery URL for the Supabase project."""
    return f"{supabase_url}/auth/v1/.well-known/openid-configuration"
