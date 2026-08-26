#!/usr/bin/env bash
#
# Every check that needs no AWS credentials, in one command.
#
#     ./test.sh
#
# **The split this script exists to make.** The repo's verification is mostly seven `verify_*.py`
# suites that each need a deployed stack and real credentials — so running "the tests" was a
# five-minute, region-sensitive act that nobody performs while editing a formatter. The checks below
# need none of that and finish in seconds, which is the only reason they get run at all.
#
# What is deliberately NOT here, and where it lives:
#
#   scripts/verify_isolation.py         7 isolation layers, cross-tenant probes   } need a deployed
#   scripts/verify_tools.py              14 tools through the real gateway         } stack and real
#   scripts/verify_conversation_api.py   streaming, CSRF, a booking by clicking    } credentials
#   scripts/verify_audit.py              CloudTrail attribution
#   scripts/verify_guardrails.py         model-level guardrail (A/B fail by design)
#   scripts/verify_log_masking.py        ingestion-time masking (read-only, cheap)
#   scripts/verify_network.py            VPC topology and endpoint policies
#
#   tools/*/test_local.py  — STALE once the backend moved into a VPC: they call it over HTTPS from a
#   laptop that now has no route to it. The failure reads as a broken tool (the escalation suite
#   reports 3/8 with `queue=None`), which is why they are excluded rather than left to mislead. The
#   fix is the one `verify_isolation.py` applies to its backend check — invoke the Lambda directly
#   with a synthetic proxy event.
#
# A browser pass is not a test suite and is not here either. Thirty passing API checks once coexisted
# with a flow that did not work in a browser at all, so anything user-visible still gets one real
# browser run before it is called done.

set -euo pipefail

cd "$(dirname "$0")"

failed=()
run() {
  local label="$1"
  shift
  printf '\n\033[1m── %s\033[0m\n' "$label"
  if "$@"; then
    printf '\033[32m   ok\033[0m\n'
  else
    printf '\033[31m   FAILED\033[0m\n'
    failed+=("$label")
  fi
}

# The mock TMC backend: routers, tenant scoping, the offer lifecycle, policy arithmetic.
# **`--frozen` so a green suite means the locked versions ran.** Without it `uv run` may re-resolve
# and quietly update the lockfile, so "the tests passed" stops implying "against what is pinned" —
# and the tool Lambdas now install a version read straight from `tools/uv.lock`, which makes lock
# drift a deployment difference rather than a detail.
run "backend (pytest)" bash -c 'cd backend && uv run --frozen pytest -q'

# CloudTrail lookup pagination with fake responses: found, genuinely absent, and search-bound exhausted.
run "verification scripts (pytest)" bash -c 'cd backend && uv run --frozen pytest -q ../scripts/test_verify_audit.py'

# **Twenty-one tests that existed, were counted in the README, and never ran.** The trace-header
# contract in `tools/common` and the PII curation rules in `tools/profile` are ordinary offline tests,
# but the only Python job that could have collected them runs from `backend/`, whose
# `testpaths = ["tests"]` stops at its own directory. So they sat in the tree passing nothing.
#
# `tools/` is its own uv project with its own lock, and its `pythonpath = [".."]` is what makes the
# `tools.*` imports resolve. The `test_local.py` files alongside them contribute nothing here on
# purpose: they are smoke tests against a *deployed* backend, they define no test functions, and their
# work sits behind `__main__` — so collection imports them harmlessly and this job stays offline.
run "tools (pytest)" bash -c 'cd tools && uv run --frozen pytest -q'

# The BFF's closed action registry, handle filtering, cookie flags, and the citation re-authorisation.
# No AWS: the runtime and DynamoDB are faked at the boundary.
#
# **`uv run --frozen` like every other Python job, rather than `.venv/bin/python`.** This one reached
# into a virtualenv by path, which exists only after something else has created it — so on a fresh
# clone the job failed with `.venv/bin/python: No such file or directory` while every suite around it
# passed. `uv run` builds the environment from this package's own `uv.lock` if it is missing, which is
# what made the other jobs survive a clean checkout.
run "conversation API (local checks)" bash -c 'cd conversation-api && uv run --frozen python -m app.test_local'

# **Dependencies first, so a fresh clone can run this suite at all.** `node_modules` does not exist in
# a new checkout, and every frontend job below assumes it — as did `deploy_frontend.sh`, where the
# missing install surfaced at the last step of a first deploy. Cheap on a warm tree: `ci` is a no-op
# when the lock and the tree already agree.
run "frontend (npm ci)" bash -c 'cd frontend && npm ci --silent'
# Card formatters and the calendar file. Absent-field handling and the iCalendar rules — both classes
# fail silently in a browser, so they are asserted here instead.
run "frontend (node --test)" bash -c 'cd frontend && npm test --silent'

