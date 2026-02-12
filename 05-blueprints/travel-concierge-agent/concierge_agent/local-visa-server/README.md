# Visa Local Backend Server

Local development server for Visa card onboarding and payment integration.

## Quick Start

### Prerequisites

1. **Python 3.11+** with `uv` package manager
2. **AWS credentials** with access to Visa secrets in Secrets Manager
3. **Hosts file entry** for Visa iframe CSP (see below)

### Setup

**You will need 2 terminals, both signed into your AWS account:**

- **Terminal 1**: Run the web UI (`npm run dev`) and open `https://vcas.local.com:9000`
- **Terminal 2**: Follow the steps below to run the Visa backend server and open `http://localhost:5001`

#### Terminal 2 - Visa Backend Server Setup

1. **Add hosts entry** (one-time setup):
   ```bash
   sudo sh -c 'echo "127.0.0.1 vcas.local.com" >> /etc/hosts'
   ```
   This is required because Visa's iframe CSP only allows whitelisted domains.

2. Navigate to this directory
    ```
    cd local-visa-server
    ```

3. Create virtual environment and install dependencies
    ```
    uv venv
    source .venv/bin/activate
    uv pip install -r requirements.txt
    ```

4. Add hosts entry for Visa iframe (one-time setup)
    This is required because Visa's iframe CSP only allows specific domains
    ```
    ../scripts/setup-visa-local.sh
    ```

5. Run the server
    ```
    python server.py
    ```

6. Go to the local host 

### Why the Hosts File Entry?

Visa's iframe sends a Content Security Policy (CSP) header that only allows specific domains:
```
frame-ancestors 'self' https://vcas.local.com:9000 ...
```

This is browser-enforced security - the iframe will refuse to load if your UI is not on a whitelisted domain. `vcas.local.com` is Visa's pre-registered test domain for sandbox development.

**Only the UI needs this** - the backend server can stay on `localhost:5001`.

## Server Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/api/visa/secure-token` | GET | Get Visa OAuth token |
| `/api/visa/onboard-card` | POST | Enroll card + provision token |
| `/api/visa/device-attestation` | POST | WebAuthn attestation |
| `/api/visa/device-binding` | POST | Bind device to token |
| `/api/visa/step-up` | POST | Select OTP method |
| `/api/visa/validate-otp` | POST | Validate OTP code |
| `/api/visa/complete-passkey` | POST | Complete passkey registration |
| `/api/visa/vic/enroll-card` | POST | VIC enrollment |
| `/api/visa/vic/initiate-purchase` | POST | Initiate purchase |
| `/api/visa/vic/payment-credentials` | POST | Get payment cryptogram |


## File Structure

```
local-visa-server/
├── server.py              # Main Flask server entry point
├── requirements.txt       # Python dependencies
├── README.md              # This file
├── visa/                  # Visa API integration
│   ├── __init__.py
│   ├── flow.py            # Visa flow orchestration
│   ├── api_wrapper.py     # Simplified wrapper functions
│   ├── secure_token.py    # Direct secure token API
│   └── helpers.py         # Utility functions
└── config/                # Configuration files
    └── .gitkeep
```

## Security Notes

- Card data never touches this server - it goes directly from iframe to Visa
- All Visa credentials are stored in AWS Secrets Manager
- CORS is restricted to known origins only
- Sensitive tokens are not logged
