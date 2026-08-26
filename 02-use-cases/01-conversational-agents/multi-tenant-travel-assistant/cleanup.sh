#!/usr/bin/env bash
#
# Tear the sample down: agent first, then infrastructure.
#
#     ./cleanup.sh              # asks before deleting anything
#     ./cleanup.sh --yes        # no prompt (for CI)
#
# **Order is the opposite of deploy, and getting it wrong leaves a resource you cannot delete.** The
# Runtime's JWT authorizer points at the Cognito pool that `infra/` owns. Deleting a Runtime makes
# CloudFormation *validate* that authorizer, which fetches the pool's OpenID discovery document — so if
# the pool is already gone the delete fails with `Failed to fetch discovery document from:
# https://cognito-idp.<region>.amazonaws.com/<pool-id>/.well-known/openid-configuration`, and the stack
# lands in `DELETE_FAILED` with no way forward through CloudFormation. Recovering means calling
# `DeleteAgentRuntime` directly (the service itself does not do this validation) and then re-deleting
# the stack. Cheaper to just tear the agent down first, which is why a failure below is fatal here
# rather than a warning: continuing past it is what creates the stuck resource.
#
# The agent's gateway targets also reference the tool Lambdas, so an out-of-order teardown additionally
# leaves a gateway that 500s on every call.
#
# **Leaving the stacks up between sessions is fine and usually the right call.** Everything is
# `RemovalPolicy.DESTROY` and pay-per-request, so idle cost is near zero — *unless* the private VPC is
# deployed, which bills ~$161/month for its interface endpoints whether or not anyone uses it. That is
# the one arrangement worth tearing down when you are done with it.

set -euo pipefail

export TRAVEL_REGION="${TRAVEL_REGION:-us-east-1}"
export AWS_REGION="$TRAVEL_REGION"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

ASSUME_YES=false
[[ "${1:-}" == "--yes" ]] && ASSUME_YES=true

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
note() { printf '    %s\n' "$1"; }

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)" || {
  echo "no usable AWS credentials" >&2; exit 1; }

step "About to destroy the deployment"
note "account $ACCOUNT, region $TRAVEL_REGION"
note ""
note "This deletes the agent runtime, gateway, memory (including conversation history),"
note "all DynamoDB tables and their seeded fixtures, the Cognito pool and its users,"
note "the knowledge base, and the CloudTrail audit bucket."

if ! $ASSUME_YES; then
  read -r -p "    Type the account id to confirm: " CONFIRM
  [[ "$CONFIRM" == "$ACCOUNT" ]] || { echo "    mismatch — nothing was deleted"; exit 1; }
fi

# --- 1. agent -----------------------------------------------------------------------------------

# **The AgentCore CLI has no `destroy`.** `agentcore --help` on the pinned 0.24.x lists `deploy` but
# nothing that removes what it deployed — an earlier version of this script called `agentcore destroy`,
# which exits with `error: unknown command 'destroy'` and, because that exit was swallowed as a
# warning, the whole agent side survived a teardown that printed "Done". A `deploy` is a CDK app, so a
# `destroy` is a CloudFormation stack delete.
#
# The stack name is built by the CLI's own CDK entrypoint (`agentcore/cdk/bin/cdk.ts`) as
# `AgentCore-<project>-<target>` with underscores replaced by hyphens. Deriving it from the same two
# files the CLI reads keeps this correct if either is renamed, instead of hardcoding one name here.

step "Destroying the agent (CloudFormation)"
AGENT_STACKS="$(cd agent/MultiTenantTravel/agentcore && python3 -c '
import json
name = json.load(open("agentcore.json"))["name"].replace("_", "-")
for target in json.load(open("aws-targets.json")):
    print("AgentCore-" + name + "-" + target["name"].replace("_", "-"))
')"

