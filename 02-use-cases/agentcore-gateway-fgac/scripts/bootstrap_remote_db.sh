#!/usr/bin/env bash
# Run the database bootstrap (create tables + seed sample products) against
# the deployed RDS instance. Launches a one-off Fargate task using the same
# task definition + container image as the app, but overrides the command to
# `python -m ecommerce.bootstrap`.
#
# Inputs are read from the platform stack's terraform outputs. Requires:
#   - The platform stack has been applied.
#   - The container image referenced by the task definition exists in ECR
#     (i.e. you've completed the `podman push` step at least once).
#
# Usage:
#   scripts/bootstrap_remote_db.sh
#
# Exits non-zero if the bootstrap task does not complete with exit code 0.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
platform_dir="$repo_root/infra/envs/dev/platform"

if [[ ! -f "$platform_dir/terraform.tfstate" ]]; then
  echo "ERROR: platform stack has no state file at $platform_dir." >&2
  echo "       Run 'cd $platform_dir && terraform apply' first." >&2
  exit 1
fi

cd "$platform_dir"

cluster=$(terraform output -raw ecs_cluster_name)
task_def=$(terraform output -raw task_definition_arn)
log_group=$(terraform output -raw task_log_group_name)
sg_id=$(terraform output -raw app_security_group_id)
subnet_ids=$(terraform output -json private_subnet_ids | jq -r 'join(",")')

echo "→ Cluster:    $cluster"
echo "→ Task def:   $task_def"
echo "→ Subnets:    $subnet_ids"
echo "→ Log group:  $log_group"
echo

network_config="awsvpcConfiguration={subnets=[$subnet_ids],securityGroups=[$sg_id],assignPublicIp=DISABLED}"

# Override the container command. The container name in the task def is "app".
# Use the venv's absolute python — the distroless runtime image has no shell
# and no `python` on PATH outside /app/.venv/bin.
overrides=$(jq -n '{
  containerOverrides: [
    { name: "app", command: ["/app/.venv/bin/python", "-m", "ecommerce.bootstrap"] }
  ]
}')

echo "→ Launching one-off Fargate task..."
task_arn=$(aws ecs run-task \
  --cluster "$cluster" \
  --task-definition "$task_def" \
  --launch-type FARGATE \
  --network-configuration "$network_config" \
  --overrides "$overrides" \
  --query 'tasks[0].taskArn' \
  --output text)

if [[ -z "$task_arn" || "$task_arn" == "None" ]]; then
  echo "ERROR: run-task returned no task ARN." >&2
  exit 1
fi

task_id=${task_arn##*/}
echo "→ Task ARN:   $task_arn"
echo "→ Waiting for task to stop (up to 10 min)..."
aws ecs wait tasks-stopped --cluster "$cluster" --tasks "$task_arn"

# Stream logs from the bootstrap task.
log_stream="app/app/$task_id"
echo
echo "── Logs (CloudWatch: $log_group / $log_stream) ──────────────"
aws logs tail "$log_group" \
  --log-stream-names "$log_stream" \
  --format short 2>/dev/null || \
  echo "(log stream not yet flushed — check CloudWatch directly: $log_group)"

# Inspect exit code.
exit_code=$(aws ecs describe-tasks \
  --cluster "$cluster" --tasks "$task_arn" \
  --query 'tasks[0].containers[0].exitCode' \
  --output text)
stop_reason=$(aws ecs describe-tasks \
  --cluster "$cluster" --tasks "$task_arn" \
  --query 'tasks[0].stoppedReason' \
  --output text)

echo
if [[ "$exit_code" == "0" ]]; then
  echo "✓ Bootstrap completed successfully."
else
  echo "✗ Bootstrap task exited with code $exit_code."
  echo "  Stop reason: $stop_reason"
  exit 1
fi
