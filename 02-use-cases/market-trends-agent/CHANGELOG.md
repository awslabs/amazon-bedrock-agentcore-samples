# Changelog

## [Unreleased]

### Fixed

#### `evaluators/scripts/deploy.py` — production control plane endpoint
- **Removed** the `CP_ENDPOINT` env var and its gamma default (`https://gamma.us-west-2.elcapcp.genesis-primitives.aws.dev`). That endpoint is internal-only and not accessible from customer accounts.
- **Changed** `_cp_client()` to use the `bedrock-agentcore-control` boto3 service (production control plane). Evaluators registered here are visible to the production data plane (`bedrock-agentcore`), which resolves the `ResourceNotFoundException` that occurred when evaluators were registered on the gamma CP.
- **Removed** the hardcoded `AGENT_RUNTIME_ARN` default (pointing to a specific account/runtime). Added `_resolve_agent_arn()` which reads from the `AGENT_RUNTIME_ARN` env var or falls back to the `.agent_arn` file written by `deploy.py`. Exits with a clear error message if neither is set.
- **Fixed** `_create_online_config()` to accept `agent_runtime_arn` as a parameter instead of reading the module-level constant, making the function easier to test and reason about.

#### `evaluators/iam/trust-policy.json` — remove internal service principal
- **Removed** `preprod.genesis-service.aws.internal` from the trust policy `Principal.Service` list. This was an Amazon-internal pre-production service principal that is not valid in customer accounts and would cause IAM role assumption to fail at runtime.
- Trust policy now contains only `bedrock-agentcore.amazonaws.com`.

#### `evaluators/scripts/invoke.py` — remove hardcoded account ARN
- **Removed** the hardcoded `AGENT_RUNTIME_ARN` default (pointing to a specific account). Replaced with the same `_resolve_agent_arn()` pattern used in `evaluators/scripts/deploy.py` — reads from `AGENT_RUNTIME_ARN` env var or `.agent_arn` file.

### Removed

#### `pyproject.toml` — starter toolkit dependency
- **Removed** `bedrock-agentcore-starter-toolkit` from the project dependencies. This package was used only in `deploy.py` for the `Runtime` class; the agent code itself uses the `bedrock-agentcore` SDK directly (`BedrockAgentCoreApp`, `MemoryClient`).

### Changed

#### `cleanup.py` — replace starter toolkit with SDK and boto3
- **Removed** `from bedrock_agentcore_starter_toolkit import Runtime` and `self.runtime = Runtime()`.
- **Added** `boto3.client("bedrock-agentcore-control")` as `self.agentcore_control`. Runtime deletion now calls `agentcore_control.delete_agent_runtime(agentRuntimeId=agent_id)` directly.
- Memory cleanup continues to use `bedrock_agentcore.memory.MemoryClient` (SDK), unchanged.

#### `deploy.py` — replace starter toolkit with SDK and boto3
- **Removed** `from bedrock_agentcore_starter_toolkit import Runtime` and all uses of `Runtime.configure()`, `Runtime.launch()`, and `Runtime.status()`.
- **Added** `from botocore.exceptions import ClientError` import.
- **Added** `_trigger_codebuild()` method — triggers the existing CodeBuild project (`bedrock-agentcore-{agent_name}-builder`) via boto3 and polls for completion. Raises `RuntimeError` with clear instructions if the project does not exist (pointing the user to run `agentcore deploy` once to bootstrap it).
- **Added** `_ensure_runtime()` method — uses `boto3.client("bedrock-agentcore-control")` to list existing runtimes and either update the matching one or create a new runtime. Replaces the starter toolkit's `Runtime.launch()`.
- **Rewrote** `deploy_agent()` to call `_trigger_codebuild()` then `_ensure_runtime()` instead of the toolkit. Memory creation and IAM creation remain unchanged (already used the SDK and boto3 respectively).

### Fixed (discovered during live testing)

#### `evaluators/scripts/invoke.py` — missing `Path` import
- Added `from pathlib import Path` (was missing after the `_resolve_agent_arn()` refactor).

#### `evaluators/scripts/deploy.py` — `aws/spans` added to data source
- The online eval config was initially created with only the runtime log group
  (`/aws/bedrock-agentcore/runtimes/…-DEFAULT`). The actual OTel spans (with
  `gen_ai.tool.name`, `session.id`, etc.) live in `aws/spans`. Updated
  `_create_online_config()` to include both log groups.

#### `evaluators/workflow_contract_gsr/lambda_function.py` — agent-agnostic contract
- `DEFAULT_CONTRACT` originally used LangGraph tool names only (`identify_broker`,
  `get_broker_financial_profile`, `update_broker_financial_interests`,
  `parse_broker_profile_from_message`). Updated to also cover the Strands agent's
  tool names (`update_broker_profile`, `get_broker_profile`) and removed the
  `identify_broker` group (not a separate tool in the Strands implementation).
  Both agent styles now score correctly against the contract.

#### `evaluators/schema_validator/lambda_function.py` — status-only span support
- Strands agents emit `gen_ai.tool.status: "success"` in span attributes but do not
  embed output text (`gen_ai.tool.call.result` is absent). Added a fallback in
  `_tool_output_text()` to return the status string when no richer output is
  available. Added `_is_status_only()` helper so `_validate_get_stock_data()` and
  `_validate_search_news()` pass on status-only spans rather than failing. Agents
  that do embed result text continue to be validated structurally as before.

### Added

#### `README.md` — custom code-based evaluators documentation
- Added a full **"Evaluating Your Agent with Custom Code-Based Evaluators"** section covering:
  - How code-based evaluators work (data flow diagram)
  - Description of all five evaluators with level, folder, and what each checks
  - Evaluator label reference table
  - IAM requirements for the execution roles
  - Step-by-step setup instructions (`evaluators/scripts/deploy.py`)
  - Traffic generation guide (`evaluators/scripts/invoke.py`) with per-scenario expected outcomes
  - Results viewing guide (`evaluators/scripts/results.py`)
  - **AgentCore CLI** reference — `agentcore eval evaluator create`, `agentcore add online-eval`, `agentcore run eval`, `agentcore evals history`, `agentcore logs evals`, `agentcore pause/resume online-eval`
  - Evaluator cleanup instructions
- Added evaluators to the architecture diagram and component table.
- Corrected LLM model name in architecture section (Claude Haiku 4.5, matching the code).
- Added link to official AWS docs: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-based-evaluators.html
