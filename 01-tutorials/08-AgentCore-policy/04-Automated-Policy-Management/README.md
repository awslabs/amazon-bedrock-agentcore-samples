# Amazon Bedrock AgentCore Policy - Automated Policy Management

## Overview

This sample demonstrates **automated, agent-driven Cedar policy lifecycle management** for Amazon Bedrock AgentCore.

A policy orchestration agent — built with [Strands Agents](https://github.com/strands-agents/sdk-python) — discovers tools on an AgentCore Gateway, reads the RBAC permission manifests those tools emit on registration, auto-generates valid Cedar policies using the NL2Cedar API, routes each policy through a human reviewer via Amazon SNS, and commits approved policies to a Policy Engine attached to the Gateway.

## What You Will Learn

1. How tools registered on an AgentCore Gateway emit structured RBAC permission manifests
2. How to convert RBAC metadata into natural language policy descriptions
3. How to use the AgentCore NL2Cedar API to auto-generate Cedar policies
4. How to implement a human-in-the-loop review workflow using Amazon SNS + interactive approval
5. How to programmatically create policies in a Policy Engine and enforce them at the Gateway

## Architecture

```
  Lambda Tools
  (FinancialReportTool, TradeExecutionTool)
       |
       | register on Gateway (emits RBAC manifest)
       v
  AgentCore Gateway
       |
       |<---- Policy Orchestration Agent (Strands)
       |         1. list_gateway_tools
       |         2. get_tool_rbac_permissions
       |         3. generate_nl_policy_statement
       |         4. generate_cedar_policy (NL2Cedar API)
       |         5. request_human_approval (SNS email + interactive)
       |         6. create_policy_in_engine
       v
  Policy Engine
  (Cedar policies: enforce parameter constraints)
       |
       | ALLOW / DENY at runtime
       v
  Tool Invocations
```

## Demo Scenario: Financial Data Platform

Two Lambda-backed tools are deployed:

| Tool | Function | RBAC-Derived Cedar Rules |
|------|----------|--------------------------|
| FinancialReportTarget | `get_financial_report` | `classification_level` must be `internal`; `region` in `{US, EU, APAC}` |
| TradeExecutionTarget  | `execute_trade`        | `amount` must not exceed 500,000 |

## File Structure

```
04-Automated-Policy-Management/
├── Automated-Policy-Management.ipynb   # Main notebook - start here
├── requirements.txt
├── README.md
└── scripts/
    ├── setup_infrastructure.py         # Deploy Lambda + create Gateway + attach targets
    ├── cedar_utils.py                  # RBAC->NL conversion and NL2Cedar helper
    ├── human_review.py                 # SNS/SQS review infrastructure
    ├── policy_orchestrator.py          # Strands agent + tool definitions
    └── lambda-tools/
        ├── financial_report_tool.js    # FinancialReportTool Lambda (Node.js)
        └── trade_execution_tool.js     # TradeExecutionTool Lambda (Node.js)
```

## Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.10+
- Access to Amazon Bedrock (Nova Lite model)
- IAM permissions for: Lambda, IAM, Cognito, Bedrock AgentCore, SNS, SQS

## Quick Start

1. Open `Automated-Policy-Management.ipynb` in JupyterLab
2. Run cells sequentially from Step 0 through Step 6
3. When prompted for an email, enter a valid address to receive SNS review notifications
4. Approve or reject each generated Cedar policy when the agent pauses for review
5. Run the test cells to verify policy enforcement
6. Run the cleanup cell when done

## Key Concepts

### RBAC Manifest Emission

When a tool is attached to an AgentCore Gateway, its registration contract includes a **RBAC permission manifest** — a structured JSON object describing:
- Which user roles may invoke the tool
- Data classification requirements
- Input parameter constraints (allowed values, max values)

The orchestrator reads this manifest from `config.json` after infrastructure setup.

### NL2Cedar Generation

The `cedar_utils.py` module converts each RBAC manifest entry through two stages:
1. `rbac_to_natural_language()` — deterministic conversion to a policy sentence
2. `generate_cedar_from_nl()` — calls the AgentCore `generate_policy` API

### Human-in-the-Loop

For each generated policy:
1. An SNS notification is published (email to subscribed reviewer)
2. The orchestrator agent pauses and displays the Cedar policy in the notebook
3. The operator types `yes` (approve) or `no` (reject)
4. Only approved policies are created in the Policy Engine

## Relationship to Other Samples

This sample builds on concepts from:
- `01-Getting-Started`: Gateway setup patterns, agent-with-tools structure
- `02-Natural-Language-Policy-Authoring`: NL2Cedar API usage

The infrastructure setup reuses the same Gateway/Lambda/PolicyClient patterns established in those samples.
