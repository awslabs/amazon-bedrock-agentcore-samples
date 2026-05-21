"""
Provider Setup: Stripe (Privy)

Walk through creating a Privy app, generating an authorization key, and running
the Privy reference frontend so end users can grant AgentCore signing permission.

What you'll get:
    PRIVY_APP_ID                   - Identifies your Privy app
    PRIVY_APP_SECRET               - Authenticates your Privy API calls
    PRIVY_AUTHORIZATION_ID         - Key quorum ID for agent signing
    PRIVY_AUTHORIZATION_PRIVATE_KEY - P-256 private key AgentCore uses to authenticate to Privy

NOTE: The Authorization Private Key is displayed once in the Privy dashboard.
Copy it before closing the dialog.

Usage:
    python stripe_privy_account_setup.py

Prerequisites:
    - A valid email address
    - Node.js 18+ and git on your local machine (for the Privy reference frontend)
    - pip install -r requirements.txt
"""

import os
import sys

from dotenv import load_dotenv

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from utils import update_env_file, save_privy_authorization_key

ENV_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
)
load_dotenv(ENV_FILE, override=True)

# ── Instructions ──────────────────────────────────────────────────────────────
print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║         Provider Setup: Stripe (Privy)                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

MANUAL STEPS (complete in your browser before running the credential cells):

Step 1 — Create a Privy App
────────────────────────────
  1. Go to https://dashboard.privy.io and sign up (or log in).
  2. On the dashboard, choose New app.
  3. Enter an app name (e.g. AgentCore payments Tutorial).
  4. Choose Create app.
  5. Copy the App ID and App Secret from the dialog.
  6. Open User management → Authentication.
  7. Under Basics, make sure Email is enabled.
  8. Scroll to External wallets and enable both EVM wallets and SVM (Solana) wallets.

  NOTE: Create a DEDICATED Privy app for AgentCore payments. Do not reuse Privy
  apps that serve other purposes.
""")

# ── Step 1: Save App ID and App Secret ───────────────────────────────────────
print("── Step 1: Save Privy App Credentials ──")
print("Paste your Privy App ID and App Secret below.\n")

PRIVY_APP_ID = input("Privy App ID: ").strip()
PRIVY_APP_SECRET = input("Privy App Secret: ").strip()

if not PRIVY_APP_ID or PRIVY_APP_SECRET.startswith("<"):
    print("\n❌ Both App ID and App Secret are required.")
    sys.exit(1)

update_env_file(
    ENV_FILE,
    {
        "CREDENTIAL_PROVIDER_TYPE": "StripePrivy",
        "PRIVY_APP_ID": PRIVY_APP_ID,
        "PRIVY_APP_SECRET": PRIVY_APP_SECRET,
    },
)
print(f"  ✅ Saved PRIVY_APP_ID and PRIVY_APP_SECRET to {os.path.abspath(ENV_FILE)}")

# ── Step 2: Generate Authorization Key ────────────────────────────────────────
print("""
── Step 2: Generate Authorization Key ──

MANUAL STEPS in the Privy dashboard:
  1. In the Privy dashboard, make sure your app is selected in the left sidebar.
  2. Go to Wallet Infrastructure → Authorization.
  3. Choose New key.
  4. Enter a name (e.g. Demo app key).
  5. Choose Continue. Privy generates a P-256 keypair and displays the ID + Private Key.
  6. Copy BOTH values.
  7. Choose Save and close.

  NOTE: Privy prefixes the private key with 'wallet-auth:'.
  The script below strips this prefix automatically — paste the value exactly
  as Privy displays it.
""")

PRIVY_AUTHORIZATION_ID = input("Privy Authorization ID: ").strip()
PRIVY_AUTHORIZATION_PRIVATE_KEY = input("Privy Authorization Private Key: ").strip()

if not PRIVY_AUTHORIZATION_ID or not PRIVY_AUTHORIZATION_PRIVATE_KEY:
    print("\n❌ Both Authorization ID and Private Key are required.")
    sys.exit(1)

save_privy_authorization_key(
    env_path=ENV_FILE,
    authorization_id=PRIVY_AUTHORIZATION_ID,
    authorization_private_key=PRIVY_AUTHORIZATION_PRIVATE_KEY,
)
print(f"  ✅ Authorization ID: {PRIVY_AUTHORIZATION_ID}")
print(f"  ✅ 4 Privy env vars saved to {os.path.abspath(ENV_FILE)}")

# ── Step 3: Privy Reference Frontend ─────────────────────────────────────────
# Load current env values to generate the .env.local content
load_dotenv(ENV_FILE, override=True)
app_id = os.environ.get("PRIVY_APP_ID", PRIVY_APP_ID)
app_secret = os.environ.get("PRIVY_APP_SECRET", PRIVY_APP_SECRET)
auth_id = os.environ.get("PRIVY_AUTHORIZATION_ID", PRIVY_AUTHORIZATION_ID)

print("""
── Step 3: Set up the Privy Reference Frontend ──

