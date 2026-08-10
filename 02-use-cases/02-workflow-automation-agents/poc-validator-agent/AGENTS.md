# POC Validator Agent — AI Coding Assistant Context

> **For humans:** see [README.md](./README.md) and [docs/decisions/](./docs/decisions/).

Reviews a proposed AWS architecture against segment and industry rules, prices it, scores
a Scope of Work, and recommends AWS-only further reading. Runs on Amazon Bedrock
AgentCore via the **AgentCore CLI** (`agentcore/agentcore.json`).

> **Never generate `.bedrock_agentcore.yaml`.** The Starter Toolkit is deprecated and its
> use is penalised in `02-use-cases/use-case-assessment.md`. AgentCore resources are
> declared in `agentcore/agentcore.json` and managed by `agentcore deploy`.

## Architecture

```
Streamlit UI (ui/)  — separate venv, no agentcore dependency
  │ HTTP
  ▼
AgentCore Runtime (app/pocvalidator/)
  Phase 1  Diagram extraction   Sonnet + vision  → submit_extraction
           ⤷ CONFIRMATION GATE — returns awaiting_confirmation, does not proceed
  Phase 2  Validation           deterministic
  Phase 3  Pricing              deterministic
  Phase 4  SOW scoring          Haiku → submit_sow_assessment, weights applied in Python
  Phase 5  Recommendations      deterministic, domain allowlist
  │
  ├─ Gateway (MCP, CUSTOM_JWT, Cedar ENFORCE) → AWS Documentation MCP target
  ├─ Identity  @requires_access_token M2M for the Gateway
  ├─ Memory    SEMANTIC + SUMMARIZATION, pocvalidator/{actorId}/…
  └─ Evaluators  ExtractionFidelity, SowGrading + 3 built-ins
```

## Invariants — do not break these

1. **`core/` imports nothing from AWS and nothing from Streamlit.** It is the shared
   spine for the agent, the UI and the tests. Adding a boto3 import there breaks offline
   testing and the no-account quickstart.
2. **The model never computes a total, a cost, or a finding.** It extracts and it bands.
   Arithmetic and rule evaluation are Python. If you find yourself asking the model for a
   score, put the weights in YAML instead.
3. **All `os.getenv` calls live in `config.py`.** A test enforces this
   (`test_env_vars_are_only_read_in_config`). `catalog.py` is the single exception, for
   `POC_VALIDATOR_ROOT`.
4. **An unknown service pair is `unverified`, never `native`.** Silence must not read as
   approval.
5. **Never widen the recommendation allowlist to a non-AWS domain.** It is enforced in
   `core/resources.py`, and `test_no_catalogue_entry_is_rejected_by_the_allowlist` fails
   CI if the catalogue drifts.
6. **No hardcoded account IDs, ARNs or regions.** Enforced by
   `test_no_hardcoded_account_ids_or_arns`.
7. **The confirmation gate stays.** Do not "streamline" it away.

## Conventions

- Self-documenting code; comments only where logic is non-obvious.
- Comments never reference previous implementations — no "changed from X".
- Simplicity over cleverness. This is a sample; a reader should follow it in one sitting.
- Data over code: a new industry, service or reading recommendation is a YAML edit.
- Region default `us-east-1` via `AWS_REGION`; the pricing snapshot is `ap-south-1` and
  says so in the UI.

## Adding things

**An industry** → `rules/industries/<id>.yaml`. Needs `id`, `name`, `description`,
`requirements[]` with `applies_to`, `attribute` (must exist in `data/services.yaml`),
`operator` (`equals` | `min` | `max`), `value`, `severity`, `rationale`, `remediation`,
`doc_url`. Tests validate every rule against the attribute registry.

**A service** → entry in `data/services.yaml`, rates in `data/pricing.yaml`, valid edges
in `data/integrations.yaml`.

**A reading recommendation** → entry in `data/resources.yaml` with an allowlisted URL and
`tags` that overlap attribute names, categories, segment ids or industry ids.

## Commands

```bash
python -m pytest tests/ -q                        # 55 tests, offline
python scripts/local_review.py --example fsi_loan # CLI review, no AWS
streamlit run ui/app.py                           # UI (separate venv)
agentcore validate && agentcore dev               # local runtime, hot reload
./deploy.sh dev  /  ./destroy.sh dev
```
