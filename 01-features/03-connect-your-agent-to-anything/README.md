# Connect Your Agent to Anything

Give your agents access to powerful built-in tool environments — sandboxed code execution and headless browser automation — managed and scaled by Amazon Bedrock AgentCore.

## Top-level layout

| Folder | What's inside |
|:-------|:--------------|
| [`01-code-interpreter/`](./01-code-interpreter/) | Sandboxed Python execution environment — run code, execute shell commands, upload and read files, use the AWS CLI, all in an isolated per-session sandbox |
| [`02-browser/`](./02-browser/) | Fully managed headless Chromium browser — drive it with Nova Act, Browser-Use, Strands, or raw Playwright via the Chrome DevTools Protocol |

## How these tools work

Both tools follow the same pattern: AgentCore provisions an isolated sandbox session on demand, your agent calls tool APIs within that session, and the session terminates when you stop it. No infrastructure to manage.

### Code Interpreter

- **What it is**: A Python 3.12 sandbox with a writable filesystem, shell, and AWS CLI
- **Use it for**: Agents that need to write and run code, perform data analysis, install packages, or make authenticated AWS API calls
- **Entry point**: `from bedrock_agentcore.tools.code_interpreter_client import code_session`

```python
from bedrock_agentcore.tools.code_interpreter_client import code_session

with code_session("us-west-2") as client:
    result = client.invoke("executeCode", {
        "code": "print(2 + 2)",
        "language": "python",
        "clearContext": False,
    })
```

### Browser Tool

- **What it is**: A managed headless Chromium instance accessed over the Chrome DevTools Protocol (CDP)
- **Use it for**: Agents that need to navigate websites, fill forms, extract structured data, or test web apps
- **Entry point**: `from bedrock_agentcore.tools.browser_client import browser_session`

```python
from bedrock_agentcore.tools.browser_client import browser_session

with browser_session("us-west-2") as client:
    ws_url, headers = client.generate_ws_headers()
    # Pass ws_url + headers to Nova Act, Browser-Use, Playwright, or Strands
```

## Quick Start

```bash
# Code Interpreter
pip install -r 01-code-interpreter/requirements.txt
python 01-code-interpreter/01-file-operations/file_operations.py

# Browser Tool
pip install -r 02-browser/requirements.txt
playwright install chromium
python 02-browser/01-nova-act/getting_started.py \
  --nova-act-key $NOVA_ACT_API_KEY \
  --prompt "Search Amazon for MacBooks"
```

## Resources

- [Code Interpreter — Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-overview.html)
- [Browser Tool — Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool-overview.html)
- [boto3 Data Plane Reference (`bedrock-agentcore`)](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-agentcore.html)
