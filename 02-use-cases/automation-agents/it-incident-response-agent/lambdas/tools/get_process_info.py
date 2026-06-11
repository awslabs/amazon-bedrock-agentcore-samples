"""Gateway tool: get_process_info.

Looks up information about a hardware/software process or service from the
asset catalog. The agent uses this to understand what's affected.
"""

import logging
import os
import re

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

PROCESSES_TABLE = os.environ["PROCESSES_TABLE"]
_processes = boto3.resource("dynamodb").Table(PROCESSES_TABLE)

# Input validation constants
MAX_PROCESS_NAME_LENGTH = 256
PROCESS_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_\-\. /()]+$")


# Gateway Lambda targets return the tool result DIRECTLY to the model — no
# API-Gateway-style {statusCode, body} envelope. Errors are returned as a
# plain {"error": ...} object so the model can read them.
def _ok(body: dict) -> dict:
    return body


def _err(message: str) -> dict:
    return {"error": message}


def lambda_handler(event, context):
    """Look up process/service information from asset catalog."""
    # STEP: ENRICH — Understand what service/process is affected
    logger.info("get_process_info invoked")

    process_name = event.get("process_name")
    if not process_name:
        return _err("process_name is required")

    # Input validation: prevent excessively long or malformed process names
    if not isinstance(process_name, str):
        return _err("process_name must be a string")
    if len(process_name) > MAX_PROCESS_NAME_LENGTH:
        return _err(f"process_name exceeds maximum length of {MAX_PROCESS_NAME_LENGTH} characters")
    if not PROCESS_NAME_PATTERN.match(process_name):
        return _err("process_name contains invalid characters (allowed: alphanumeric, _, -, ., space, /, ())")

    item = _processes.get_item(Key={"process_name": process_name}).get("Item")
    if not item:
        return _err(f"process {process_name} not found in asset catalog")

    return _ok(
        {
            "process_name": process_name,
            "type": item.get("type"),
            "version": item.get("version"),
            "owner_team": item.get("owner_team"),
            "criticality": item.get("criticality"),
            "current_status": item.get("current_status"),
            "known_issues": item.get("known_issues", []),
        }
    )
