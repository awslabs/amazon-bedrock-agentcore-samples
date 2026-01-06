# Frontend Mock Mode - No Visa Backend Required!

## Overview

You can use the **"Add Payment Method"** button **without Visa API credentials or local Visa server**! The frontend can use mock Visa API responses directly in the browser, allowing you to test the payment flow without any Visa integration setup.

## Quick Start (Default)

### 1. Enable Frontend Mock Mode

Edit `web-ui/.env.local`:

```bash
VITE_VISA_MOCK_MODE=true
```

**This is the default setting** - mock mode is enabled by default!

### 2. Start the Application

```bash
# From project root
npm run dev
```

That's it! No Visa server or credentials needed.

### 3. Test "Add Payment Method"

1. Open `https://vcas.local.com:9000`
2. Sign in or create a new user
3. Add items to cart using the shopping agent
4. Click **"Checkout"** or **"Add Payment Method"**
5. Fill in any test card details
6. Complete the flow (all steps are mocked in the browser!)


## Comparison

| Mode | Visa Server? | Setup | Speed |
|------|-------------|-------|-------|
| **Frontend Mock** (default) | ❌ Not needed | ✅ Just set env var | ⚡ Instant |
| **Real Visa API** | ✅ Required | Credentials + secrets | 🐌 Real API calls |

## Configuration Options

### Option 1: Frontend Mock Mode (Recommended for Development)

```bash
# web-ui/.env.local
VITE_VISA_MOCK_MODE=true
```

**Pros:**
- ✅ No backend server needed
- ✅ No Python setup required
- ✅ Instant responses
- ✅ No credentials needed
- ✅ Perfect for frontend development

**Cons:**
- ⚠️ Cannot test backend integration
- ⚠️ Cannot test real Visa API flow

### Option 2: Local Visa Server (Mock Mode)

```bash
# web-ui/.env.local
VITE_VISA_MOCK_MODE=false
VISA_INTEGRATION_ENABLED=true

# Terminal 1: Start local Visa server (real mode)
cd concierge_agent/local-visa-server
export VISA_INTEGRATION_ENABLED=true
python3 server.py

# Terminal 2: Start application
cd ../..
npm run dev
```

**Pros:**
- ✅ Tests real Visa integration
- ✅ Real card tokenization
- ✅ Real OTPs and biometrics

**Cons:**
- ⚠️ Requires Visa API credentials
- ⚠️ Requires Visa certificates in `infrastructure/certs/`
- ⚠️ Slowest option
- ⚠️ May incur API costs

**Note:** See [VISA_LOCAL_SETUP.md](./VISA_LOCAL_SETUP.md) for detailed setup instructions.

### Issue: Getting "fetch failed" errors

You probably have `VITE_VISA_MOCK_MODE=false` but the local Visa server isn't running.

**Fix:** Either:
1. Enable frontend mock: `VITE_VISA_MOCK_MODE=true`
2. Or start local Visa server: `cd concierge_agent/local-visa-server && python3 server.py`

### Issue: Want to test full stack integration

**Set to false:**
```bash
VITE_VISA_MOCK_MODE=false
```

**Start local Visa server:**
```bash
cd concierge_agent/local-visa-server
python3 server.py
```

**Start application:**
```bash
cd ../..
npm run dev
```

## Files Created

### New Frontend Mock Service
- **`web-ui/src/services/visaMockService.ts`** - Mock Visa API service
  - Provides all mock responses
  - Simulates network delays
  - Returns predictable test data

### Updated Components
- **`web-ui/src/components/VisaIframeAuth.tsx`** - Updated to use mock service
  - Checks `VITE_VISA_MOCK_MODE` environment variable
  - Routes to mock or backend based on setting
  - Logs current mode to console

### Configuration
- **`web-ui/.env.local`** - Added `VITE_VISA_MOCK_MODE=true`
- **`web-ui/.env.local.example`** - Template with all options documented

## Related Documentation

- [VISA_LOCAL_SETUP.md](./VISA_LOCAL_SETUP.md) - Setup local Visa server with real API
- [VISA_FEATURE_FLAG.md](./VISA_FEATURE_FLAG.md) - Complete feature flag system
- [VISA_IFRAME_INTEGRATION.md](./VISA_IFRAME_INTEGRATION.md) - Visa iframe integration details