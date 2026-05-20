# Custom Containers

| Information         | Details                                                          |
|:--------------------|:-----------------------------------------------------------------|
| Tutorial type       | Advanced Example                                                 |
| Agent type          | Coding assistant                                                 |
| Agentic Framework   | None (direct boto3)                                              |
| LLM model           | Anthropic Claude Haiku 4.5                                       |
| Tutorial components | AgentCore harness — Custom Container, ExecuteCommand             |
| Example complexity  | Intermediate                                                     |

## Overview

Attach any custom container image to a harness so the agent runs in your own environment.
Demonstrates Node.js, Go, and Python container presets, plus cross-compilation on Go.

## What is a Custom Container?

By default, harness runs on Amazon Linux 2023 with Python. Custom containers let you bring any Linux ARM64 image:

- Specific language runtimes (Node.js, Go, Rust, Java, Ruby)
- System libraries (Chromium, FFmpeg, ImageMagick)
- Pre-installed dependencies and source code
- A locked-down environment that matches production

## Architecture

```
[harness resource]
    │
    └── update_harness(environmentArtifact.containerConfiguration.containerUri)
                │
                ▼
        [Custom container image]
        e.g. public.ecr.aws/docker/library/node:slim
                │
                ▼
        [Firecracker microVM]
        - node, npm, full Node.js ecosystem
        - Agent can install packages, run servers, use curl
        - Same session ID = same VM state persists
```

## Sample Prompts

**Prompt (node)**: "Write a Node.js HTTP server on port 3000 that returns JSON with the current time. Test it, then kill the server."
**Expected Behavior**: Agent creates `server.js`, starts it in background, makes an HTTP request, shows JSON output, kills server.

**Prompt (go)**: "Write a Go HTTP server, build it, run it, and curl it."
**Expected Behavior**: Agent initializes a Go module, writes `main.go`, runs `go build`, starts binary, curls it, shows response.

**Prompt (node/npm)**: "Install chalk and write a colorful banner script."
**Expected Behavior**: Agent runs `npm install chalk`, writes `colors.js`, executes it showing colored output.

**Prompt (go/cross-compile)**: "Cross-compile for linux/amd64 and show the file info."
**Expected Behavior**: Agent sets `GOOS=linux GOARCH=amd64`, runs `go build -o goserver_linux_amd64`, shows file with `file` command.

## Key Concepts

**Container update timing**: After `update_harness`, wait for the harness to return to `READY` status before invoking (the update is async).

**Session isolation**: Each `runtimeSessionId` gets a fresh VM. After updating the container, use a new session ID to get a VM with the updated image.

**ARM64 requirement**: Container images must support `linux/arm64`. All `public.ecr.aws/docker/library/` official images include ARM64 variants.

## Troubleshooting

### Issue: Agent can't find `node` command
**Solution**: The container update may not be complete yet. Ensure `get_harness` returns `READY` before invoking. Also use a new session ID after the container update.

### Issue: `npm install` fails with network errors
**Solution**: Outbound internet access from the microVM depends on your account's network configuration. If using VPC, ensure appropriate routes exist.

### Issue: Go compilation fails with "module not found"
**Solution**: Ensure the agent initializes a Go module (`go mod init`) before writing source files. The script prompt explicitly asks for this.

## AgentCore CLI

Custom container configuration is supported via the AgentCore CLI (preview channel):

```bash
npm install -g @aws/agentcore@preview
agentcore create --name mycontaineragent --model-provider bedrock
```

The interactive wizard lets you choose **Custom Environment** and specify a container URI. After configuring:

```bash
agentcore deploy
agentcore invoke --harness mycontaineragent \
  --session-id "$(uuidgen)" \
  "Write a Node.js HTTP server and test it."
```

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
# Node.js preset (default)
python custom_container.py

# Go preset
python custom_container.py --language go

# Python preset
python custom_container.py --language python

# Any container image
python custom_container.py --container public.ecr.aws/docker/library/rust:slim

# Keep resources for inspection
python custom_container.py --skip-cleanup
```
