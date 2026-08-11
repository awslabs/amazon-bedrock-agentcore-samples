# CI & Security Scanning

This repository is hosted as a **private GitLab project** and runs its full offline
verification plus GitLab's security scanners on every push. This document explains what
runs, why, and how findings have been handled.

## Pipeline layout (`.gitlab-ci.yml`)

| Job | Image | What it verifies |
|---|---|---|
| `pytest` | `python:3.12-slim` | The 106 offline tests — deterministic core, tool boundary, catalogue integrity, repo conventions. JUnit report attached to the pipeline. |
| `pip-audit` | `python:3.12-slim` | The exact dependency set the agent container installs (`app/pocvalidator/requirements.txt`) against the PyPI advisory database. Fails the pipeline on any known-vulnerable resolved version. |
| `jest-agentcore-cdk` | `node:22` | TypeScript build + jest suite for the AgentCore CDK app, then an `npm audit` JSON artifact. |
| `jest-web-cdk` | `node:22` | Same for the web-layer CDK app. |
| `semgrep-sast` (template) | GitLab SAST | Static analysis of Python and TypeScript sources. |
| `secret_detection` (template) | GitLab Secret Detection | Credential scan with `SECRET_DETECTION_HISTORIC_SCAN: "true"` — the full git history was scanned on the initial push, not just the diff. |
| `gemnasium-*` (template) | GitLab Dependency Scanning | `app/pocvalidator/requirements.txt`, `agentcore/cdk/package-lock.json`, `web/cdk/package-lock.json`. |
| `kics-iac-sast` (template) | GitLab IaC SAST | `Dockerfile`s (agent runtime image, AWS Documentation MCP target). |

Notes on tiers: every scanner above **runs and produces its `gl-*-report.json` artifact on
all GitLab tiers**. The aggregated Vulnerability Report UI is an Ultimate feature; on lower
tiers, read the JSON artifacts from the job pages (that is how the findings below were
triaged).

## Dependency posture (as of 2026-08-12)

**Python (agent):** floors raised to the versions the suite is verified against —
`bedrock-agentcore >=1.21.0`, `strands-agents >=1.51.0`, `mcp >=1.29.0`,
`botocore[crt] >=1.43.69`, `aws-opentelemetry-distro >=0.19.0`. Upper bounds unchanged
(the Dockerfile installs `requirements.txt`, so deployed containers stay reproducible).

**Python (UI):** `streamlit` verified on 1.61.1 within the existing `>=1.50,<2` range.
The UI and agent still cannot share a virtualenv — see ADR 0005.

**npm (both CDK apps):** `aws-cdk-lib` bumped `~2.261.0 → 2.264.0` (exact pin);
`npm overrides` keeps every reachable `brace-expansion` at ≥5.0.9. Known residual:
`aws-cdk-lib`'s *bundled* `brace-expansion` 5.0.8 (GHSA-rgw5-rvv9-x895, HIGH) — bundled
dependencies are physically inside the published `aws-cdk-lib` tarball and cannot be
overridden. Build-time-only exposure (`cdk synth` asset-globbing, devDependency path);
clears automatically at the next `aws-cdk-lib` release that bundles 5.0.9. Tracked in the
README's Known Limitations.

## Scanner findings log

This section is the running record of every scanner finding and its resolution.
(Populated per pipeline run; newest first.)

### Initial push

- Pending first pipeline — this log is updated as results land.
