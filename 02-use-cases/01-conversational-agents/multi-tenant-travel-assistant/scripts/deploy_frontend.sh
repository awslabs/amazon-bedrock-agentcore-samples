#!/usr/bin/env bash
#
# Build the SPA against the deployed API and publish it.
#
#     scripts/deploy_frontend.sh
#
# Reads every value from SSM rather than taking arguments, so the bundle cannot be built against one
# environment and uploaded to another — the failure that produces is a site that loads and then fails
# every request with an opaque CORS error.
#
# **Two cache policies, and the split is the point.** Fingerprinted assets are immutable, so they are
# uploaded first with a one-year max-age; `index.html` is uploaded second with `no-cache`, because it
# is the file that names which fingerprints to fetch. Uploading it first would briefly point browsers
# at assets that are not there yet.
set -euo pipefail

REGION="${TRAVEL_REGION:-us-east-1}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

param() {
  aws ssm get-parameter --name "$1" --region "$REGION" --query Parameter.Value --output text
}

BUCKET="$(param /multi-tenant-travel/frontend/bucket)"
DISTRIBUTION="$(param /multi-tenant-travel/frontend/distribution-id)"
ORIGIN="$(param /multi-tenant-travel/frontend/origin)"
# **A path, not a URL.** The distribution serves the API from this same origin under its stage
# prefix, which is what lets the `SameSite=Strict` session cookie be sent at all — a cookie set on
# `execute-api.amazonaws.com` is a different site from the SPA and would never come back.
# Derived from the deployed URL rather than hardcoded, so the stage name has one source.
API_STAGE="$(param /multi-tenant-travel/conversation-api/url | sed -E 's#^https://[^/]+/##; s#/*$##')"
API_BASE="/${API_STAGE}"
API_URL="$(param /multi-tenant-travel/conversation-api/url | sed 's:/*$::')"

echo "API      $API_URL"
echo "SPA calls $API_BASE (same origin, via the distribution)"
echo "Bucket   $BUCKET"
echo "Site     $ORIGIN"

cd "$HERE/frontend"
# Regenerated first, so a card type added in Python cannot ship as an unrendered tile — the renderer's
# exhaustive switch turns it into a build failure instead.
python3 "$HERE/scripts/generate_card_types.py"

# **`npm ci` first, because a fresh clone has no `node_modules`.** Without it the first deploy of a
# new checkout fails here — at the very last step, after every stack has already succeeded, which is
# the most expensive place to discover a missing install.
#
# `ci` rather than `install`: it installs exactly `package-lock.json` and fails if the lock and the
# manifest disagree, which is what you want for the bundle a deployment serves. `install` would
# quietly resolve something newer and update the lock as a side effect of deploying.
npm ci --silent

VITE_API_BASE="$API_BASE" npm run build

aws s3 sync dist/ "s3://$BUCKET/" \
  --region "$REGION" \
  --delete \
  --exclude index.html \
  --cache-control "public, max-age=31536000, immutable"

aws s3 cp dist/index.html "s3://$BUCKET/index.html" \
  --region "$REGION" \
  --cache-control "no-cache, must-revalidate" \
  --content-type "text/html"

# Only `index.html`: the assets are fingerprinted, so invalidating them costs money and achieves
# nothing. A wildcard invalidation here would be the reflex and the wrong call.
aws cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION" \
  --paths /index.html \
  --query 'Invalidation.Id' --output text

echo "Published to $ORIGIN"
