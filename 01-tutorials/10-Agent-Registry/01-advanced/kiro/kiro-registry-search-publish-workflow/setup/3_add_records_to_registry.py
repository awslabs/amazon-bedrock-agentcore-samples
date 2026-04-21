#!/usr/bin/env python3
"""
Step 3: Register agents in the AgentCore Registry.

All agents are registered as CUSTOM descriptorType with inline metadata.
Runtime ARNs are auto-discovered from AgentCore Runtime if not passed via --arn.

Run:  python3 3_add_records_to_registry.py market_research_agent [--arn <runtime-arn>]
"""

import argparse
import json
import logging
import time

import boto3
import requests as http_requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from setup import get_cp_client, REGION

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("register")


def load_metadata(agent_name: str) -> dict:
    mod = __import__(f"seed_agents.{agent_name}", fromlist=["METADATA"])
    return mod.METADATA


def discover_runtime_arn(agent_name: str) -> str:
    """Auto-discover runtime ARN by listing agents on AgentCore Runtime control plane (paginated)."""
    ac_cp = boto3.client("bedrock-agentcore-control", region_name=REGION)
    try:
        resp = ac_cp.list_agent_runtimes()
        while True:
            for agent in resp.get("agentRuntimes", []):
                if agent["agentRuntimeName"] == agent_name:
                    logger.info("Auto-discovered ARN for %s: %s", agent_name, agent["agentRuntimeArn"])
                    return agent["agentRuntimeArn"]
            nt = resp.get("nextToken")
            if not nt:
                break
            resp = ac_cp.list_agent_runtimes(nextToken=nt)
    except Exception as e:
        logger.warning("Could not auto-discover ARN for %s: %s", agent_name, e)
    return None


def _create_record_raw(registry_id, body: dict) -> str:
    """Create a registry record via signed HTTP."""
    cp_client = get_cp_client()
    url = f"{cp_client.meta.endpoint_url}/registries/{registry_id}/records"
    data = json.dumps(body)
    req = AWSRequest(method="POST", url=url, data=data, headers={"Content-Type": "application/json"})
    creds = boto3.Session(region_name=REGION).get_credentials().get_frozen_credentials()
    SigV4Auth(creds, "bedrock-agentcore", REGION).add_auth(req)
    resp = http_requests.post(url, headers=dict(req.headers), data=data)
    resp.raise_for_status()
    return resp.json()["recordArn"].split("/")[-1]


def wait_for_draft(cp, registry_id, record_id, max_wait=30):
    for _ in range(max_wait // 3):
        time.sleep(3)
        rec = cp.get_registry_record(registryId=registry_id, recordId=record_id)
        if rec["status"] not in ("CREATING", "UPDATING"):
            return rec["status"]
    return "CREATING"


def approve(cp, registry_id, record_id):
    cp.submit_registry_record_for_approval(registryId=registry_id, recordId=record_id)
    creds = boto3.Session(region_name=REGION).get_credentials().get_frozen_credentials()
    url = f"{cp.meta.endpoint_url}/registries/{registry_id}/records/{record_id}/status"
    body = json.dumps({"status": "APPROVED", "statusReason": "Approved"})
    req = AWSRequest(method="PATCH", url=url, data=body, headers={"Content-Type": "application/json"})
    SigV4Auth(creds, "bedrock-agentcore", REGION).add_auth(req)
    http_requests.request(method="PATCH", url=url, headers=dict(req.headers), data=body).raise_for_status()


def register_agent(cp, registry_id, meta: dict, runtime_arn: str = None) -> str:
    """Create a CUSTOM registry record for an agent and approve it."""
    inline = {
        "name": meta["name"],
        "description": meta["description"],
        "version": meta.get("version", "1.0.0"),
        "protocol": "HTTP",
        "team": meta.get("team", ""),
        "capabilities": meta.get("capabilities", []),
        "tools": meta["tools"],
    }
    if runtime_arn:
        inline["runtimeArn"] = runtime_arn

    record_id = _create_record_raw(registry_id, {
        "name": meta["name"],
        "description": meta["description"],
        "descriptorType": "CUSTOM",
        "recordVersion": meta.get("version", "1.0"),
        "descriptors": {"custom": {"inlineContent": json.dumps(inline)}},
    })
    logger.info("Created: %s -> %s", meta["name"], record_id)

    status = wait_for_draft(cp, registry_id, record_id)
    logger.info("Status: %s", status)
    approve(cp, registry_id, record_id)
    logger.info("Approved: %s", meta["name"])
    return record_id


def main():
    parser = argparse.ArgumentParser(description="Register agent(s) in AgentCore Registry")
    parser.add_argument("agent", help="Agent module name")
    parser.add_argument("--arn", help="Runtime ARN (auto-discovered if omitted)")
    parser.add_argument("--registry-id", help="Override REGISTRY_ID from .env")
    args = parser.parse_args()

    registry_id = args.registry_id
    if not registry_id:
        logger.error("No REGISTRY_ID set. Run 1_create_registry.py first.")
        return

    meta = load_metadata(args.agent)
    cp = get_cp_client()

    runtime_arn = args.arn or discover_runtime_arn(meta["name"])

    logger.info("Registering: %s — Team: %s — ARN: %s", meta["name"], meta.get("team", "unknown"), runtime_arn or "NONE")
    record_id = register_agent(cp, registry_id, meta, runtime_arn=runtime_arn)
    logger.info("Done: %s | Record: %s", meta["name"], record_id)


if __name__ == "__main__":
    main()
