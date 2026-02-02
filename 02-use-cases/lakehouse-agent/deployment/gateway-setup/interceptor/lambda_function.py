"""
AgentCore Gateway Interceptor for Health Lakehouse Data

This Lambda function acts as a Gateway Interceptor following the AgentCore MCP protocol:
1. Extracts JWT bearer tokens from MCP gateway request structure
2. Validates JWT tokens against Cognito
3. Extracts user principal (email/username) from JWT claims
4. Adds user identity to request headers for downstream MCP server
5. Returns responses in proper MCP interceptor format

Reference: https://github.com/awslabs/amazon-bedrock-agentcore-samples/blob/main/01-tutorials/02-AgentCore-gateway/14-token-exchange-at-request-interceptor/

OAuth Flow:
  Streamlit → lakehouse-agent → Gateway (this interceptor) → MCP server
  
The interceptor extracts the principal from the JWT token and passes it to the MCP server
for Lake Formation row-level security enforcement.
"""

import json
import logging
import os
import boto3
from typing import Dict, Any, Optional
import urllib.request
import base64
from jose import jwt, JWTError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cache for configuration and keys
_config = None
_jwks = None


def get_config() -> Dict[str, str]:
    """
    Get Cognito configuration from environment variables or SSM.
    
    Returns:
        Dictionary with Cognito configuration
    """
    global _config
    
    if _config is not None:
        return _config
    
    # First try environment variables
    region = os.environ.get('COGNITO_REGION') or os.environ.get('AWS_REGION', 'us-west-2')
    user_pool_id = os.environ.get('COGNITO_USER_POOL_ID', '')
    app_client_id = os.environ.get('COGNITO_APP_CLIENT_ID', '')
    
    # If not set, try SSM Parameter Store
    if not user_pool_id or not app_client_id:
        logger.info("Loading Cognito configuration from SSM Parameter Store...")
        try:
            ssm = boto3.client('ssm', region_name=region)
            
            if not user_pool_id:
                response = ssm.get_parameter(Name='/app/lakehouse-agent/cognito-user-pool-id')
                user_pool_id = response['Parameter']['Value']
                logger.info(f"Loaded user_pool_id from SSM: {user_pool_id}")
            
            if not app_client_id:
                response = ssm.get_parameter(Name='/app/lakehouse-agent/cognito-app-client-id')
                app_client_id = response['Parameter']['Value']
                logger.info(f"Loaded app_client_id from SSM: {app_client_id}")
                
        except Exception as e:
            logger.error(f"Error loading configuration from SSM: {e}")
            raise
    
    _config = {
        'region': region,
        'user_pool_id': user_pool_id,
        'app_client_id': app_client_id,
        'issuer': f'https://cognito-idp.{region}.amazonaws.com/{user_pool_id}'
    }
    
    logger.info(f"Cognito configuration loaded: region={region}, user_pool_id={user_pool_id}")
    return _config


def get_cognito_public_keys() -> Dict[str, Any]:
    """
    Fetch Cognito public keys for JWT validation.

    Returns:
        Dictionary of public keys
    """
    global _jwks

    if _jwks is not None:
        return _jwks

    try:
        config = get_config()
        jwks_url = f"{config['issuer']}/.well-known/jwks.json"
        logger.info(f"Fetching JWKS from: {jwks_url}")
        
        with urllib.request.urlopen(jwks_url) as response:
            _jwks = json.loads(response.read())
            logger.info("Successfully fetched Cognito public keys")
            return _jwks
    except Exception as e:
        logger.error(f"Error fetching Cognito public keys: {str(e)}")
        raise


