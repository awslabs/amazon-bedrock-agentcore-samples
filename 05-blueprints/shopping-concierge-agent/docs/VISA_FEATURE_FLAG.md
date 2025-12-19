# Visa Integration Feature Flag

## Overview

This repository includes a feature flag system to toggle between the **real Visa Token Service API** and a **mock/fake implementation**. This allows you to develop and test the application without requiring actual Visa API credentials or making real API calls.

## Quick Start

### Disable Visa Integration (Use Mock API - Default)

By default, the Visa integration is **disabled** and uses a mock/fake API:

```bash
# Option 1: Don't set the environment variable (defaults to false)

# Option 2: Explicitly disable
export VISA_INTEGRATION_ENABLED=false

# Option 3: Use 0 to disable
export VISA_INTEGRATION_ENABLED=0
```

### Enable Visa Integration (Use Real API)

To use the real Visa Token Service API:

```bash
# Option 1: Set to true
export VISA_INTEGRATION_ENABLED=true

# Option 2: Set to 1
export VISA_INTEGRATION_ENABLED=1
```

## How It Works

The feature flag is controlled by the `VISA_INTEGRATION_ENABLED` environment variable:

- **When DISABLED** (`false`, `0`, or unset):
  - All Visa API calls are mocked/faked
  - No real HTTP requests are made to Visa servers
  - No Visa API credentials are required
  - Returns fake enrollment IDs, token IDs, and card tokens
  - Perfect for development and testing

- **When ENABLED** (`true` or `1`):
  - Uses the real Visa Token Service API
  - Requires valid Visa API credentials in AWS Secrets Manager
  - Makes actual HTTPS requests to Visa servers
  - Returns real enrollment data and secure tokens
  - Required for production use
