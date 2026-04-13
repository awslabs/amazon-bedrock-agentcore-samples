import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'setup'))

import boto3
import json
import logging
import uuid
import time
import requests
from setup import REGION, get_cp_client, get_dp_client, get_oauth_token

ACCOUNT_ID = boto3.client('sts', region_name=REGION).get_caller_identity()['Account']

# Clients
cp_client = get_cp_client()
dp_client = get_dp_client()
ac_client = boto3.client("bedrock-agentcore", region_name=REGION)
DP_ENDPOINT = dp_client.meta.endpoint_url


def search_registry(query, registry_id=None, max_results=5):
    """Search the Auth0 OAuth-protected registry."""
    rid = registry_id
    audience = f"{DP_ENDPOINT}/registry/{rid}/mcp"
    token = get_oauth_token(audience=audience)
    resp = requests.post(
        f"{DP_ENDPOINT}/registry-records/search",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "searchQuery": query,
            "registryIds": [f"arn:aws:bedrock-agentcore:{REGION}:{ACCOUNT_ID}:registry/{rid}"],
            "maxResults": max_results,
        },
    )
    return resp.json()


def get_inline_metadata(record):
    """Extract inline metadata from a registry record's descriptors."""
    descs = record.get('descriptors', {})
    dtype = record.get('descriptorType', '')
    raw = None
    if dtype == 'CUSTOM':
        raw = (descs.get('custom') or {}).get('inlineContent')
    elif dtype == 'MCP':
        raw = (descs.get('mcp', {}).get('server') or {}).get('inlineContent')
    elif dtype == 'A2A':
        raw = (descs.get('a2a') or {}).get('inlineContent')
    elif dtype == 'AGENT_SKILLS':
        raw = (descs.get('agentSkills') or {}).get('inlineContent')
    if raw:
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            return raw
    return None


def print_results(query, results):
    """Pretty-print search results with inline metadata."""
    print(f"Search: '{query}'")
    for r in results.get('registryRecords', []):
        print(f"  → {r['name']} ({r['descriptorType']}) — {r.get('description', '')[:80]}")
        meta = get_inline_metadata(r)
        if meta:
            if isinstance(meta, dict):
                for k, v in meta.items():
                    val = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    if len(val) > 120:
                        val = val[:120] + '...'
                    print(f"    {k}: {val}")
            else:
                print(f"    metadata: {str(meta)[:200]}")
        print()


def invoke_http_agent(runtime_arn, prompt):
    """Invoke an HTTP agent on AgentCore Runtime (IAM auth)."""
    resp = ac_client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=str(uuid.uuid4()) + "-notebook-session-pad",
        payload=json.dumps({"prompt": prompt}),
        qualifier="DEFAULT",
    )
    return json.loads(resp["response"].read().decode("utf-8"))


def resolve_agents_from_registry(queries, registry_id):
    """Search registry and extract runtime ARNs / MCP endpoints from descriptors."""
    agents = {}
    for q in queries:
        for r in search_registry(q, registry_id).get("registryRecords", []):
            name = r["name"]
            if name in agents:
                continue
            dtype = r["descriptorType"]
            descs = r.get("descriptors", {})
            if dtype == "CUSTOM":
                raw = (descs.get("custom") or {}).get("inlineContent")
                if raw:
                    desc = json.loads(raw) if isinstance(raw, str) else raw
                    agents[name] = {"type": "HTTP", "metadata": desc}
                    if desc.get("runtimeArn"):
                        agents[name]["runtimeArn"] = desc["runtimeArn"]
            elif dtype == "MCP":
                mcp_desc = descs.get("mcp", {})
                server_raw = (mcp_desc.get("server") or {}).get("inlineContent")
                tools_raw = (mcp_desc.get("tools") or {}).get("inlineContent")
                server_meta = json.loads(server_raw) if server_raw and isinstance(server_raw, str) else server_raw
                tools_meta = json.loads(tools_raw) if tools_raw and isinstance(tools_raw, str) else tools_raw
                info = {"type": "MCP"}
                if server_meta:
                    info["server"] = server_meta
                    url = None
                    if isinstance(server_meta, str):
                        url = server_meta
                    elif isinstance(server_meta, dict):
                        remotes = server_meta.get("remotes", [])
                        if remotes:
                            url = remotes[0].get("url")
                        if not url:
                            url = server_meta.get("url") or server_meta.get("endpoint")
                    if url:
                        info["mcpUrl"] = url
                if tools_meta:
                    info["tools"] = tools_meta
                agents[name] = info
    return agents


def cleanup(registry_id=None):
    """Delete all records, then the registry. Also cleans up runtimes and gateways found in descriptors."""
    logger = logging.getLogger("poc")
    registry_id = registry_id
    cp = get_cp_client()
    ac = boto3.client("bedrock-agentcore-control", region_name=REGION)

    runtime_arns = set()

    # 1. List records, extract runtime ARNs, delete records
    try:
        records = cp.list_registry_records(registryId=registry_id).get('registryRecords', [])
        for rec in records:
            rid = rec['recordId']
            try:
                detail = cp.get_registry_record(registryId=registry_id, recordId=rid)
                meta = get_inline_metadata(detail)
                if isinstance(meta, dict) and meta.get('runtimeArn'):
                    runtime_arns.add(meta['runtimeArn'])
            except Exception:
                pass
            cp.delete_registry_record(registryId=registry_id, recordId=rid)
            logger.info('Deleted record %s (%s)', rec.get('name', rid), rid)

        time.sleep(5)
        cp.delete_registry(registryId=registry_id)
        logger.info('Registry %s deleted', registry_id)
    except Exception as e:
        logger.warning('Registry cleanup: %s', e)

    # 2. Delete agent runtimes discovered from records
    for arn in runtime_arns:
        try:
            rt_id = arn.split('/')[-1]
            ac.delete_agent_runtime(agentRuntimeId=rt_id)
            logger.info('Deleted runtime %s', rt_id)
        except Exception as e:
            logger.warning('Runtime %s: %s', arn, e)

    logger.info('Cleanup complete')