def validate_and_decode_jwt(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate JWT token and decode claims.

    Args:
        token: JWT bearer token

    Returns:
        Decoded JWT claims or None if invalid
    """
    try:
        config = get_config()
        
        # Get Cognito public keys
        jwks = get_cognito_public_keys()

        # Decode token header to get key ID
        unverified_headers = jwt.get_unverified_header(token)
        kid = unverified_headers.get('kid')

        # Find the correct public key
        key = None
        for k in jwks.get('keys', []):
            if k.get('kid') == kid:
                key = k
                break

        if not key:
            logger.error("Public key not found for token")
            return None

        # Validate and decode JWT
        # Note: For access tokens, we don't validate audience since Cognito
        # access tokens don't have 'aud' claim. We validate client_id instead.
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=['RS256'],
                audience=config['app_client_id'],
                issuer=config['issuer']
            )
        except JWTError as e:
            # If audience validation fails, try without audience (for access tokens)
            if 'audience' in str(e).lower() or 'aud' in str(e).lower():
                logger.info("Retrying JWT validation without audience check (access token)")
                claims = jwt.decode(
                    token,
                    key,
                    algorithms=['RS256'],
                    issuer=config['issuer'],
                    options={'verify_aud': False}
                )
                # Manually verify client_id for access tokens
                if claims.get('client_id') != config['app_client_id']:
                    logger.error(f"Client ID mismatch: {claims.get('client_id')} != {config['app_client_id']}")
                    return None
            else:
                raise

        logger.info(f"Successfully validated JWT for user: {claims.get('username', claims.get('sub'))}")
        return claims

    except JWTError as e:
        logger.error(f"JWT validation error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error validating JWT: {str(e)}")
        return None


def extract_bearer_token_from_mcp(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract bearer token from MCP gateway request structure.
    
    Following AgentCore Gateway MCP protocol, the event structure is:
    {
        "mcp": {
            "gatewayRequest": {
                "headers": {"Authorization": "Bearer <token>"},
                "body": {...}
            }
        }
    }

    Args:
        event: Lambda event with MCP structure

    Returns:
        Bearer token (without 'Bearer ' prefix) or None if not found
    """
    try:
        # Extract from MCP structure
        mcp_data = event.get('mcp', {})
        gateway_request = mcp_data.get('gatewayRequest', {})
        headers = gateway_request.get('headers', {})
        
        # Check Authorization header (case-insensitive)
        auth_header = headers.get('Authorization') or headers.get('authorization')
        
        if auth_header:
            # Remove 'Bearer ' prefix if present
            if auth_header.startswith('Bearer '):
                token = auth_header.replace('Bearer ', '', 1)
            elif auth_header.startswith('bearer '):
                token = auth_header.replace('bearer ', '', 1)
            else:
                token = auth_header
            
            logger.info(f"✅ Bearer token extracted from MCP gateway request")
            return token
        
        logger.warning("⚠️  Bearer token not found in MCP gateway request headers")
        return None
        
    except Exception as e:
        logger.error(f"❌ Error extracting bearer token from MCP structure: {str(e)}")
        return None


def extract_user_principal(claims: Dict[str, Any]) -> Optional[str]:
    """
    Extract user principal (identity) from JWT claims.
    
    The principal is used for Lake Formation row-level security.
    Priority order:
    1. email (preferred for user identification)
    2. username
    3. cognito:username
    4. sub (user ID as fallback)

    Args:
        claims: Decoded JWT claims

    Returns:
        User principal (email/username) or None
    """
    # Try multiple claim fields in priority order
    principal = (
        claims.get('email') or
        claims.get('username') or
        claims.get('cognito:username') or
        claims.get('sub')
    )

    if principal:
        logger.info(f"✅ Extracted user principal: {principal}")
        return principal

    logger.warning("⚠️  User principal not found in JWT claims")
    return None


def get_user_scopes(claims: Dict[str, Any]) -> list:
    """
    Extract OAuth scopes from JWT claims for logging and context.

    Args:
        claims: Decoded JWT claims

    Returns:
        List of scopes
    """
    # Scopes can be in 'scope' claim (space-separated) or 'cognito:groups'
    scope_string = claims.get('scope', '')
    scopes = scope_string.split() if scope_string else []

    # Add groups as scopes
    groups = claims.get('cognito:groups', [])
    if isinstance(groups, list):
        scopes.extend(groups)

    return scopes


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for AgentCore Gateway interceptor.
    
    Follows the MCP protocol for request interception:
    1. Extracts JWT token from MCP gateway request structure
    2. Validates JWT and extracts user principal
    3. Adds user identity to request for downstream MCP server
    4. Returns transformed request in MCP format
    
    Event Structure (Input):
    {
        "mcp": {
            "gatewayRequest": {
                "headers": {"Authorization": "Bearer <token>"},
                "body": {...}
            }
        }
    }
    
    Response Structure (Output):
    {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayRequest": {
                "headers": {...},
                "body": {...}
            }
        }
    }

    Args:
        event: Lambda event with MCP structure
        context: Lambda context

    Returns:
        Transformed request in MCP format or error response
    """
    logger.info("🔍 Gateway interceptor invoked")
    logger.info(f"📦 Event structure: {json.dumps(event, default=str)[:500]}...")

    try:
        # Extract MCP gateway request
        mcp_data = event.get('mcp', {})
        gateway_request = mcp_data.get('gatewayRequest', {})
        headers = gateway_request.get('headers', {})
        body = gateway_request.get('body', {})
        
        logger.info(f"📋 Headers present: {list(headers.keys())}")
        logger.info(f"📋 Body keys: {list(body.keys())}")
        
        # Extract bearer token from MCP structure
        token = extract_bearer_token_from_mcp(event)

        if not token:
            logger.error("❌ No bearer token found in request")
            return {
                'statusCode': 401,
                'body': json.dumps({
                    'error': 'Unauthorized',
                    'message': 'Bearer token required in Authorization header'
                })
            }

        # Validate and decode JWT
        claims = validate_and_decode_jwt(token)

        if not claims:
            logger.error("❌ JWT validation failed")
            return {
                'statusCode': 401,
                'body': json.dumps({
                    'error': 'Unauthorized',
                    'message': 'Invalid or expired JWT token'
                })
            }

        # Extract user principal from JWT claims
        user_principal = extract_user_principal(claims)

        if not user_principal:
            logger.error("❌ User principal not found in JWT claims")
            return {
                'statusCode': 401,
                'body': json.dumps({
                    'error': 'Unauthorized',
                    'message': 'User principal not found in token claims'
                })
            }

        # Get user scopes for logging
        scopes = get_user_scopes(claims)
        logger.info(f"👤 User: {user_principal}, Scopes: {scopes}")

        # Add user identity to headers for downstream MCP server
        # The MCP server will use X-User-Identity for Lake Formation RLS
        transformed_headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-User-Identity': user_principal,
            'X-User-Scopes': ','.join(scopes) if scopes else ''
        }

        # Also add user context to body if it has params/arguments
        # This ensures the MCP server can access user identity
        transformed_body = body.copy()
        if 'params' in transformed_body and 'arguments' in transformed_body['params']:
            if 'context' not in transformed_body['params']['arguments']:
                transformed_body['params']['arguments']['context'] = {}
            transformed_body['params']['arguments']['context']['user_id'] = user_principal
            transformed_body['params']['arguments']['context']['scopes'] = scopes

        # Return transformed request in MCP format
        response = {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayRequest": {
                    "headers": transformed_headers,
                    "body": transformed_body
                }
            }
        }

        logger.info(f"✅ Request authorized for user: {user_principal}")
        logger.info(f"📤 Returning transformed request")
        
        return response

    except Exception as e:
        logger.error(f"❌ Error in gateway interceptor: {str(e)}")
        import traceback
        logger.error(f"Stack trace: {traceback.format_exc()}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal Server Error',
                'message': f'Error processing request: {str(e)}'
            })
        }
