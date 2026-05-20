# AgentCore Managed Tools

Fully managed, sandboxed environments that your agents can use at runtime — no infrastructure to provision or maintain.

## Top-level layout

| Folder | What's inside |
|:-------|:--------------|
| [`01-code-interpreter/`](./01-code-interpreter/) | Sandboxed Python 3.12 execution environment with a writable filesystem, shell, and AWS CLI — file operations, agent-driven code execution, data analysis, and shell commands |
| [`02-browser/`](./02-browser/) | Managed headless Chromium sandbox accessible via CDP WebSocket — Nova Act, Browser-Use, Strands, and domain filtering demos |

## How this section is organized

Each tool maps to one sub-folder. Both follow the same structure:

```
<tool>/
  README.md               ← tool overview, API concepts, IAM permissions
  requirements.txt        ← shared dependencies for all sub-demos
  utils/                  ← shared agent / client code
  01-<demo>/              ← one script per capability
  02-<demo>/
  ...
```

Sub-demos inside each tool folder are **independent** — run any one without running the others first.

## The two tools at a glance

| | Code Interpreter | Browser Tool |
|:--|:-----------------|:-------------|
| **What it provides** | Python 3.12 sandbox + shell + AWS CLI | Headless Chromium + CDP WebSocket |
| **Session model** | `code_session()` context manager | `browser_session()` context manager |
| **Data plane operations** | `executeCode`, `executeCommand`, `writeFiles`, `listFiles` | CDP WebSocket + SigV4 auth headers |
| **Automation frameworks** | Direct SDK or Strands agent | Nova Act, Browser-Use, Strands, Playwright |
| **Isolation** | Per session, persistent filesystem within session | Per session, auto-cleanup on exit |
| **Custom resource** | `create_code_interpreter()` with custom execution role | `create_browser()` with execution role + S3 recording |
| **IAM service** | `bedrock-agentcore` (data plane) | `bedrock-agentcore` (data plane) |

## Finding things

- **Run arbitrary Python code from an agent** → `01-code-interpreter/02-code-execution/`
- **Upload files into a sandbox and execute scripts** → `01-code-interpreter/01-file-operations/`
- **Multi-step data analysis with a persistent session** → `01-code-interpreter/03-data-analysis/`
- **Shell commands and AWS CLI inside the sandbox** → `01-code-interpreter/04-run-commands/`
- **Start a browser session and issue a natural language prompt** → `02-browser/01-nova-act/`
- **Connect Browser-Use to an AgentCore session** → `02-browser/02-browser-use/`
- **Record, replay, and log browser sessions** → `02-browser/03-observability/`
- **Strands agent with browser as a tool** → `02-browser/04-strands/`
- **Restrict the browser to an allow-listed set of domains** → `02-browser/05-domain-filtering/`

## Resources

- [Code Interpreter — Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-overview.html)
- [Code Interpreter IAM reference](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-permissions.html)
- [Browser Tool — Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool-overview.html)
- [Browser Tool IAM reference](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool-permissions.html)
- [boto3 Data Plane Reference (`bedrock-agentcore`)](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-agentcore.html)

## Prerequisites

- Python 3.12+
- AWS account with Amazon Bedrock AgentCore access
- AWS CLI configured with credentials

## Running the Python Scripts

```bash
# Code Interpreter
pip install -r 01-code-interpreter/requirements.txt

python 01-code-interpreter/01-file-operations/file_operations.py
python 01-code-interpreter/02-code-execution/code_execution.py
python 01-code-interpreter/03-data-analysis/data_analysis.py

# Shell/AWS CLI demo requires a custom execution role
export EXECUTION_ROLE_ARN=arn:aws:iam::<account>:role/<role-name>
python 01-code-interpreter/04-run-commands/run_commands.py
```

```bash
# Browser Tool
pip install -r 02-browser/requirements.txt
playwright install chromium

# Nova Act (requires NOVA_ACT_API_KEY)
python 02-browser/01-nova-act/getting_started.py \
  --nova-act-key $NOVA_ACT_API_KEY \
  --prompt "Search Amazon for MacBooks and return the first result"

# Browser-Use
python 02-browser/02-browser-use/getting_started.py \
  --task "Search for a coffee maker on amazon.com and extract the first result"

# Session recording and replay (creates custom browser with S3 recording)
python 02-browser/03-observability/browser_observability.py \
  --nova-act-key $NOVA_ACT_API_KEY

# Strands agent with browser tool
python 02-browser/04-strands/demo.py \
  --url "https://www.marketwatch.com/investing/stock/tsla" \
  --question "What is the current stock price and P/E ratio?"

# Domain filtering (deploy CloudFormation stack first)
aws cloudformation deploy \
  --template-file 02-browser/05-domain-filtering/agentcore-browser-firewall.yaml \
  --stack-name agentcore-browser-firewall \
  --capabilities CAPABILITY_IAM
python 02-browser/05-domain-filtering/verify_domain_filtering.py
```