for stack in $AGENT_STACKS; do
  if ! aws cloudformation describe-stacks --stack-name "$stack" >/dev/null 2>&1; then
    note "$stack does not exist — nothing to delete"
    continue
  fi
  note "deleting $stack"
  aws cloudformation delete-stack --stack-name "$stack"
  if ! aws cloudformation wait stack-delete-complete --stack-name "$stack" 2>/dev/null; then
    echo >&2
    echo "    $stack did not delete cleanly. Stopping before infrastructure teardown, because" >&2
    echo "    destroying infra/ now would delete the Cognito pool and make the Runtime" >&2
    echo "    permanently undeletable through CloudFormation. To recover:" >&2
    echo >&2
    echo "      aws cloudformation describe-stack-events --stack-name $stack \\" >&2
    echo "        --query 'StackEvents[?ResourceStatus==\`DELETE_FAILED\`].[LogicalResourceId,ResourceStatusReason]'" >&2
    echo >&2
    echo "    If a Runtime is the blocker, delete it directly and re-run this script:" >&2
    echo >&2
    echo "      aws bedrock-agentcore-control list-agent-runtimes \\" >&2
    echo "        --query 'agentRuntimes[?contains(agentRuntimeName, \`MultiTenantTravel\`)].agentRuntimeId'" >&2
    echo "      aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-id <id>" >&2
    exit 1
  fi
  note "deleted $stack"
done

# **The CLI's own record of what it deployed, which `destroy` does not always remove.** It names
# resources by id, so a stale copy makes the next deploy try to update things that no longer exist.
# Left behind, it is a deploy failure days later with nothing obviously connecting the two.
rm -f agent/MultiTenantTravel/agentcore/.cli/deployed-state.json

# --- 2. the one bucket that does not empty itself -----------------------------------------------
#
# Every other bucket sets `autoDeleteObjects`. The site bucket deliberately does not: that property
# provisions a custom-resource Lambda, which is noise in a repo people read. So it is emptied here —
# and a non-empty bucket is the single most common reason a CDK destroy stalls.

step "Emptying the frontend bucket"
SITE_BUCKET="multi-tenant-travel-frontend-${ACCOUNT}"
if aws s3api head-bucket --bucket "$SITE_BUCKET" >/dev/null 2>&1; then
  aws s3 rm "s3://${SITE_BUCKET}" --recursive --only-show-errors
  note "emptied $SITE_BUCKET"
else
  note "$SITE_BUCKET does not exist — nothing to empty"
fi

# --- 3. infrastructure --------------------------------------------------------------------------

# **One retry, because the access-logs bucket loses a race against its own teardown.** Every bucket
# here sets `autoDeleteObjects` except the site bucket emptied above, so a non-empty bucket should not
# be possible — and yet:
#
#     Storage/AccessLogs  DELETE_FAILED  "The bucket you tried to delete is not empty"
#
# S3 server access logs are delivered asynchronously, and the access-logs bucket receives them from the
# other buckets in this stack. So the auto-delete Lambda empties it, S3 then delivers the log lines
# describing *that very emptying*, and CloudFormation deletes a bucket that refilled a second ago.
# Confirmed from the object timestamps on a real teardown: the two objects left behind were
# `policy-docs/…` and `site-bucket/…`, delivered 90 and 30 seconds before the failed delete.
#
# **The retry is enough, and that is not luck.** The buckets that generate those logs are gone by the
# end of the first pass, so nothing produces new ones — a second destroy finds the bucket empty and
# stays that way. Intermittent by nature: an idle deployment tears down first time, which is exactly
# what makes it the kind of failure a reader hits and the author does not.

step "Destroying infrastructure (cdk)"
if ! (cd infra && npm run destroy); then
  note "first pass did not finish — emptying anything that refilled during teardown, then retrying"
  for bucket in $(aws s3api list-buckets \
    --query "Buckets[?starts_with(Name, 'multi-tenant-travel-')].Name" --output text 2>/dev/null); do
    aws s3 rm "s3://${bucket}" --recursive --only-show-errors 2>/dev/null && note "emptied $bucket"
  done
  (cd infra && npm run destroy)
fi

