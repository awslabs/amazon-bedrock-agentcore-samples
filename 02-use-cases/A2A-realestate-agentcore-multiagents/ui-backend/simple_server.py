#!/usr/bin/env python3
"""
Minimal Backend API - Connects UI to deployed agents
Can run locally or deploy to AWS Lambda
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import requests
from datetime import datetime, timedelta
import base64
from uuid import uuid4

app = Flask(__name__)
CORS(app)

# Cache for token
_token_cache = {'token': None, 'expiry': None}

def get_config():
    """Load deployment configuration."""
    config_path = os.path.join(os.path.dirname(__file__), '../deployment_info.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_oauth_token():
    """Get OAuth token (cached or fresh)."""
    global _token_cache
    
    # Return cached token if still valid
    if _token_cache['token'] and _token_cache['expiry'] and datetime.now() < _token_cache['expiry']:
        return _token_cache['token']
    
    # Try to load token from file first
    token_file = os.path.join(os.path.dirname(__file__), '../.bearer_token')
    if os.path.exists(token_file):
        # Use file modification time + 50 minutes as expiry (Cognito tokens last 60 min)
        file_mtime = datetime.fromtimestamp(os.path.getmtime(token_file))
        token_expiry = file_mtime + timedelta(minutes=50)
        if datetime.now() < token_expiry:
            with open(token_file, 'r', encoding='utf-8') as f:
                token = f.read().strip()
                if token:
                    _token_cache['token'] = token
                    _token_cache['expiry'] = token_expiry
                    print(f"✓ Loaded token from file (expires: {token_expiry})")
                    return token
    
    # Get fresh token
    print("Generating fresh OAuth token...")
    config = get_config()
    cognito_config = config['cognito_config']
    
    # Get client secret from AWS
    import boto3
    cognito = boto3.client('cognito-idp', region_name='us-east-1')
    
    try:
        response = cognito.describe_user_pool_client(
            UserPoolId=cognito_config['user_pool_id'],
            ClientId=cognito_config['client_id']
        )
        client_secret = response['UserPoolClient']['ClientSecret']
    except Exception as e:
        raise Exception(f"Failed to get client secret: {e}")
    
    # Get domain
    pool_response = cognito.describe_user_pool(UserPoolId=cognito_config['user_pool_id'])
    domain = pool_response['UserPool']['Domain']
    
    # Request token
    token_endpoint = f"https://{domain}.auth.us-east-1.amazoncognito.com/oauth2/token"
    auth_string = f"{cognito_config['client_id']}:{client_secret}"
    auth_b64 = base64.b64encode(auth_string.encode('ascii')).decode('ascii')
    
    response = requests.post(
        token_endpoint,
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {auth_b64}'
        },
        data={
            'grant_type': 'client_credentials',
            'scope': 'a2a-agents/invoke'
        },
        timeout=30
    )
    
    if response.status_code == 200:
        token_data = response.json()
        _token_cache['token'] = token_data['access_token']
        _token_cache['expiry'] = datetime.now() + timedelta(seconds=token_data['expires_in'] - 60)
        
        # Save to file
        with open(token_file, 'w', encoding='utf-8') as f:
            f.write(_token_cache['token'])
        
        print(f"✓ Generated fresh token (expires in {token_data['expires_in']} seconds)")
        return _token_cache['token']
    else:
        raise Exception(f"Failed to get token: {response.text}")

def call_agent(agent_arn, message):
    """Call an agent via AgentCore Runtime API."""
    token = get_oauth_token()
    
    # Construct runtime URL
    arn_encoded = agent_arn.replace(':', '%3A').replace('/', '%2F')
    base_url = f"https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/{arn_encoded}/invocations/"
    
    # Create JSON-RPC request
    session_id = str(uuid4())
    message_id = str(uuid4())
    
    jsonrpc_request = {
        "jsonrpc": "2.0",
        "id": f"req-{uuid4().hex[:8]}",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": message}],
                "messageId": message_id
            }
        }
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}',
        'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': session_id
    }
    
    response = requests.post(base_url, headers=headers, json=jsonrpc_request, timeout=120)
    
    if response.status_code == 200:
        result = response.json()
        if 'result' in result and 'artifacts' in result['result']:
            artifacts = result['result']['artifacts']
            if artifacts and 'parts' in artifacts[0]:
                return artifacts[0]['parts'][0].get('text', 'No response')
        return str(result)
    else:
        raise Exception(f"Agent call failed: {response.status_code} - {response.text}")

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages - route to appropriate agent."""
    try:
        data = request.json
        message = data.get('message', '')
        
        if not message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400
        
        config = get_config()
        
        # Simple routing logic - you can make this smarter
        message_lower = message.lower()
        
        # Determine which agent to call
        if any(word in message_lower for word in ['book', 'booking', 'reserve', 'reservation']):
            # Call booking agent
            agent = next(a for a in config['agents'] if 'booking' in a['name'])
            response_text = call_agent(agent['arn'], message)
        else:
            # Call search agent by default
            agent = next(a for a in config['agents'] if 'search' in a['name'])
            response_text = call_agent(agent['arn'], message)
        
        return jsonify({
            'success': True,
            'response': response_text,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        import traceback
        import logging
        
        # Log the full error internally
        logging.error(f"Error in chat endpoint: {str(e)}")
        logging.error(traceback.format_exc())
        
        # Return generic error message to client (don't expose stack trace)
        return jsonify({
            'success': False,
            'error': 'An error occurred processing your request. Please try again.',
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    print("="*70)
    print("Minimal Backend API - Connecting to Cloud Agents")
    print("="*70)
    print("Starting server on http://localhost:5000")
    print("="*70)
    print("\n⚠️  WARNING: Debug mode should not be used in production!")
    print("    Set debug=False for production deployments.\n")
    # Use environment variable to control debug mode
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    # Local development only — use gunicorn/waitress for production
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)  # nosec B104  # nosemgrep
