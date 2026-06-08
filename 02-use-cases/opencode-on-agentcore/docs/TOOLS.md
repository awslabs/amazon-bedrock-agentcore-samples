<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Tools

Reference for the six MCP tools the sample exposes through the AgentCore Gateway. All tools are routed to a single MCP Server target named `opencode`, so the effective Cedar action identifiers are `opencode___{tool}` with three underscores.

## Tool reference

| Tool | Mode | Description | Required parameters |
|------|------|-------------|---------------------|
| `code` | Sync | Execute coding task, stream progress via MCP, return PR URL. Uses `ctx.elicit()` for OAuth consent if needed. | `task_description`, `repo_url`, `base_branch` |
| `run_coding_task` | Async | Submit task, get `job_id` immediately. Runs in background via AgentCore async tasks. No mid-task clarification. | `task_description`, `repo_url`, `base_branch` |
| `connect_git_host` | Sync | Connect a git host (GitHub) by completing OAuth via elicitation. Run before submitting coding tasks to a new host. | `git_host` |
| `get_task_status` | Sync | Poll job status by `job_id` from DynamoDB. | `job_id` |
| `list_tasks` | Sync | List jobs for the authenticated user. Supports status filtering, capped at 100 results. | - |
| `cancel_task` | Sync | Cancel a running task. Attempts in-process cancellation first; falls back to cross-session `StopRuntimeSession` API. Updates DynamoDB to `CANCELLED`. | `job_id` |

Cold start is roughly 1.2 s per microVM.

## Examples

### `code` - synchronous coding tool

```json
// Input
{
  "task_description": "Add dark mode toggle",
  "repo_url": "https://github.com/org/repo",
  "base_branch": "main"
}

// Output
{
  "status": "complete",
  "pr_url": "https://github.com/org/repo/pull/42",
  "stop_reason": "end_turn",
  "files_edited": ["src/components/DarkMode.tsx", "src/styles/theme.css"],
  "duration_seconds": 120
}
```

### `run_coding_task` - asynchronous coding tool

```json
// Input
{
  "task_description": "Migrate the payment module to the new v2 API",
  "repo_url": "https://github.com/org/repo",
  "base_branch": "main"
}

// Output (immediate)
{
  "status": "submitted",
  "job_id": "01HXYZ..."
}
```

Poll with `get_task_status` using the returned `job_id` to watch the job move through `QUEUED -> RUNNING -> {COMPLETED | FAILED | CANCELLED}`.

### `connect_git_host` - interactive OAuth consent

```json
// Input
{ "git_host": "github.com" }

// Output
{
  "status": "connected",
  "git_host": "github.com",
  "message": "Successfully connected to github.com."
}
```

Run this once per git host before submitting coding tasks. The async pipeline cannot pause for OAuth mid-job, so it fails fast with `git_host_not_connected` if credentials are missing.

## Cedar policy action names

Because the Gateway registers a single MCP Server target named `opencode`, Cedar policies reference these action identifiers (three underscores between target name and tool name):

- `opencode___code`
- `opencode___run_coding_task`
- `opencode___connect_git_host`
- `opencode___get_task_status`
- `opencode___list_tasks`
- `opencode___cancel_task`

See [HARDENING.md](HARDENING.md#cedar-policy-engine) for how to switch Cedar from LOG_ONLY to ENFORCE and for example production policies.