# Type errors and the exhaustive `card_type` switch, which is a compile-time guarantee rather than a
# test: removing a case is a build failure by design.
run "frontend (typecheck + build)" bash -c 'cd frontend && npm run build --silent'
run "frontend (lint)" bash -c 'cd frontend && npm run lint --silent'

# **Same reason as the frontend install above, and this one was missing.** Three jobs need
# `infra/node_modules`: the typecheck below, and the prettier check further down which runs
# `npx --no-install prettier` from this directory. On a fresh clone none of them could work.
run "infra (npm ci)" bash -c 'cd infra && npm ci --silent'

# **The infrastructure was not typechecked here at all until a rename proved it needed to be.** An
# import was left pointing at a file that no longer existed and every suite above stayed green,
# because nothing in this script compiled `infra/`. `cdk.json` runs `node dist/bin/infra.js`, so a
# stale `dist/` can also mask a source error — `tsc` is what notices either.
#
# **`--no-install` is not a nicety here, it is the difference between a typecheck and a supply-chain
# accident.** `tsc` on the public registry is not TypeScript; it is an unrelated package last published
# in 2016. A bare `npx tsc` on a clone with no `node_modules` does not fail — it offers to install
# *that*, and sits waiting for a `y`, which on a fresh clone is where this suite stopped. TypeScript is
# a declared devDependency, so with `--no-install` the only `tsc` that can run is the pinned one.
run "infra (typecheck)" bash -c 'cd infra && npx --no-install tsc --noEmit'

# **The second CDK app, which nothing here compiled.** The AgentCore CLI generates and drives its own
# app under `agent/*/agentcore/cdk/`, and it is what actually creates the runtime, gateway, memory and
# policy engine. `infra`'s typecheck above says nothing about it, so a break there surfaced only at
# `agentcore deploy` — twenty minutes into a deploy rather than in seconds here.
#
# Typecheck only, deliberately. A `cdk synth` of that app needs the rendered `agentcore.json`, which
# needs a live deployment to resolve tool Lambda ARNs and the gateway id, so it cannot run on a suite
# that must pass with no AWS account. The generated `test/cdk.test.ts` does synth, but against an
# **empty** spec — no runtimes, no memories — so it asserts nothing about ours and would not have
# caught a missing field on the real runtime.
run "agent cdk app (npm ci)" bash -c 'cd agent/MultiTenantTravel/agentcore/cdk && npm ci --silent'
run "agent cdk app (typecheck)" bash -c 'cd agent/MultiTenantTravel/agentcore/cdk && npx --no-install tsc --noEmit'

# The Lambda bundle installs from `backend/requirements-lambda.txt`; the suite above installs from
# `backend/uv.lock`. Two files, one dependency set, so they drift — and the drift is silent, because
# both halves keep working and the only symptom is a deployed function running a version nothing
# tested. Two files, no network.
run "backend lambda pins match the lock" python3 scripts/check_lambda_pins.py

# **Both ruff gates, because upstream CI runs both** — `check` and `format --check`, on changed
# files, with no `continue-on-error`. Nothing here gated Python at all until 192 findings had
# accumulated. One invocation from `backend/` so paths resolve against a `line-length = 100` config;
# ruff discovers per-directory settings itself.
# **The agent's own source is in this list because it was the one thing nothing checked.** The tests
# beside it were covered; the module they test was not, which is how an unsorted import block and a
# deprecated `datetime.utc` alias survived. Its package ignores `E501` and only `E501` — see the note
# in its `pyproject.toml`. ruff resolves per-package settings itself, so one invocation covers both.
AGENT_APP='../agent/MultiTenantTravel/app/MultiTenantTravel'
PY_PATHS=". ../scripts ../conversation-api ../tools ../shared ../agent/tests ../evaluation $AGENT_APP"
run "python (ruff check)" bash -c "cd backend && uv run --frozen ruff check $PY_PATHS"
run "python (ruff format)" bash -c "cd backend && uv run --frozen ruff format --check $PY_PATHS"

# Prettier, for the same reason — though upstream's JS/TS job sets `continue-on-error`, so this one
# is about keeping the diff readable rather than about passing CI.
# **`--no-install`, and prettier is a declared devDependency of `infra/`.** It was a bare
# `npx prettier`, which downloads whatever version is current the first time anyone runs the suite:
# needs network on a fresh clone, and an unpinned formatter can change the check under you. Declared in
# `infra/` rather than a new root `package.json` because that project already exists and owns most of
# the formatted files; the paths stay repo-relative, so the globs are unchanged.
run "js/ts (prettier)" bash -c 'cd infra && npx --no-install prettier --check "../frontend/src/**/*.{ts,tsx}" "../frontend/tests/**/*.mjs" "lib/**/*.ts" "bin/**/*.ts" "lambda/**/*.mjs" "../shared/generated/*.ts"'