# --- 4. what CloudFormation does not own --------------------------------------------------------
#
# Some parameters under `/multi-tenant-travel/` are written by scripts rather than by CDK —
# `publish_agent_refs.py` writes the runtime ARN and the memory id, `seed.sh` writes the demo
# password as a `SecureString`, and the budget walkthrough in the README has you write
# `budget/trajectory` by hand. Nothing deletes any of them.
#
# Stale values are worse than absent ones: a later deploy would find a runtime ARN pointing at a
# runtime that no longer exists, and the BFF would fail with a 404 from AgentCore rather than the
# clear "not deployed yet" refusal `agent_refs.py` raises when the parameter is gone. And a leftover
# password parameter is a credential outliving the account it opened.
#
# **Sweep the prefix rather than name the parameters.** This step runs after `cdk destroy`, so
# anything still under `/multi-tenant-travel/` at this point is by definition not owned by
# CloudFormation — which is the exact set to remove, and stays correct when someone adds the next
# hand-written parameter without remembering to update a list here. The earlier version named two,
# and had already fallen two behind.

step "Removing parameters CloudFormation does not own"
LEFTOVER=$(aws ssm get-parameters-by-path --path /multi-tenant-travel/ --recursive \
  --query 'Parameters[].Name' --output text 2>/dev/null | tr '\t' '\n' | grep . || true)
if [ -z "$LEFTOVER" ]; then
  note "nothing left under /multi-tenant-travel/"
else
  # `delete-parameters` (plural) takes at most 10 names per call, so batch. It reports unknown names
  # in `InvalidParameters` instead of failing, which makes a re-run of `cleanup.sh` a no-op.
  echo "$LEFTOVER" | xargs -n 10 aws ssm delete-parameters --names >/dev/null
  echo "$LEFTOVER" | while read -r param; do note "deleted $param"; done
fi

# --- 5. log groups that outlive their stack -----------------------------------------------------
#
# **The prompt above promises this teardown deletes conversation history, and log groups are the part
# that quietly breaks that promise.** A verified teardown left three behind: the Runtime's
# `/aws/bedrock-agentcore/runtimes/...` group, which the service creates rather than the stack; the
# group for CDK's S3 auto-delete custom resource; and `/aws/lambda/<stack>-mock-tmc`. Runtime logs hold
# traveller prompts and the mock TMC is the one component that legitimately returns passport and card
# data, so leaving these is not a tidiness question.
#
# Swept by prefix rather than by name, for the same reason as the parameters above: this runs after
# both stacks are gone, so anything still matching is by definition unowned, and the sweep stays
# correct when the next function is added.

step "Removing log groups CloudFormation does not own"
AGENT_PROJECT="$(cd agent/MultiTenantTravel/agentcore && python3 -c \
  'import json; print(json.load(open("agentcore.json"))["name"])')"
STALE_LOGS=""
for prefix in "/aws/lambda/multi-tenant-travel" "/aws/apigateway/multi-tenant-travel" \
              "/aws/vendedlogs/multi-tenant-travel" "/aws/bedrock-agentcore/runtimes/${AGENT_PROJECT}"; do
  FOUND=$(aws logs describe-log-groups --log-group-name-prefix "$prefix" \
    --query 'logGroups[].logGroupName' --output text 2>/dev/null | tr '\t' '\n' | grep . || true)
  [ -n "$FOUND" ] && STALE_LOGS="${STALE_LOGS}${FOUND}"$'\n'
done
STALE_LOGS=$(printf '%s' "$STALE_LOGS" | grep . || true)
if [ -z "$STALE_LOGS" ]; then
  note "no stale log groups"
else
  echo "$STALE_LOGS" | while read -r lg; do
    aws logs delete-log-group --log-group-name "$lg" 2>/dev/null && note "deleted $lg" \
      || note "could not delete $lg"
  done
fi

step "Done"
note "Cost allocation tag *activations* survive teardown — they are account-level billing settings,"
note "not stack resources, and leaving them active costs nothing."
note ""
note "A customer-managed KMS key deleted by either stack enters a mandatory 7-30 day pending-deletion"
note "window and bills for that period. AWS does not allow it to be purged sooner, so this is expected"
note "rather than a leftover: aws kms describe-key --key-id <id> --query KeyMetadata.DeletionDate"
