"""Shared configuration for the Databricks Genie via AgentCore Gateway sample.

All values come from environment variables so no credentials are stored in the
repo. The four Databricks values are required; see README.md for how to obtain
each one.

    export DATABRICKS_HOST="https://dbc-xxxxxxxx-xxxx.cloud.databricks.com"
    export DATABRICKS_CLIENT_ID="<service principal application ID>"
    export DATABRICKS_CLIENT_SECRET="<OAuth M2M secret>"
    export GENIE_SPACE_ID="<Genie space ID>"
    export AWS_REGION="us-east-1"
"""

import os

# --- Databricks -------------------------------------------------------------
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
DATABRICKS_CLIENT_ID = os.environ.get("DATABRICKS_CLIENT_ID", "")
DATABRICKS_CLIENT_SECRET = os.environ.get("DATABRICKS_CLIENT_SECRET", "")
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")

# --- AWS --------------------------------------------------------------------
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

# --- Resource names ---------------------------------------------------------
GATEWAY_NAME = "DatabricksGenieGateway"
TARGET_NAME = "DatabricksGenie"
CREDENTIAL_PROVIDER_NAME = "databricks-genie-oauth"
IAM_POLICY_NAME = "DatabricksGenieOAuthAccess"

# --- Local state ------------------------------------------------------------
# Written by deploy.py, read by invoke.py / cleanup.py and by the deployed agent.
STATE_FILE = os.path.join(os.path.dirname(__file__), "gateway_config.json")

SYSTEM_PROMPT = (
    "You answer business questions by calling the Databricks Genie tool exposed "
    "through the gateway. Genie returns governed, lakehouse-native SQL answers. "
    "Be concise and present results in a readable format."
)


def require_databricks_config() -> None:
    """Fail fast with an actionable message if any Databricks value is missing."""
    missing = [
        name
        for name, value in (
            ("DATABRICKS_HOST", DATABRICKS_HOST),
            ("DATABRICKS_CLIENT_ID", DATABRICKS_CLIENT_ID),
            ("DATABRICKS_CLIENT_SECRET", DATABRICKS_CLIENT_SECRET),
            ("GENIE_SPACE_ID", GENIE_SPACE_ID),
        )
        if not value
    ]
    if missing:
        raise SystemExit(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + "\nSee the Configuration section of README.md."
        )


def genie_mcp_url() -> str:
    """Databricks-managed Genie MCP endpoint for the configured space."""
    return f"{DATABRICKS_HOST}/api/2.0/mcp/genie/{GENIE_SPACE_ID}"
