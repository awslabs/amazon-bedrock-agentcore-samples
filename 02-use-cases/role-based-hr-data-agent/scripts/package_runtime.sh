#!/bin/bash
# =============================================================================
# Package the AgentCore Runtime into dist/runtime.zip
#
# Bundles:
#   main.py            — BedrockAgentCoreApp entry point
#   agent_config/      — HRDataAgent, task orchestration, SSM utils
#   requirements.txt   — AgentCore Runtime installs deps on first launch
#
# Output: dist/runtime.zip
#
# Usage:
#   bash scripts/package_runtime.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist"

TMP_DIR=$(mktemp -d)
trap "rm -rf ${TMP_DIR}" EXIT

mkdir -p "${DIST_DIR}"
rm -f "${DIST_DIR}/runtime.zip"

echo "Packaging AgentCore Runtime..."
echo "  Source: ${ROOT_DIR}"
echo "  Output: ${DIST_DIR}/runtime.zip"

# Copy runtime entry point and agent module
cp "${ROOT_DIR}/main.py" "${TMP_DIR}/"
cp -r "${ROOT_DIR}/agent_config" "${TMP_DIR}/"

# Install Python dependencies for Linux ARM64 (AgentCore Runtime target platform).
# Use --platform flags to download manylinux aarch64 wheels from PyPI instead of
# local macOS binaries, and --no-cache-dir to bypass the macOS wheel cache.
if [[ -f "${ROOT_DIR}/requirements.txt" ]]; then
  echo "  Installing dependencies for Linux ARM64..."
  pip install \
    -r "${ROOT_DIR}/requirements.txt" \
    -t "${TMP_DIR}/" \
    --quiet \
    --upgrade \
    --platform manylinux_2_17_aarch64 \
    --platform manylinux2014_aarch64 \
    --only-binary=:all: \
    --python-version 3.11 \
    --implementation cp \
    --no-cache-dir
else
  echo "  WARNING: requirements.txt not found, skipping dependency install"
fi

# Create ZIP
(cd "${TMP_DIR}" && zip -qr "${DIST_DIR}/runtime.zip" .)

SIZE=$(du -sh "${DIST_DIR}/runtime.zip" | cut -f1)
FILE_COUNT=$(unzip -l "${DIST_DIR}/runtime.zip" | tail -1 | awk '{print $2}')
echo "  Built: dist/runtime.zip (${SIZE}, ${FILE_COUNT} files)"
echo ""
echo "Next: upload to S3 before running agentcore_agent_runtime.py create"
echo "  BUCKET=\$(aws ssm get-parameter --name /app/hrdlp/deploy-bucket --query Parameter.Value --output text)"
echo "  aws s3 cp dist/runtime.zip s3://\${BUCKET}/hr-data-agent/runtime.zip"
