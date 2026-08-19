# Visa Card Onboarding - Secrets Manager Setup

## Quick Start

### 1. Place Certificate Files

```bash
infrastructure/certs/
├── server_mle_cert.pem
└── mle_private_cert.pem
```

### 2. Edit Export Script

Edit `infrastructure/scripts/export-visa-secrets.sh` with your API keys:

```bash
export VISA_API_KEY="your_api_key_here" # pragma: allowlist secret
export VISA_SHARED_SECRET="your_shared_secret_here" # pragma: allowlist secret
export VISA_ENCRYPTION_API_KEY="your_encryption_api_key_here" # pragma: allowlist secret
export VISA_ENCRYPTION_SHARED_SECRET="your_encryption_shared_secret_here" # pragma: allowlist secret
```

### 3. Load and Deploy

```bash
cd infrastructure
source ./scripts/export-visa-secrets.sh
npm run deploy:agent
```

Done! Secrets are automatically created and populated.

---

## Manual Setup (Alternative)

If you prefer to set environment variables manually:

```bash
# Simple secrets
export VISA_API_KEY="your_key" # pragma: allowlist secret
export VISA_SHARED_SECRET="your_secret" # pragma: allowlist secret
export VISA_ENCRYPTION_API_KEY="your_enc_key" # pragma: allowlist secret
export VISA_ENCRYPTION_SHARED_SECRET="your_enc_secret" # pragma: allowlist secret
export VISA_KEY_ID_="your_key_id" # pragma: allowlist secret

# PEM files - load entire file content
export VISA_SERVER_MLE_CERT=$(cat path/to/server_mle_cert.pem)
export VISA_MLE_PRIVATE_CERT=$(cat path/to/mle_private_cert.pem)

# Deploy
npm run deploy:mcp
```

## Usage in Agent Code

```python
from cart_manager.visa_onboarding import complete_visa_onboarding

# Secrets are automatically fetched from Secrets Manager
result = complete_visa_onboarding(
    card_number="4111111111111111",
    cvv="123",
    exp_month="12",
    exp_year="2025",
    email="user@example.com"
)
```

## Cost

AWS Secrets Manager: **$0.40 per secret per month**
- 6 secrets = ~$2.40/month + API call costs

## Disable Visa Secrets

```typescript
visaSecrets: {
  enabled: false
}
```
