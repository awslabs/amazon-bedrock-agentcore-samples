"""
Provider Setup: Coinbase Developer Platform (CDP)

Walk through creating a Coinbase account, enabling CDP, and saving the three
credentials that Tutorial 00 needs to .env.

What you'll get:
    COINBASE_API_KEY_ID     - Identifies your CDP API key
    COINBASE_API_KEY_SECRET - Authenticates your CDP API calls
    COINBASE_WALLET_SECRET  - Unlocks the wallet managed by CDP

NOTE: The Wallet Secret is shown only once at creation time. Save it immediately
to a secure location (AWS Secrets Manager, 1Password, etc.).

Usage:
    python coinbase_cdp_account_setup.py

Prerequisites:
    - A valid email address and phone number
    - Coinbase account (or create one at coinbase.com)
    - CDP API key + wallet secret from portal.cdp.coinbase.com
    - pip install -r requirements.txt
"""

import os
import sys

from dotenv import load_dotenv

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from utils import update_env_file

ENV_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
)
load_dotenv(ENV_FILE, override=True)

# ── Instructions ──────────────────────────────────────────────────────────────
print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║         Provider Setup: Coinbase Developer Platform (CDP)                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

MANUAL STEPS (complete in your browser before running the credential cells):

Step 1 — Create a Coinbase Account (skip if you have one)
──────────────────────────────────────────────────────────
  1. Go to https://coinbase.com/
  2. Choose Get started.
  3. Enter an email address.
  4. Create a password.
  5. Verify your email via the link Coinbase sends.
  6. Complete phone verification (SMS code).

Step 2 — Enable Coinbase Developer Platform
────────────────────────────────────────────
  1. Go to https://portal.cdp.coinbase.com/
  2. Sign in with your Coinbase account.
  3. Create a Project (or select an existing one).

Step 3a — Create an API Key
────────────────────────────
  1. In the CDP Portal, navigate to your project.
  2. Choose Create API key (or New key).
  3. Enter a descriptive name (e.g. agentcore-payments-tutorial).
  4. Choose Create or Save.
  5. Download the keys when prompted.
  → Gives you: API Key ID  →  COINBASE_API_KEY_ID
                API Key Secret  →  COINBASE_API_KEY_SECRET

Step 3b — Get the Wallet Secret
────────────────────────────────
  1. In the CDP Portal, go to Wallets → ServerWallet.
  2. Copy the Wallet Secret (sometimes called "wallet passphrase").
  → Gives you: Wallet Secret  →  COINBASE_WALLET_SECRET
  ⚠️  The Wallet Secret is shown only ONCE. Save it immediately.

Step 6 — Enable Delegated Signing (REQUIRED before Tutorial 00)
────────────────────────────────────────────────────────────────
  1. In CDP Portal → Wallets → Embedded Wallet → Policies tab.
  2. Enable Delegated Signing.
  Once enabled, all embedded wallets in this project support delegated signing.
""")

# ── Step 4: Paste credentials and save to .env ────────────────────────────────
print("── Step 4: Save Credentials to .env ──")
print("Paste your three Coinbase CDP credentials below.")
print("Press Enter after each value.\n")

COINBASE_API_KEY_ID = input("Coinbase API Key ID: ").strip()
COINBASE_API_KEY_SECRET = input("Coinbase API Key Secret: ").strip()
COINBASE_WALLET_SECRET = input("Coinbase Wallet Secret: ").strip()

# Validate
missing = []
for name, val in [
    ("COINBASE_API_KEY_ID", COINBASE_API_KEY_ID),
    ("COINBASE_API_KEY_SECRET", COINBASE_API_KEY_SECRET),
    ("COINBASE_WALLET_SECRET", COINBASE_WALLET_SECRET),
]:
    if not val or val.startswith("<"):
        missing.append(name)

if missing:
    print(
        f"\n❌ Missing values: {missing}"
    )  # codeql[py/clear-text-logging-sensitive-data]
    print("   Paste your values and re-run.")
    sys.exit(1)

result = update_env_file(
    ENV_FILE,
    {
        "CREDENTIAL_PROVIDER_TYPE": "CoinbaseCDP",
        "COINBASE_API_KEY_ID": COINBASE_API_KEY_ID,
        "COINBASE_API_KEY_SECRET": COINBASE_API_KEY_SECRET,
        "COINBASE_WALLET_SECRET": COINBASE_WALLET_SECRET,
    },
)
print(f"\n  ✅ Credentials saved to {os.path.abspath(ENV_FILE)}")
print("     CREDENTIAL_PROVIDER_TYPE=CoinbaseCDP")
print("\n  Never commit .env to git.")

# ── Step 5: Optional verification ────────────────────────────────────────────
print("\n── Step 5 (Optional): Verify Credentials ──")
print("To verify CDP connectivity, install the Coinbase CDP SDK and run:")
print("  pip install cdp-sdk")
print(
    "  python -c \"from cdp import Cdp; Cdp.configure('<KEY_ID>', '<KEY_SECRET>'); print('CDP configured')\""
)
print()
print("This step is optional — AgentCore payments validates credentials during")
print("CreatePaymentCredentialProvider (Tutorial 00 Step 4).")

# ── Checklist ─────────────────────────────────────────────────────────────────
print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Pre-Tutorial 00 Checklist                                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  [ ] .env has CREDENTIAL_PROVIDER_TYPE=CoinbaseCDP                         ║
║  [ ] .env has COINBASE_API_KEY_ID, COINBASE_API_KEY_SECRET,                ║
║      COINBASE_WALLET_SECRET filled in                                       ║
║  [ ] Credentials are NOT committed to git (.env is in .gitignore)          ║
║  [ ] Wallet Secret saved to a secure location                              ║
║  [ ] Delegated Signing enabled in CDP Portal                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

Next: python ../setup_agentcore_payments.py
""")
