"""
Authentication module for Cognito integration
"""
import os
import base64
import json
import logging
from urllib.parse import urlencode
from typing import Optional, Dict, Any

import httpx
from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from jose import jwk, jwt
from jose.utils import base64url_decode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cognito configuration from environment variables
COGNITO_DOMAIN = os.getenv("COGNITO_DOMAIN")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")
COGNITO_CLIENT_SECRET = os.getenv("COGNITO_CLIENT_SECRET")
COGNITO_REDIRECT_URI = os.getenv("COGNITO_REDIRECT_URI")
COGNITO_LOGOUT_URI = os.getenv("COGNITO_LOGOUT_URI")
AWS_REGION = os.getenv("AWS_REGION")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")

# JWT validation
jwks_url = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
jwks = None

async def get_jwks():
    """Fetch the JSON Web Key Set from Cognito"""
    global jwks
    if jwks is None:
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url)
            jwks = response.json()
    return jwks

def get_login_url() -> str:
    """Generate the Cognito login URL"""
    # Use the Cognito hosted UI directly
    login_url = f"https://{COGNITO_DOMAIN}/login?client_id={COGNITO_CLIENT_ID}&response_type=code&redirect_uri={COGNITO_REDIRECT_URI}"
    
    # Debug logging
    logger.info(f"COGNITO_DOMAIN: {COGNITO_DOMAIN}")
    logger.info(f"COGNITO_CLIENT_ID: {COGNITO_CLIENT_ID}")
    logger.info(f"COGNITO_REDIRECT_URI: {COGNITO_REDIRECT_URI}")
    logger.info(f"Full login URL: {login_url}")
    
    return login_url

def get_logout_url() -> str:
    """Generate the Cognito logout URL"""
    params = {
        "client_id": COGNITO_CLIENT_ID,
        "logout_uri": COGNITO_LOGOUT_URI
    }
    return f"https://{COGNITO_DOMAIN}/logout?{urlencode(params)}"

async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    """Exchange authorization code for tokens"""
    token_endpoint = f"https://{COGNITO_DOMAIN}/oauth2/token"
    
    # Instead of using Authorization header, include client_id and client_secret in the form data
    data = {
        "grant_type": "authorization_code",
        "client_id": COGNITO_CLIENT_ID,
        "client_secret": COGNITO_CLIENT_SECRET,
        "code": code,
        "redirect_uri": COGNITO_REDIRECT_URI
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    logger.info(f"Exchanging code for tokens with client_id: {COGNITO_CLIENT_ID}")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_endpoint, headers=headers, data=data)
        
    if response.status_code != 200:
        logger.error(f"Token exchange failed: {response.text}")
        raise HTTPException(status_code=400, detail=f"Failed to exchange code for tokens: {response.text}")
        
    return response.json()

async def validate_token(token: str) -> Dict[str, Any]:
    """Validate the JWT token from Cognito"""
    # Get the key id from the token header
    header = jwt.get_unverified_header(token)
    kid = header["kid"]
    
    # Get the public key that matches the key id
    jwks_client = await get_jwks()
    key = None
    for jwk_key in jwks_client["keys"]:
        if jwk_key["kid"] == kid:
            key = jwk_key
            break
    
    if not key:
        raise HTTPException(status_code=401, detail="Invalid token: Key not found")
    
    # Verify the signature
    hmac_key = jwk.construct(key)
    message, encoded_signature = token.rsplit(".", 1)
    decoded_signature = base64url_decode(encoded_signature.encode())
    
    if not hmac_key.verify(message.encode(), decoded_signature):
        raise HTTPException(status_code=401, detail="Invalid token: Signature verification failed")
    
    # Verify the claims
    claims = jwt.get_unverified_claims(token)
    
    # Check expiration
    import time
    if claims["exp"] < time.time():
        raise HTTPException(status_code=401, detail="Token expired")
    
    # Check audience
    if claims["client_id"] != COGNITO_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Invalid audience")
    
    return claims

async def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get the current authenticated user from the session or simple cookie"""
    # Check for Cognito session first
    if "user" in request.session:
        return request.session["user"]
    
    # Check for simple login cookie as fallback
    simple_user = request.cookies.get("simple_user")
    if simple_user:
        return {"username": simple_user, "auth_type": "simple"}
    
    return None

def login_required(request: Request):
    """Dependency to check if user is logged in"""
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user
