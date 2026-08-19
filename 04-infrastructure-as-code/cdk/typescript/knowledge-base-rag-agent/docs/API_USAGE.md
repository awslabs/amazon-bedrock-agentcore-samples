# API Usage Examples

This document provides examples of how to interact with your Bedrock Agent API programmatically.

## Authentication

First, obtain a JWT token from Cognito:

```javascript
import { CognitoIdentityProviderClient, InitiateAuthCommand } from "@aws-sdk/client-cognito-identity-provider";

const client = new CognitoIdentityProviderClient({ region: "us-east-1" });

const command = new InitiateAuthCommand({
  AuthFlow: "USER_PASSWORD_AUTH",
  ClientId: "your-user-pool-client-id",
  AuthParameters: {
    USERNAME: "user@example.com",
    PASSWORD: "password123"
  }
});

const response = await client.send(command);
const token = response.AuthenticationResult.IdToken;
```

## Chat API Examples

### Basic Chat Request

```javascript
const chatResponse = await fetch('https://your-api-gateway-url/v1/chat/invoke', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    message: "What is Amazon Bedrock?",
    sessionId: "user-session-123"
  })
});

const data = await chatResponse.json();
console.log(data.response);
```

### Python Example

```python
import requests
import json

def chat_with_agent(message, session_id, token, api_url):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    
    payload = {
        'message': message,
        'sessionId': session_id
    }
    
    response = requests.post(f'{api_url}/v1/chat/invoke', 
                           headers=headers, 
                           data=json.dumps(payload))
    
    if response.status_code == 200:
        return response.json()['response']
    else:
        raise Exception(f"API call failed: {response.status_code}")

# Usage
response = chat_with_agent(
    message="How do I configure my AI assistant?",
    session_id="python-session",
    token="your-jwt-token",
    api_url="https://your-api-gateway-url"
)
print(response)
```

### cURL Example

```bash
curl -X POST https://your-api-gateway-url/v1/chat/invoke \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "message": "Tell me about knowledge bases",
    "sessionId": "curl-session"
  }'
```

## Session Management

Maintain conversation context by using consistent session IDs:

```javascript
class AgentCoreClient {
  constructor(apiUrl, token) {
    this.apiUrl = apiUrl;
    this.token = token;
    this.sessionId = `session-${Date.now()}`;
  }

  async chat(message) {
    const response = await fetch(`${this.apiUrl}/v1/chat/invoke`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.token}`
      },
      body: JSON.stringify({
        message,
        sessionId: this.sessionId
      })
    });

    const data = await response.json();
    return data.response;
  }
}

// Usage - these messages will maintain context
const client = new AgentCoreClient('https://your-api-url', token);
const response1 = await client.chat("What is machine learning?");
const response2 = await client.chat("Can you give me an example?");
```

## Error Handling

```javascript
async function chatWithErrorHandling(message, sessionId, token, apiUrl) {
  try {
    const response = await fetch(`${apiUrl}/v1/chat/invoke`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ message, sessionId })
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication failed - token may be expired');
      } else if (response.status === 429) {
        throw new Error('Rate limit exceeded - please wait before retrying');
      } else if (response.status >= 500) {
        throw new Error('Server error - please try again later');
      } else {
        throw new Error(`API error: ${response.status}`);
      }
    }

    const data = await response.json();
    return data.response;

  } catch (error) {
    console.error('Chat error:', error.message);
    throw error;
  }
}
```

## React Integration

```javascript
import { useState, useCallback } from 'react';
import { Auth } from 'aws-amplify';

export function useAgentCore(apiUrl) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const chat = useCallback(async (message, sessionId = 'default') => {
    setLoading(true);
    setError(null);

    try {
      const session = await Auth.currentSession();
      const token = session.getIdToken().getJwtToken();

      const response = await fetch(`${apiUrl}/v1/chat/invoke`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ message, sessionId })
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      return data.response;

    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  return { chat, loading, error };
}
```

For more advanced integration patterns and examples, see the [APG Pattern Documentation](apg/pattern.md).
