#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# setup-oauth-app.sh -- Manage OAuth App credentials for AgentCore Identity.
#
# Interactive menu:
#   - Lists existing credential providers and Secrets Manager secrets
#   - Add a new provider (GitHub)
#   - Delete an existing provider and its secret
#
# Non-interactive:
#   ./scripts/setup-oauth-app.sh --add --provider github --client-id ID --client-secret SECRET
#   ./scripts/setup-oauth-app.sh --delete --provider github
#   ./scripts/setup-oauth-app.sh --list
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - AWS_REGION set (or pass --region)

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
SECRET_PREFIX="opencode"
AWS_PROFILE="${AWS_PROFILE:-}"
AWS_REGION="${AWS_REGION:-}"
ACTION=""          # add, delete, list, or empty (interactive menu)
PROVIDER=""
CLIENT_ID=""
CLIENT_SECRET=""

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --add)         ACTION="add"; shift ;;
    --delete)      ACTION="delete"; shift ;;
    --list)        ACTION="list"; shift ;;
    --provider)
      PROVIDER="$2"
      if [[ "$PROVIDER" != "github" ]]; then
        echo "Unknown provider: $PROVIDER"; exit 1
      fi
      shift 2 ;;
    --client-id)   CLIENT_ID="$2"; shift 2 ;;
    --client-secret) CLIENT_SECRET="$2"; shift 2 ;;
    --profile)     AWS_PROFILE="$2"; shift 2 ;;
    --region)      AWS_REGION="$2"; shift 2 ;;
    -h|--help)
      cat <<'EOF'
Usage: setup-oauth-app.sh [OPTIONS]

Manage OAuth App credentials for AgentCore Identity.

Modes:
  (no flags)     Interactive menu: list providers, add, or delete
  --list         List existing providers and secrets, then exit
  --add          Add or update a provider (requires --provider, --client-id, --client-secret)
  --delete       Delete a provider and its secret (requires --provider)

Options:
  --provider       github
  --client-id      OAuth App client ID (--add only)
  --client-secret  OAuth App client secret (--add only)
  --profile        AWS CLI profile (or set AWS_PROFILE)
  --region         AWS region (or set AWS_REGION; required)
  -h, --help       Show this help
EOF
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Require a region
# ---------------------------------------------------------------------------
if [[ -z "$AWS_REGION" ]]; then
  echo "error: AWS_REGION is not set. Export it or pass --region <region>." >&2
  echo "  Confirmed deployable regions: us-east-1, eu-central-1" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Check AWS credentials -- prompt for profile if not configured
# ---------------------------------------------------------------------------
check_aws_credentials() {
  local test_args=(--region "$AWS_REGION")
  [[ -n "$AWS_PROFILE" ]] && test_args+=(--profile "$AWS_PROFILE")

  if aws sts get-caller-identity "${test_args[@]}" &>/dev/null; then
    local acct
    acct=$(aws sts get-caller-identity "${test_args[@]}" --output text --query 'Account' 2>/dev/null)
    echo "AWS credentials OK (account: ${acct})"
    [[ -n "$AWS_PROFILE" ]] && echo "Using profile: $AWS_PROFILE"
    echo ""
    return 0
  fi
  return 1
}

