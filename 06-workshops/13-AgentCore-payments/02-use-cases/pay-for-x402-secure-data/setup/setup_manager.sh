#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SAMPLE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$SAMPLE_ROOT/.env}"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

command -v python >/dev/null 2>&1 || die "python not found"
command -v aws >/dev/null 2>&1 || die "aws CLI not found"

if [[ -f "$ENV_FILE" ]]; then
  set -o allexport
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +o allexport
fi

python "$SCRIPT_DIR/setup_manager.py"