# The claim guard and forced tool choice. **Run from inside the agent package** — `agentcore.json`
# sets one `codeLocation`, so the module under test is importable only from there. `--group dev`
# because pytest is not a runtime dependency and must not end up in the deployed zip: a group is
# omitted by a plain `uv sync`, so the bundle never asks for it. It was `--with pytest`, which resolved
# from the network on every run.
run "agent (pytest)" bash -c 'cd agent/MultiTenantTravel/app/MultiTenantTravel && uv run --frozen --group dev python -m pytest ../../../tests -q'

# The task fixtures are data, so nothing checks them until the deployed runner reads them —
# by which point a misspelled persona or a `by_persona` block naming a traveller the task never
# runs as has already reported green. Seconds, no AWS account.
run "evaluation (fixtures)" bash -c 'cd evaluation && uv run --frozen --group dev python -m pytest tests -q'

# Forged, tampered, `alg:none`, expired and spoofed-header tokens against the gateway interceptor.
run "gateway interceptor (node)" node infra/lambda/interceptor/test_local.mjs

# The card contract itself: every tool's card shape against `shared/cards.py`.
run "card contract" bash -c 'cd backend && uv run --frozen python -c "
import sys; sys.path.insert(0, \"..\")
from shared.cards import CardType, REQUIRED_DATA, ALLOWED_ACTIONS
missing = [t for t in CardType if t not in REQUIRED_DATA or t not in ALLOWED_ACTIONS]
assert not missing, f\"card types with no contract: {missing}\"
print(f\"{len(list(CardType))} card types, all with required-data and allowed-action entries\")
"'

# **Nothing account-specific may reach a commit**, because this repo is published and a commit cannot
# be unpublished.
#
# `render_agent_spec.py` rewrites four tracked files *in place* with the deploying account's id — the
# agent spec, the deployment target and two IAM policy documents. The committed versions carry
# `000000000000` and `{{ACCOUNT}}` placeholders. So the working tree is dirty with a real account id
# after every deploy, and the only thing standing between that and a public commit is whoever is
# looking. The AgentCore CLI reads the spec from a fixed path, so the render cannot be redirected
# somewhere ignored, and ignoring the spec would remove the sample's main declarative artefact from
# the repo.
#
# **Checked against the commit, not the index — the first version of this checked the index and
# therefore checked nothing.** `git diff --cached` only sees files between `git add` and
# `git commit`. Anyone who writes `git add x && git commit` in one command never has a staged tree
# for this to inspect, so it reported "nothing staged", passed, and went on passing after a real
# account id had been committed. Sixteen occurrences across four files got in that way and survived
# every later run. `HEAD` is the right subject: it is what would actually be published, it is always
# inspectable, and a dirty worktree after a deploy still does not fail the run — which was the only
# thing the index version got right.
#
# Three exemptions, each established by running this against the real tree rather than reasoned about
# in advance:
#
#   * `753240598075` is AWS's own account for the published Lambda Web Adapter layer. A public layer
#     ARN names the account that publishes it, so this one belongs in the repo.
#   * `123456789012` is the account id AWS uses throughout its own documentation. It appears in a
#     unit-test fixture here, which is exactly what a made-up account id is for.
#   * Lock files are excluded. They carry hex digests, and a digest containing twelve consecutive
#     decimal digits is common — seven in `backend/uv.lock` alone. Nothing hand-written goes into
#     them, so there is nothing for this check to protect.
run "no account ids committed" bash -c '
hits=$(git grep -hoE "(^|[^0-9])[0-9]{12}([^0-9]|$)" HEAD -- . ":!*.lock" ":!*-lock.json" 2>/dev/null \
  | grep -oE "[0-9]{12}" \
  | grep -vE "^(0{12}|753240598075|123456789012)$" | sort -u)
[ -z "$hits" ] && { echo "  no account ids in the committed tree"; exit 0; }
for id in $hits; do
  printf "  %s appears in:\n" "$id"
  git grep -l "$id" HEAD -- . ":!*.lock" ":!*-lock.json" | sed "s|^HEAD:|    |"
done
exit 1
'

printf '\n'
if [ ${#failed[@]} -eq 0 ]; then
  printf '\033[32mall local suites passed\033[0m\n'
else
  printf '\033[31m%d suite(s) failed:\033[0m %s\n' "${#failed[@]}" "${failed[*]}"
  exit 1
fi
