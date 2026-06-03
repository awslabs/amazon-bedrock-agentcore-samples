#!/usr/bin/env bash
# Smoke-test the platform stack's ALB JWT validation end-to-end:
#   1. Get an access token from Okta.
#   2. Decode and print the claims (iss/aud/sub/role/exp/scp).
#   3. Hit the ALB with the token — expect 200 from the app.
#   4. Hit the ALB without a token — expect 401 from the ALB itself.
#
# Usage:
#   ALB_HOST=...  OKTA_ISSUER=...  OKTA_CLIENT_ID=...  OKTA_CLIENT_SECRET=... \
#       scripts/test_jwt.sh
#
#   # or, with a real user (Okta ROPC must be enabled on the authz server):
#   OKTA_USERNAME=...  OKTA_PASSWORD=...  ALB_HOST=...  ...  scripts/test_jwt.sh
#
#   # or, paste a token directly (e.g. from Okta's Token Preview tool):
#   OKTA_ACCESS_TOKEN=eyJ...  ALB_HOST=...  scripts/test_jwt.sh
#
# If ALB_HOST is unset, the script tries to read it from
# `infra/envs/dev/platform/terraform.tfstate`.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
platform_dir="$repo_root/infra/envs/dev/platform"

# Resolve ALB host.
if [[ -z "${ALB_HOST:-}" ]]; then
  if [[ -f "$platform_dir/terraform.tfstate" ]]; then
    ALB_HOST="$(cd "$platform_dir" && terraform output -raw alb_dns_name 2>/dev/null || true)"
  fi
fi
if [[ -z "${ALB_HOST:-}" ]]; then
  echo "ERROR: ALB_HOST is not set and could not be derived from the platform stack." >&2
  echo "       Set ALB_HOST=<dns> or run 'cd $platform_dir && terraform apply' first." >&2
  exit 1
fi

PATH_TO_TEST="${TEST_PATH:-/products}"

echo "→ ALB:     https://$ALB_HOST$PATH_TO_TEST"

if [[ -n "${OKTA_ACCESS_TOKEN:-}" ]]; then
  echo "→ Flow:    Pre-obtained token (OKTA_ACCESS_TOKEN)"
  token="$OKTA_ACCESS_TOKEN"
else
  : "${OKTA_ISSUER:?must be set (or pass OKTA_ACCESS_TOKEN to skip token fetch)}"
  : "${OKTA_CLIENT_ID:?must be set}"
  : "${OKTA_CLIENT_SECRET:?must be set}"
  SCOPES="${OKTA_SCOPES:-openid}"
  echo "→ Issuer:  $OKTA_ISSUER"

  if [[ -n "${OKTA_USERNAME:-}" && -n "${OKTA_PASSWORD:-}" ]]; then
    echo "→ Flow:    Resource Owner Password Credentials (user: $OKTA_USERNAME)"
    token_resp="$(curl -s -u "$OKTA_CLIENT_ID:$OKTA_CLIENT_SECRET" \
      --data-urlencode "grant_type=password" \
      --data-urlencode "username=$OKTA_USERNAME" \
      --data-urlencode "password=$OKTA_PASSWORD" \
      --data-urlencode "scope=$SCOPES" \
      "$OKTA_ISSUER/v1/token")"
  else
    echo "→ Flow:    Client Credentials"
    token_resp="$(curl -s -u "$OKTA_CLIENT_ID:$OKTA_CLIENT_SECRET" \
      --data-urlencode "grant_type=client_credentials" \
      --data-urlencode "scope=$SCOPES" \
      "$OKTA_ISSUER/v1/token")"
  fi

  token="$(echo "$token_resp" | jq -r '.access_token // empty')"
  if [[ -z "$token" ]]; then
    echo "ERROR: failed to obtain token from Okta. Response:" >&2
    echo "$token_resp" | jq . >&2 || echo "$token_resp" >&2
    exit 1
  fi
fi

echo
echo "── Token claims (already signed by Okta; ALB will re-verify) ──"
TOKEN="$token" python3 - <<'PY'
import base64, json, os
token = os.environ["TOKEN"]
payload = token.split(".")[1]
payload += "=" * (-len(payload) % 4)
claims = json.loads(base64.urlsafe_b64decode(payload))
keep = {k: claims.get(k) for k in ("iss", "aud", "sub", "role", "exp", "scp", "cid")}
print(json.dumps(keep, indent=2))
PY

echo
echo "── Test 1: WITH token (expect 200 from app) ─────────────────"
curl -ksi "https://$ALB_HOST$PATH_TO_TEST" -H "Authorization: Bearer $token" | head -15
echo

echo "── Test 2: WITHOUT token (expect 401 from ALB itself) ───────"
curl -ksi "https://$ALB_HOST$PATH_TO_TEST" | head -15
echo