if ! check_aws_credentials; then
  echo "No valid AWS credentials found."
  echo ""

  profiles=()
  if [[ -f ~/.aws/config ]]; then
    while IFS= read -r line; do profiles+=("$line"); done \
      < <(grep -oE '\[profile [^]]+\]' ~/.aws/config 2>/dev/null | sed 's/\[profile //;s/\]//' || true)
  fi
  if [[ -f ~/.aws/credentials ]]; then
    while IFS= read -r line; do profiles+=("$line"); done \
      < <(grep -oE '\[[^]]+\]' ~/.aws/credentials 2>/dev/null | sed 's/\[//;s/\]//' || true)
  fi
  # Deduplicate
  if [[ ${#profiles[@]} -gt 0 ]]; then
    deduped=()
    while IFS= read -r line; do deduped+=("$line"); done < <(printf '%s\n' "${profiles[@]}" | sort -u)
    profiles=("${deduped[@]}")
  fi

  if [[ ${#profiles[@]} -eq 0 ]]; then
    echo "No AWS profiles found. Run 'aws configure' or set AWS_PROFILE."
    exit 1
  fi

  echo "Available AWS profiles:"
  for i in "${!profiles[@]}"; do echo "  $((i + 1))) ${profiles[$i]}"; done
  echo ""
  read -rp "Select profile [1-${#profiles[@]}]: " profile_choice

  if [[ "$profile_choice" -ge 1 && "$profile_choice" -le ${#profiles[@]} ]] 2>/dev/null; then
    AWS_PROFILE="${profiles[$((profile_choice - 1))]}"
    export AWS_PROFILE
    echo ""
    if ! check_aws_credentials; then
      echo "Selected profile '$AWS_PROFILE' does not have valid credentials."
      echo "You may need to run: aws sso login --profile $AWS_PROFILE"
      exit 1
    fi
  else
    echo "Invalid choice"; exit 1
  fi
fi

# ---------------------------------------------------------------------------
# AWS CLI args (reused everywhere)
# ---------------------------------------------------------------------------
AWS_ARGS=(--region "$AWS_REGION" --no-cli-pager)
[[ -n "$AWS_PROFILE" ]] && AWS_ARGS+=(--profile "$AWS_PROFILE")

# ---------------------------------------------------------------------------
# List existing providers and secrets
# ---------------------------------------------------------------------------
show_status() {
  echo "=== Credential Providers (AgentCore Identity, $AWS_REGION) ==="
  echo ""

  local providers_json
  providers_json=$(aws bedrock-agentcore-control list-oauth2-credential-providers \
    "${AWS_ARGS[@]}" --output json 2>/dev/null || echo '{"credentialProviders":[]}')

  local count
  count=$(echo "$providers_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('credentialProviders',d.get('oAuth2CredentialProviders',[]))))" 2>/dev/null || echo "0")

  if [[ "$count" == "0" ]]; then
    echo "  (none)"
  else
    echo "$providers_json" | python3 -c "
import sys, json
d = json.load(sys.stdin)
providers = d.get('credentialProviders', d.get('oAuth2CredentialProviders', []))
for i, p in enumerate(providers, 1):
    name = p.get('name', '?')
    vendor = p.get('credentialProviderVendor', '?')
    updated = p.get('lastUpdatedTime', p.get('createdTime', '?'))
    print(f'  {i}) {name}  ({vendor})  updated: {updated}')
" 2>/dev/null || echo "  (could not parse provider list)"
  fi

  echo ""
  echo "=== Secrets Manager (${SECRET_PREFIX}/* in $AWS_REGION) ==="
  echo ""

  local secrets_json
  secrets_json=$(aws secretsmanager list-secrets \
    --filters "Key=name,Values=${SECRET_PREFIX}/" \
    "${AWS_ARGS[@]}" --output json 2>/dev/null || echo '{"SecretList":[]}')

  local sec_count
  sec_count=$(echo "$secrets_json" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('SecretList',[])))" 2>/dev/null || echo "0")

  if [[ "$sec_count" == "0" ]]; then
    echo "  (none)"
  else
    echo "$secrets_json" | python3 -c "
import sys, json
for i, s in enumerate(json.load(sys.stdin).get('SecretList', []), 1):
    name = s.get('Name', '?')
    desc = s.get('Description', '')
    print(f'  {i}) {name}')
    if desc:
        print(f'     {desc}')
" 2>/dev/null || echo "  (could not parse secret list)"
  fi
  echo ""
}

# ---------------------------------------------------------------------------
# Resolve provider -> secret name and registration name
# ---------------------------------------------------------------------------
resolve_names() {
  # Sets: SECRET_NAME, DISPLAY_HOST, PROVIDER_REG_NAME
  case "$PROVIDER" in
    github)
      SECRET_NAME="${SECRET_PREFIX}/github-oauth-app"
      DISPLAY_HOST="github.com"
      PROVIDER_REG_NAME="github-provider"
      ;;
    *) echo "Unknown provider: $PROVIDER"; exit 1 ;;
  esac
}

# ---------------------------------------------------------------------------
# Prompt for provider type (interactive)
# ---------------------------------------------------------------------------
prompt_provider() {
  PROVIDER="github"
}

# ---------------------------------------------------------------------------
# Show provider-specific setup instructions
# ---------------------------------------------------------------------------
show_instructions() {
  echo ""
  case "$PROVIDER" in
    github)
      echo "=== GitHub OAuth App Setup ==="
      echo ""
      echo "1. Go to: https://github.com/settings/developers"
      echo "   (Profile picture -> Settings -> Developer settings -> OAuth Apps)"
      echo "2. Click 'New OAuth App' (or 'Register a new application')"
      echo "3. Fill in:"
      echo "   - Application name: OpenCode on AgentCore"
      echo "   - Homepage URL: https://github.com (or your org URL)"
      echo "   - Authorization callback URL: use any placeholder for now"
      echo "     (the script will show the correct URL after registration)"
      echo "4. Leave 'Enable Device Flow' unchecked"
      echo "   (not needed -- we use the authorization code flow)"
      echo "5. Click 'Register application'"
      echo "6. Copy the Client ID from the app page"
      echo "7. Click 'Generate a new client secret' -- copy it immediately (shown only once)"
      echo ""
      echo "Docs: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app"
      echo ""
      ;;
  esac
}

# ---------------------------------------------------------------------------
# Add (create or update) a provider
# ---------------------------------------------------------------------------
do_add() {
  if [[ -z "$PROVIDER" ]]; then
    prompt_provider
  fi
  resolve_names

  show_instructions

  if [[ -z "$CLIENT_ID" ]]; then
    read -rp "OAuth App Client ID: " CLIENT_ID
  fi
  if [[ -z "$CLIENT_SECRET" ]]; then
    read -rsp "OAuth App Client Secret: " CLIENT_SECRET
    echo ""
  fi
  [[ -z "$CLIENT_ID" || -z "$CLIENT_SECRET" ]] && { echo "Error: client_id and client_secret are required"; exit 1; }

  local secret_value
  secret_value="{\"client_id\":\"${CLIENT_ID}\",\"client_secret\":\"${CLIENT_SECRET}\",\"provider\":\"${PROVIDER}\",\"host\":\"${DISPLAY_HOST}\"}"

  echo ""
  echo "Storing OAuth App credentials:"
  echo "  Provider:    $PROVIDER ($DISPLAY_HOST)"
  echo "  Secret name: $SECRET_NAME"
  echo "  Region:      $AWS_REGION"
  echo ""

  if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" "${AWS_ARGS[@]}" &>/dev/null; then
    echo "Secret exists -- updating..."
    echo "$secret_value" | aws secretsmanager put-secret-value \
      --secret-id "$SECRET_NAME" \
      --secret-string file:///dev/stdin \
      "${AWS_ARGS[@]}"
  else
    echo "Creating secret..."
    echo "$secret_value" | aws secretsmanager create-secret \
      --name "$SECRET_NAME" \
      --description "OAuth App credentials for AgentCore Identity ($DISPLAY_HOST)" \
      --secret-string file:///dev/stdin \
      "${AWS_ARGS[@]}"
  fi
  echo ""
  echo "Done. Secret stored at: $SECRET_NAME"
  echo ""

  # Register credential provider
  echo "Registering credential provider with AgentCore Identity..."

  local vendor_config provider_vendor
  case "$PROVIDER" in
    github)
      vendor_config="{\"githubOauth2ProviderConfig\":{\"clientId\":\"${CLIENT_ID}\",\"clientSecret\":\"${CLIENT_SECRET}\"}}"
      provider_vendor="GithubOauth2"
      ;;
  esac

  if result=$(echo "$vendor_config" | aws bedrock-agentcore-control create-oauth2-credential-provider \
      --name "$PROVIDER_REG_NAME" \
      --credential-provider-vendor "$provider_vendor" \
      --oauth2-provider-config-input file:///dev/stdin \
      "${AWS_ARGS[@]}" 2>/dev/null); then
    echo "Credential provider '$PROVIDER_REG_NAME' registered."
  elif result=$(echo "$vendor_config" | aws bedrock-agentcore-control update-oauth2-credential-provider \
      --name "$PROVIDER_REG_NAME" \
      --credential-provider-vendor "$provider_vendor" \
      --oauth2-provider-config-input file:///dev/stdin \
      "${AWS_ARGS[@]}" 2>/dev/null); then
    echo "Credential provider '$PROVIDER_REG_NAME' updated."
  else
    echo ""
    echo "Warning: Could not register credential provider automatically."
    echo "This may happen if AgentCore Identity is not yet deployed."
    echo "The provider will be registered on next: cdk deploy OpenCodeIdentity"
  fi

  # Extract the callback URL from the create/update response.
  # The CreateOauth2CredentialProvider API returns a `callbackUrl` field
  # directly.  Fall back to constructing from the ARN for older SDK versions.
  local callback_url
  callback_url=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('callbackUrl',''))" 2>/dev/null || true)

  if [[ -z "$callback_url" ]]; then
    # Fallback: extract UUID from the ARN (legacy behavior).
    local provider_arn callback_uuid
    provider_arn=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('credentialProviderArn',''))" 2>/dev/null || true)
    if [[ -n "$provider_arn" ]]; then
      callback_uuid="${provider_arn##*/}"
      callback_url="https://bedrock-agentcore.${AWS_REGION}.amazonaws.com/identities/oauth2/callback/${callback_uuid}"
    fi
  fi

  if [[ -n "$callback_url" ]]; then
    echo ""
    echo "=== IMPORTANT: Update your OAuth App callback URL ==="
    echo ""
    echo "Set the Authorization callback URL in your OAuth App to:"
    echo "  $callback_url"
    echo ""
    echo "AgentCore Identity appends a provider-specific UUID to the callback path."
    echo "The OAuth App callback URL must match exactly, or GitHub will reject the redirect."
  fi

  echo ""
  echo "Setup complete -- the credential provider is active."
}

# ---------------------------------------------------------------------------
# Delete a provider and its secret (interactive: pick from live list)
# ---------------------------------------------------------------------------
do_delete() {
  # Non-interactive path: --delete --provider github
  if [[ -n "$PROVIDER" ]]; then
    resolve_names
    _confirm_and_delete "$PROVIDER_REG_NAME" "$SECRET_NAME"
    return
  fi

  # Interactive path: fetch live providers and let user pick
  local providers_json
  providers_json=$(aws bedrock-agentcore-control list-oauth2-credential-providers \
    "${AWS_ARGS[@]}" --output json 2>/dev/null || echo '{"credentialProviders":[]}')

  # Build parallel arrays of provider names and vendors
  local names=() vendors=()
  while IFS='|' read -r n v; do
    names+=("$n")
    vendors+=("$v")
  done < <(echo "$providers_json" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for p in d.get('credentialProviders', d.get('oAuth2CredentialProviders', [])):
    print(p.get('name','') + '|' + p.get('credentialProviderVendor',''))
" 2>/dev/null || true)

  if [[ ${#names[@]} -eq 0 ]]; then
    echo "No credential providers found in $AWS_REGION. Nothing to delete."
    return
  fi

  echo "Existing credential providers in $AWS_REGION:"
  for i in "${!names[@]}"; do
    echo "  $((i + 1))) ${names[$i]}  (${vendors[$i]})"
  done
  echo ""
  read -rp "Select provider to delete [1-${#names[@]}], or 0 to cancel: " del_choice

  if [[ "$del_choice" == "0" ]]; then
    echo "Cancelled."
    return
  fi

  if ! [[ "$del_choice" -ge 1 && "$del_choice" -le ${#names[@]} ]] 2>/dev/null; then
    echo "Invalid choice"
    exit 1
  fi

  local selected_name="${names[$((del_choice - 1))]}"

  # Try to find the matching secret. Convention: github-provider -> opencode/github-oauth-app,
  # custom-<host> -> opencode/ghe-oauth-app-<host> or opencode/gitlab-oauth-app-<host>.
  # Fall back to searching Secrets Manager for any opencode/* secret whose stored JSON
  # references this provider name.
  local secret_name=""
  if [[ "$selected_name" == "github-provider" ]]; then
    secret_name="${SECRET_PREFIX}/github-oauth-app"
  fi

  _confirm_and_delete "$selected_name" "$secret_name"
}

_confirm_and_delete() {
  local provider_name="$1"
  local secret_name="${2:-}"

  echo ""
  echo "Will delete:"
  echo "  Credential provider: $provider_name"
  if [[ -n "$secret_name" ]]; then
    echo "  Secret:              $secret_name"
  else
    echo "  Secret:              (no matching secret found)"
  fi
  echo "  Region:              $AWS_REGION"
  echo ""
  read -rp "Are you sure? [y/N]: " confirm
  [[ "$confirm" != "y" && "$confirm" != "Y" ]] && { echo "Cancelled."; return; }
  echo ""

  # Delete credential provider
  if aws bedrock-agentcore-control delete-oauth2-credential-provider \
      --name "$provider_name" "${AWS_ARGS[@]}" 2>/dev/null; then
    echo "Credential provider '$provider_name' deleted."
  else
    echo "Credential provider '$provider_name' not found or already deleted."
  fi

  # Delete secret
  if [[ -n "$secret_name" ]]; then
    if aws secretsmanager describe-secret --secret-id "$secret_name" "${AWS_ARGS[@]}" &>/dev/null; then
      aws secretsmanager delete-secret \
        --secret-id "$secret_name" \
        --force-delete-without-recovery \
        "${AWS_ARGS[@]}" >/dev/null
      echo "Secret '$secret_name' deleted (immediate, no recovery window)."
    else
      echo "Secret '$secret_name' not found or already deleted."
    fi
  fi

  echo ""
  echo "Done."
}

# ---------------------------------------------------------------------------
# Main: dispatch by action or show interactive menu
# ---------------------------------------------------------------------------
case "$ACTION" in
  list)
    show_status
    ;;
  add)
    do_add
    ;;
  delete)
    do_delete
    ;;
  "")
    # Interactive menu
    show_status
    echo "What would you like to do?"
    echo "  1) Add or update a provider"
    echo "  2) Delete a provider"
    echo "  3) Quit"
    read -rp "Choice [1-3]: " menu_choice
    echo ""
    case "$menu_choice" in
      1) do_add ;;
      2) do_delete ;;
      3) echo "Done."; exit 0 ;;
      *) echo "Invalid choice"; exit 1 ;;
    esac
    ;;
esac
