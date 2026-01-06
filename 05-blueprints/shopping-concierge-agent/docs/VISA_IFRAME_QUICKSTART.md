# Visa Iframe Integration - Quick Start

## What Happens Now

When a user clicks **"💳 Add Payment Card"** button:

1. ✅ Frontend calls agent: `"Get Visa iframe config for card onboarding"`
2. ✅ Agent calls `get_visa_iframe_config()` tool
3. ✅ Returns iframe configuration with Visa URL and API keys
4. ✅ Frontend embeds `VisaIframe` component
5. ✅ User completes verification in Visa iframe
6. ✅ Secure token sent back to agent
7. ✅ Agent completes card onboarding

## Files Modified

### Backend
- ✅ `cart_manager/visa_iframe.py` - New module for iframe config
- ✅ `cart_manager/tools.py` - Added `get_visa_iframe_config()` tool
- ✅ `cart_manager/agent.py` - Added tool to agent

### Frontend
- ✅ `components/VisaIframe.tsx` - React component for iframe
- ✅ `components/Chat.tsx` - Updated button to launch iframe

## Testing

### 1. Start the app
```bash
npm run dev
```

### 2. Click "Add Payment Card" button
The button appears when agent mentions card onboarding

### 3. Verify iframe loads
Should see Visa secure checkout iframe

### 4. Complete verification
Follow Visa's authentication flow

## Fallback

If iframe config fails, automatically falls back to `CardOnboardingForm`

## Environment Variables Needed

```bash
export VISA_API_KEY= "your_key" # pragma: allowlist secret
export VISA_CLIENT_APP_ID= "VICTestAccountTR"  # Optional, has default
```

## Next Steps

1. Deploy with Visa credentials in Secrets Manager
2. Test with real Visa sandbox credentials
3. Handle token completion in backend
4. Store tokenized card data in user profile

## Troubleshooting

**Iframe not showing:**
- Check browser console for errors
- Verify `get_visa_iframe_config` tool is registered
- Check agent response contains `config.iframeUrl`

**postMessage not working:**
- Verify iframe origin matches Visa domain
- Check browser allows iframe embedding
- Ensure HTTPS (required by Visa)
