# Visa Iframe Integration Guide

## Overview

This integration allows your UI to embed the Visa iframe for secure card onboarding during the `onboard_card` tool invocation.

## Flow

```
User → Agent → onboard_card(use_iframe=True) → Returns iframe config → UI embeds iframe → User completes verification → Token sent back to agent
```

## Backend Integration

### 1. Agent Tool Call

When the agent calls `onboard_card` with `use_iframe=True`:

```python
from cart_manager.tools import onboard_card

result = onboard_card(
    card_number="4111111111111111",
    expiration_date="12/25",
    cvv="123",
    card_type="Visa",
    use_iframe=True  # Returns iframe config instead of processing
)

# Result:
{
    "success": True,
    "config": {
        "iframeUrl": "https://sandbox.secure.checkout.visa.com/wallet/v2/wallet.html",
        "apiKey": "YOUR_API_KEY", # pragma: allowlist secret
        "clientAppId": "VICTestAccountTR",
        "locale": "en_US",
        "userEmail": "user@example.com",
        "sessionId": "session_abc123"
    },
    "html": "<iframe src=...>",  # Ready-to-use HTML
    "message": "Please complete card verification in the Visa iframe"
}
```

### 2. Frontend Receives Config

Your chat UI receives this response and:
1. Detects `config.iframeUrl` in the response
2. Renders the `VisaIframe` component
3. Listens for token completion

## Frontend Integration

### React Component Usage

```tsx
import { VisaIframe } from './components/VisaIframe';

function ChatInterface() {
  const [iframeConfig, setIframeConfig] = useState(null);

  const handleAgentResponse = (response) => {
    // Check if response contains iframe config
    if (response.config?.iframeUrl) {
      setIframeConfig(response.config);
    }
  };

  const handleTokenReceived = async (secureToken) => {
    // Send token back to agent to complete onboarding
    await fetch('/api/agent/complete-visa-onboarding', {
      method: 'POST',
      body: JSON.stringify({
        sessionId: iframeConfig.sessionId,
        secureToken: secureToken
      })
    });
    
    setIframeConfig(null); // Close iframe
  };

  return (
    <div>
      {iframeConfig && (
        <VisaIframe
          config={iframeConfig}
          onTokenReceived={handleTokenReceived}
          onError={(err) => console.error(err)}
        />
      )}
      {/* Your chat UI */}
    </div>
  );
}
```

### Vanilla JavaScript

```html
<div id="visa-iframe-container"></div>

<script>
function embedVisaIframe(config) {
  const container = document.getElementById('visa-iframe-container');
  const iframe = document.createElement('iframe');
  
  iframe.src = `${config.iframeUrl}?apiKey=${config.apiKey}&clientAppId=${config.clientAppId}`;
  iframe.style.width = '100%';
  iframe.style.height = '600px';
  iframe.allow = 'payment; publickey-credentials-get';
  
  container.appendChild(iframe);
  
  // Listen for token
  window.addEventListener('message', (event) => {
    if (event.data.type === 'SECURE_TOKEN_RECEIVED') {
      completeOnboarding(config.sessionId, event.data.secureToken);
      container.innerHTML = ''; // Remove iframe
    }
  });
  
  // Initialize session
  iframe.onload = () => {
    iframe.contentWindow.postMessage({
      command: 'CREATE_AUTH_SESSION',
      apiKey: config.apiKey,
      clientAppId: config.clientAppId
    }, config.iframeUrl);
  };
}

async function completeOnboarding(sessionId, secureToken) {
  await fetch('/api/agent/complete-visa-onboarding', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId, secureToken })
  });
}
</script>
```

## Complete Backend Endpoint

Add an endpoint to complete onboarding after token is received:

```python
# In your agent API
@app.post("/api/agent/complete-visa-onboarding")
async def complete_visa_onboarding(request: Request):
    data = await request.json()
    session_id = data['sessionId']
    secure_token = data['secureToken']
    
    # Use the secure token to complete Visa enrollment
    from cart_manager.visa_onboarding import provision_token_with_secure_token
    
    result = provision_token_with_secure_token(
        secure_token=secure_token,
        email=get_user_email()
    )
    
    if result['success']:
        # Store token in user profile
        save_visa_token_to_profile(result['tokenData'])
    
    return result
```

## Testing

### 1. Test Backend
```bash
cd concierge_agent/code
python -c "
from cart_manager.tools import onboard_card
result = onboard_card(
    card_number='4111111111111111',
    expiration_date='12/25',
    cvv='123',
    use_iframe=True
)
print(result)
"
```

### 2. Test Frontend
Open browser console and paste the HTML from `result['html']`

## Security Notes

- Iframe uses `allow="payment; publickey-credentials-get"` for WebAuthn
- All communication via postMessage with origin verification
- Secure token is single-use and expires quickly
- Never store CVV or full card numbers

## Troubleshooting

**Iframe not loading:**
- Check CORS settings
- Verify API key is valid
- Ensure HTTPS (required by Visa)

**postMessage not working:**
- Verify origin in event listener
- Check iframe contentWindow is accessible
- Ensure iframe has loaded before sending messages

**Token not received:**
- Check browser console for errors
- Verify WebAuthn is supported
- Test with Visa sandbox credentials
