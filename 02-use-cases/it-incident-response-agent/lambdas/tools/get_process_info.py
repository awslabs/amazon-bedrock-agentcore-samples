"""Gateway tool: get_process_info.

Looks up information about a hardware/software process or service from the
asset catalog. The agent uses this to understand what's affected.
"""

import json
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PROCESSES_TABLE = os.environ["PROCESSES_TABLE"]
_processes = boto3.resource("dynamodb").Table(PROCESSES_TABLE)


def _ok(body):
    return {"statusCode": 200, "body": json.dumps(body, default=str)}


def _err(message, status=400):
    return {"statusCode": status, "body": json.dumps({"error": message})}


def lambda_handler(event, context):
    logger.info("get_process_info invoked, event=%s", event)

    process_name = event.get("process_name")
    if not process_name:
        return _err("process_name is required")

    item = _processes.get_item(Key={"process_name": process_name}).get("Item")
    if not item:
        return _err(f"process {process_name} not found in asset catalog", status=404)

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