These steps run on your LOCAL MACHINE (not this host) in a terminal.
The Privy reference frontend is a Next.js app that must serve from http://localhost:3000.

3a. Clone the Privy reference frontend:
──────────────────────────────────────
  git clone https://github.com/privy-io/aws-agentcore-sdk
  cd aws-agentcore-sdk

3b. Create .env.local with your credentials:
────────────────────────────────────────────
  Copy the .env.local content printed below into aws-agentcore-sdk/.env.local
""")

# Print the .env.local content
try:
    from utils import render_frontend_env_local

    env_local_body = render_frontend_env_local(
        app_id=app_id,
        app_secret=app_secret,
        signer_id=auth_id,
        network_mode="testnet",
    )
    print("─" * 72)
    print("  Copy everything between the lines into aws-agentcore-sdk/.env.local")
    print("─" * 72)
    print(env_local_body)
    print("─" * 72)
except Exception as exc:
    print(f"  (Could not render .env.local template: {exc})")
    print("  Manually create aws-agentcore-sdk/.env.local with:")
    print(f"    NEXT_PUBLIC_PRIVY_APP_ID={app_id}")
    print(
        f"    PRIVY_APP_SECRET={app_secret}"
    )  # codeql[py/clear-text-logging-sensitive-data]
    print(f"    PRIVY_AUTHORIZATION_ID={auth_id}")

print("""
3c. Install dependencies and start the dev server:
──────────────────────────────────────────────────
  npm install -g pnpm     # if pnpm not installed
  pnpm install
  pnpm dev

  When ready, you'll see: Local: http://localhost:3000

  NOTE: If pnpm install fails with a native-binding error, run:
    rm -rf node_modules && pnpm install

3d. Add the dev origin to your Privy app:
──────────────────────────────────────────
  1. In Privy dashboard → Configuration → App settings → Domains.
  2. Under Allowed origins → Web & mobile web, choose + Add.
  3. Enter http://localhost:3000
  4. Choose Save.

  PRODUCTION NOTE: Use HTTPS for production origins. Never reuse dev apps for prod.

3e. Log in to verify the Privy reference frontend works:
─────────────────────────────────────────────────────────
  1. Open http://localhost:3000 in your browser.
  2. Enter the email you want to use as the end-user account.
     Use the SAME email you plan to set as LINKED_EMAIL in .env.
  3. Submit the 6-digit OTP Privy sends to that email.

  Keep this browser tab open — you'll return to it in Tutorial 00 Step 7b
  after AgentCore provisions the wallet, to choose Connect agent.

  NOTE: The Connect agent step happens in Tutorial 00 Step 7b, NOT here.
  Consent is not possible until the wallet exists on the AgentCore side.
""")

# ── Checklist ─────────────────────────────────────────────────────────────────
print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  Pre-Tutorial 00 Checklist                                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  [ ] .env has CREDENTIAL_PROVIDER_TYPE=StripePrivy                         ║
║  [ ] .env has PRIVY_APP_ID, PRIVY_APP_SECRET,                              ║
║      PRIVY_AUTHORIZATION_ID, PRIVY_AUTHORIZATION_PRIVATE_KEY filled in     ║
║  [ ] Credentials are NOT committed to git (.env is in .gitignore)          ║
║  [ ] Authorization Private Key saved to a secure location                  ║
║  [ ] Privy app has Email + EVM wallets + SVM (Solana) wallets enabled      ║
║  [ ] Privy reference frontend running on http://localhost:3000             ║
║  [ ] localhost:3000 on the Privy allowed-origins list                      ║
║  [ ] Logged in as LINKED_EMAIL to verify the frontend works                ║
╚══════════════════════════════════════════════════════════════════════════════╝

Next: python ../setup_agentcore_payments.py
""")
