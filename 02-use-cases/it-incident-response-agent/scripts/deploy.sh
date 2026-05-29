#!/usr/bin/env bash
# One-command deploy. Run from the project root.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found. Copy .env.example to .env and fill it in." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --quiet -r requirements.txt

set -a
# shellcheck disable=SC1091
source .env
set +a

echo "==> CDK bootstrap (idempotent)"
cdk bootstrap "aws://${CDK_DEFAULT_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text)}/${AWS_REGION}"

echo "==> CDK deploy ${STACK_NAME:-ItIncidentResponseAgent}"
cdk deploy --require-approval never
