# Convert your MCP tools to respond with TOON instead of JSON

[Token-Oriented Object Notation](https://github.com/toon-format/toon) (TOON) is a compact, human-readable encoding of the JSON data model that minimizes tokens and makes structure easy for models to follow. It's intended for LLM input as a drop-in, lossless representation of your existing JSON.

TOON reaches 74% accuracy (vs JSON's 70%) while using ~40% fewer tokens in mixed-structure benchmarks across 4 models.

![toon](./images/toon.gif)

![inspector](./images/inspector.gif)

## Prerequisites

- [AWS CLI](https://aws.amazon.com/cli/) configured with appropriate credentials
- [AWS CDK](https://aws.amazon.com/cdk/) v2 installed (`npm install -g aws-cdk`)
- [uv](https://github.com/astral-sh/uv) for Python package management
- Python 3.11+
- Node.js 18+ (for interceptor Lambda)
- [Docker](https://www.docker.com/) intalled and running

## Deploy

1. Create virtual environment

   ```bash
   uv sync
   source .venv/bin/activate
   ```

2. Bootstrap CDK (first time only)

   ```bash
   cdk bootstrap
   ```

3. Deploy infrastructure

   ```bash
   # Deploy with dev environment (default)
   cdk deploy --all

   # Deploy with prod environment
   cdk deploy --all -c environment=prod

   # Deploy with test environment
   cdk deploy --all -c environment=test
   ```

## Scripts

### List and Invoke MCP Gateway Tools

```bash
# List available tools
uv run scripts/mcp_toon.py -e dev

# Invoke batch_get_customers
uv run scripts/mcp_toon.py -e dev -i customers-crud___batch_get_customers

# Invoke query_by_region with arguments
uv run scripts/mcp_toon.py -e dev -i customers-crud___query_by_region -a '{"region": "Northeast"}'

# Invoke query_by_tier with arguments
uv run scripts/mcp_toon.py -e dev -i customers-crud___query_by_tier -a '{"subscription_tier": "Premium", "limit": 10}'

# Invoke get_customer
uv run scripts/mcp_toon.py -e dev -i customers-crud___get_customer -a '{"customer_id": "abc123"}'

# Invoke scan_customers with pagination
uv run scripts/mcp_toon.py -e dev -i customers-crud___scan_customers -a '{"limit": 10}'
```

### Get Bearer Token

```bash
# Get token with verbose output
uv run scripts/get_token.py -e dev

# Get token only (for scripting)
uv run scripts/get_token.py -e dev -q
```

### Script Options

**mcp_toon.py**

| Option | Short | Description |
|--------|-------|-------------|
| `--environment` | `-e` | Environment (dev, test, prod). Default: dev |
| `--gateway-url` | `-g` | Gateway URL (fetched from SSM if not provided) |
| `--invoke` | `-i` | Tool name to invoke |
| `--args` | `-a` | JSON arguments for the tool |

**get_token.py**

| Option | Short | Description |
|--------|-------|-------------|
| `--environment` | `-e` | Environment (dev, test, prod). Default: dev |
| `--quiet` | `-q` | Only print the token (no extra output) |

## Cleanup

```bash
# Destroy all stacks
cdk destroy --all

# Destroy specific stack
cdk destroy GatewayStack
```
