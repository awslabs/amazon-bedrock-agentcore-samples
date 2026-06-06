# Agent Skills

| Information         | Details                                                             |
|:--------------------|:--------------------------------------------------------------------|
| Tutorial type       | Advanced Example                                                    |
| Agent type          | Document and spreadsheet generation assistant                       |
| Agentic Framework   | None (direct boto3)                                                 |
| LLM model           | Anthropic Claude Haiku 4.5                                          |
| Tutorial components | AgentCore harness — skills parameter, Node.js container, xlsx skill |
| Example complexity  | Intermediate                                                        |

## Overview

Extend agent capabilities with pre-built skill bundles that provide specialized instructions,
code templates, and domain knowledge. Demonstrates the `xlsx` skill to create professional
Excel spreadsheets with formulas, formatting, and multiple sheets.

## What are Agent Skills?

Agent Skills are pre-built capability bundles installed on the agent's VM:

- **Specialized instructions** — step-by-step guidance for complex tasks
- **Code templates** — proven implementations for file formats (xlsx, pdf, docx)
- **Domain knowledge** — best practices and common patterns

Skills are especially valuable with smaller/cheaper models that lack built-in knowledge
of specialized file formats. The skill provides the knowledge the model needs.

```python
# Install skill on the VM
client.invoke_agent_runtime_command(
    agentRuntimeArn=harness_arn,
    runtimeSessionId=session_id,
    body={"command": "npx skills add https://github.com/anthropics/skills --skill xlsx --yes"},
)

# Use skill in an invocation
client.invoke_harness(
    harnessArn=harness_arn,
    runtimeSessionId=session_id,
    skills=[{"path": ".agents/skills/xlsx"}],
    messages=[...],
)
```

## Sample Prompts

**Prompt**: "Create a 5-day Amsterdam trip budget spreadsheet with EUR/USD columns, formulas, and formatting."
**Expected Behavior**: Agent uses xlsx skill to generate `/tmp/amsterdam_budget.xlsx` with currency formatting and SUM formulas.

**Prompt**: "Create a quarterly sales report with 3 sheets: Summary, Monthly Breakdown, Top Products."
**Expected Behavior**: Agent generates a multi-sheet report with conditional formatting, freeze panes, and formula-driven status columns.

**Prompt**: "Create a project tracking spreadsheet with 10 tasks, priorities, and % completion."
**Expected Behavior**: Agent creates a formatted task tracker with status columns and a summary row.

**Prompt**: "Make a comparison table of 5 programming languages by speed, ease, ecosystem."
**Expected Behavior**: Agent creates a formatted comparison table with color coding.

## Key Concepts

**Node.js container required**: The xlsx skill uses npm packages (`xlsx` or `exceljs`). Attach a Node.js container before installing skills.

**Session persistence**: Install the skill once in a session. Subsequent invocations in the same session can use the skill — the installation persists on the VM.

**File download**: Generated files live on the agent's remote VM. Use `invoke_agent_runtime_command` with `base64` to transfer them locally.

## Troubleshooting

### Issue: `npx skills add` command hangs
**Solution**: The command downloads from GitHub. Ensure outbound HTTPS is available from your microVM. First-run may take 2-3 minutes.

### Issue: Skill not found error during invocation
**Solution**: Verify the path exists: `ls -la .agents/skills/xlsx/`. Run the installation in the same session you're invoking from.

### Issue: Generated xlsx file is empty or corrupted
**Solution**: Check that the agent's file path matches the base64 read command. The file must exist on the VM before you can download it.

## AgentCore CLI

Create and deploy a harness project via the CLI (preview channel), then use `ExecuteCommand` to install skills in your session:

```bash
npm install -g @aws/agentcore@preview
agentcore create --name myskillsagent --model-provider bedrock
agentcore deploy
agentcore invoke --harness myskillsagent \
  --session-id "$(uuidgen)" \
  "Create a 5-day Amsterdam trip budget spreadsheet with EUR/USD columns and formulas."
```

Skills installation (`npx skills add`) happens programmatically via `invoke_agent_runtime_command` as shown in this tutorial.

## Clean Up

```python
control.delete_harness(harnessId=harness_id)
from utils.iam import delete_harness_role
delete_harness_role()
```

## Running the Python Scripts

```bash
pip install -r ../../requirements.txt
```

```bash
python agent_skills.py
```

Downloaded files are saved to `/tmp/amsterdam_budget.xlsx` and `/tmp/q1_sales_report.xlsx`.
