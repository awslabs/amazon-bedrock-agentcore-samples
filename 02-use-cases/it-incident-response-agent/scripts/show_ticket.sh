#!/usr/bin/env bash
# Show the resolved state of a Jira issue (status + last comment).
#
# Reads JIRA_SITE_URL from .env. Authentication uses an Atlassian API
# token: set JIRA_API_USER (your Atlassian account email) and
# JIRA_API_TOKEN (a token from id.atlassian.com/manage-profile/security/api-tokens)
# in your shell — these are NOT consumed by the agent itself, only by
# this convenience script.
#
# Usage: scripts/show_ticket.sh INC-1042
set -euo pipefail

cd "$(dirname "$0")/.."

set -a
# shellcheck disable=SC1091
source .env
set +a

ISSUE_KEY="${1:?issue_key required, e.g. INC-1042}"

: "${JIRA_SITE_URL:?JIRA_SITE_URL must be set in .env}"
: "${JIRA_API_USER:?JIRA_API_USER must be exported (Atlassian account email)}"
: "${JIRA_API_TOKEN:?JIRA_API_TOKEN must be exported (API token)}"

curl -sS \
  -u "${JIRA_API_USER}:${JIRA_API_TOKEN}" \
  -H "Accept: application/json" \
  "${JIRA_SITE_URL%/}/rest/api/3/issue/${ISSUE_KEY}?fields=summary,status,comment" \
  | jq '{
      key,
      summary: .fields.summary,
      status: .fields.status.name,
      last_comment: (.fields.comment.comments | last | {author: .author.displayName, created, body})
    }'
