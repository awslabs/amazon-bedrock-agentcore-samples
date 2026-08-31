# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Eval script: get OAuth token → invoke agent via HTTPS → run AgentCore evaluations → gate on threshold.

NOTE: When an AgentCore Runtime is configured with JWT/OAuth inbound auth,
you CANNOT use the boto3 SDK to invoke it. You must make a direct HTTPS request
with a Bearer token. The evaluation API itself is IAM-authenticated (boto3 works fine).
"""

import contextlib
import io
import json
import os
import sys
import time
import uuid
import urllib.parse

import boto3
import requests as http_requests
from bedrock_agentcore_starter_toolkit import Evaluation


def _oauth_credentials() -> tuple[str, str]:
    """Resolve the M2M client_id/client_secret.

    Prefers reading directly from Secrets Manager (M2M_SECRET_ID) so the secret never
    passes through CI step outputs, environment files, or job logs. Falls back to
    OAUTH_CLIENT_ID/OAUTH_CLIENT_SECRET for local runs.
    """
    secret_id = os.environ.get("M2M_SECRET_ID")
    if secret_id:
        region = os.environ.get("AWS_REGION", "ap-southeast-2")
        payload = boto3.client("secretsmanager", region_name=region).get_secret_value(SecretId=secret_id)
        data = json.loads(payload["SecretString"])
        return data["client_id"], data["client_secret"]
    return os.environ["OAUTH_CLIENT_ID"], os.environ["OAUTH_CLIENT_SECRET"]


def get_token() -> str:
    """Client-credentials grant — works for both Cognito and Entra ID."""
    client_id, client_secret = _oauth_credentials()
    resp = http_requests.post(
        os.environ["TOKEN_ENDPOINT"],
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": os.environ.get("OAUTH_SCOPE", ""),
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def invoke_agent(agent_arn: str, session_id: str, prompt: str, region: str, token: str):
    """Invoke AgentCore Runtime via HTTPS with Bearer token (SDK doesn't support OAuth invocations)."""

    escaped_arn = urllib.parse.quote(agent_arn, safe="")
    url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_arn}/invocations?qualifier=DEFAULT"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
    }
    payload = json.dumps({"prompt": prompt})

    # Retry on 424 (MCP server dependency not yet available)
    # timeout is generous: agent invocations run a full LLM turn plus MCP tool calls.
    max_retries = 10
    for attempt in range(max_retries):
        resp = http_requests.post(url, headers=headers, data=payload, timeout=300)
        if resp.status_code != 424 or attempt == max_retries - 1:
            if not resp.ok:
                print(f"HTTP {resp.status_code}: {resp.text}")
            resp.raise_for_status()
            break
        print(f"424 Failed Dependency — retrying ({attempt + 1}/{max_retries})... Response: {resp.text}")
        time.sleep(30)

    body = resp.json()
    print(f"Q: {prompt}\nA: {body}\n")
    return body


def wait_for_runtime(agent_id: str, region: str, max_wait: int = 600):
    """Wait for runtime to be READY before invoking."""

    client = boto3.client("bedrock-agentcore-control", region_name=region)
    elapsed = 0
    interval = 10

    print(f"Waiting for runtime {agent_id} to be READY...")
    while elapsed < max_wait:
        try:
            resp = client.get_agent_runtime(agentRuntimeId=agent_id)
            status = resp["status"]
            print(f"Runtime status: {status} ({elapsed}s / {max_wait}s)")

            if status == "READY":
                print("✅ Runtime is READY")
                return
            elif status in ("CREATE_FAILED", "UPDATE_FAILED"):
                raise RuntimeError(f"Runtime failed: {status}")
        except Exception as e:
            print(f"Error checking status: {e}")

        time.sleep(interval)
        elapsed += interval

    raise TimeoutError(f"Runtime not ready after {max_wait}s")


def main():
    region = os.environ.get("AWS_REGION", "ap-southeast-2")
    agent_arn = os.environ["AGENT_RUNTIME_ARN"]
    agent_id = os.environ["AGENT_RUNTIME_ID"]
    threshold = float(os.environ.get("EVAL_THRESHOLD", "0.8"))

    wait_for_runtime(agent_id, region)
    token = get_token()

    # Load test prompts from dataset file
    dataset_path = os.environ.get("EVAL_DATASET", "eval_dataset.json")
    with open(dataset_path) as f:
        dataset = json.load(f)

    session_id = str(uuid.uuid4())
    for item in dataset:
        invoke_agent(agent_arn, session_id, item["prompt"], region, token)

    # Retry evaluations until traces are found (up to 10 min)
    evaluators = [
        "Builtin.GoalSuccessRate",
        "Builtin.Correctness",
        "Builtin.ToolSelectionAccuracy",
        "Builtin.ToolParameterAccuracy",
    ]
    max_wait = 600
    interval = 30
    elapsed = 0
    results = None

    print("Waiting for traces to propagate...")
    time.sleep(60)
    elapsed = 60

    while elapsed <= max_wait:
        # Suppress noisy SDK output during retries
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                results = Evaluation(region=region).run(
                    agent_id=agent_id,
                    session_id=session_id,
                    evaluators=evaluators,
                    output="evals_results/ci_output.json",
                )
        except Exception as e:
            elapsed += interval
            print(f"No traces yet... retrying ({elapsed}s / {max_wait}s) — {e}")
            time.sleep(interval)
            continue
        all_have_results = all(
            any(r.value is not None for r in results.results if r.evaluator_name == e) for e in evaluators
        )
        if all_have_results:
            break
        found = [e for e in evaluators if any(r.value is not None for r in results.results if r.evaluator_name == e)]
        missing = [e for e in evaluators if e not in found]
        if not missing:
            break
        elapsed += interval
        print(f"Waiting for traces... ({elapsed}s / {max_wait}s) — missing: {', '.join(missing)}")
        time.sleep(interval)

    failed = False
    has_results = False
    # Aggregate: keep best score per evaluator (multiple spans may return results)
    scores = {}
    for r in results.results:
        if r.value is None:
            continue
        if r.evaluator_name not in scores or r.value > scores[r.evaluator_name][0]:
            scores[r.evaluator_name] = (r.value, r.label)

    print(f"\n{'─' * 50}")
    print(f"{'Evaluator':<35} {'Score':>6}  Result")
    print(f"{'─' * 50}")
    for name in evaluators:
        if name in scores:
            has_results = True
            val, label = scores[name]
            icon = "✅" if val >= threshold else "❌"
            print(f"{icon} {name:<33} {val:>5.1f}  {label}")
            if val < threshold:
                failed = True
        else:
            print(f"⚠️  {name:<33}     -  no data")
    print(f"{'─' * 50}")

    if not has_results:
        print("\n❌ FAILED: no traces found after 10 minutes")
        sys.exit(1)
    if failed:
        print(f"\n❌ FAILED: metrics below {threshold}")
        sys.exit(1)
    print(f"\n✅ All evaluations PASSED (threshold: {threshold})")


if __name__ == "__main__":
    main()
