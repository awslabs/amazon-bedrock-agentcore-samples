# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""AgentCore Evaluation Pipeline - walkthrough.

A CI/CD-style evaluation pipeline for an Amazon Bedrock AgentCore agent, run
against an already-deployed stack. It:

  1. Reads stack outputs and fetches the M2M client secret from Secrets Manager.
  2. Gets an M2M token via the client_credentials grant (machine-to-machine, no
     user identity). The token carries the tool scopes the agent needs.
  3. Invokes the agent with a set of test prompts under a single session ID so
     the OTel traces are grouped for evaluation.
  4. Scores the session with built-in evaluators via the
     bedrock-agentcore-starter-toolkit.
  5. Applies a quality gate: exits non-zero if any score is below threshold.

This is the interactive walkthrough companion to `agentcore_eval.py`, which is
the leaner script the CI workflow runs.

Usage:
    # Deploy the stack first (see README "Deployment"), then:
    python evaluation_pipeline.py [--outputs ../outputs.json] [--threshold 0.8]

Prerequisites:
    - The CDK stack is deployed and outputs.json has been written
      (cdk deploy --outputs-file outputs.json).
    - AWS credentials configured with access to the deployed account/region.
    - pip install boto3 requests bedrock-agentcore-starter-toolkit

Exit status:
    0 if every evaluator meets the threshold, 1 otherwise.
"""

import argparse
import json
import sys
import time
import urllib.parse
import uuid

import boto3
import requests
from bedrock_agentcore_starter_toolkit import Evaluation

REGION = "ap-southeast-2"
STACK_NAME = "AgentCoreCICDStack-dev"
M2M_SECRET_ID = "agentcore/dev/m2m-client"

EVALUATORS = [
    "Builtin.GoalSuccessRate",
    "Builtin.Correctness",
    "Builtin.ToolSelectionAccuracy",
    "Builtin.ToolParameterAccuracy",
]

# Test prompts. The M2M token is granted mcp/finance and mcp/hr, so it reaches those tools.
PROMPTS = [
    "How much is 2+2?",  # calculator (built-in)
    "What is the current time in UTC?",  # get_current_datetime (MCP, public)
    "What is the stock price of AAPL?",  # get_stock_price (MCP, gated: FinanceUser role or mcp/finance scope)
    "How many employees are in engineering?",  # get_employee_count (MCP, gated: HRUser role or mcp/hr scope)
]

MAX_RETRIES = 6
WAIT_SECONDS = 30


def load_config(outputs_path: str) -> dict:
    """Read stack outputs and fetch the M2M client secret from Secrets Manager."""
    with open(outputs_path) as f:
        outputs = json.load(f)[STACK_NAME]

    sm = boto3.client("secretsmanager", region_name=REGION)
    secret = json.loads(sm.get_secret_value(SecretId=M2M_SECRET_ID)["SecretString"])

    return {
        "agent_runtime_arn": outputs["AgentRuntimeArn"],
        "agent_runtime_id": outputs["AgentRuntimeId"],
        "token_endpoint": outputs["TokenEndpoint"],
        "client_id": secret["client_id"],
        "client_secret": secret["client_secret"],
    }


def get_m2m_token(token_endpoint: str, client_id: str, client_secret: str) -> str:
    """Get an M2M token via the client_credentials grant.

    Per-domain tool scopes: the MCP AuthMiddleware grants a gated tool only to a
    caller holding its scope, so the eval dataset needs mcp/finance and mcp/hr.
    agentcore/invoke authorizes the agent call.
    """
    resp = requests.post(
        token_endpoint,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "mcp/invoke mcp/finance mcp/hr agentcore/invoke",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def invoke_agent(agent_runtime_arn: str, prompt: str, session_id: str, token: str) -> dict:
    """Invoke AgentCore Runtime via HTTPS with a Bearer token.

    OAuth-protected runtimes must be invoked via HTTPS with a Bearer token; the
    boto3 SDK does not support OAuth invocations.
    """
    escaped_arn = urllib.parse.quote(agent_runtime_arn, safe="")
    url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{escaped_arn}/invocations?qualifier=DEFAULT"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        },
        data=json.dumps({"prompt": prompt}),
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()


def run_evaluation(agent_runtime_id: str, session_id: str):
    """Score the session with built-in evaluators, retrying while traces propagate.

    Traces can take several minutes to propagate. Evaluation.run() may succeed
    while every score is still None, so retry until each evaluator returns a real
    value rather than breaking on the first non-exception response.
    """
    results = None
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"Attempt {attempt}/{MAX_RETRIES}: waiting {WAIT_SECONDS}s for trace propagation...")
        time.sleep(WAIT_SECONDS)
        try:
            results = Evaluation(region=REGION).run(
                agent_id=agent_runtime_id,
                session_id=session_id,
                evaluators=EVALUATORS,
                output="eval_output.json",
            )
        except RuntimeError as e:
            if "No spans found" in str(e) and attempt < MAX_RETRIES:
                print("  No spans yet, retrying...")
                continue
            raise

        missing = [
            e for e in EVALUATORS if not any(r.value is not None for r in results.results if r.evaluator_name == e)
        ]
        if not missing:
            break
        print(f"  Scores not ready for: {', '.join(missing)}")
    return results


def aggregate_scores(results) -> dict:
    """Keep the best score per evaluator (multiple spans may return results)."""
    scores = {}
    if results is None:
        return scores
    for r in results.results:
        if r.value is not None and (r.evaluator_name not in scores or r.value > scores[r.evaluator_name][0]):
            scores[r.evaluator_name] = (r.value, r.label)
    return scores


def print_scores(scores: dict, threshold: float) -> None:
    """Render the results table."""
    print(f"{'─' * 50}")
    print(f"{'Evaluator':<35} {'Score':>6}  Result")
    print(f"{'─' * 50}")
    for name in EVALUATORS:
        if name in scores:
            val, label = scores[name]
            icon = "✅" if val >= threshold else "❌"
            print(f"{icon} {name:<33} {val:>5.1f}  {label}")
        else:
            print(f"⚠️  {name:<33}     -  no data")
    print(f"{'─' * 50}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentCore evaluation pipeline walkthrough.")
    parser.add_argument("--outputs", default="../outputs.json", help="Path to the CDK outputs file.")
    parser.add_argument("--threshold", type=float, default=0.8, help="Quality gate threshold (default: 0.8).")
    args = parser.parse_args()

    config = load_config(args.outputs)
    print(f"Agent ARN: {config['agent_runtime_arn']}")
    print(f"Agent ID:  {config['agent_runtime_id']}")
    print(f"Token URL: {config['token_endpoint']}\n")

    token = get_m2m_token(config["token_endpoint"], config["client_id"], config["client_secret"])
    print(f"Token acquired (first 20 chars): {token[:20]}...\n")

    # A single session groups all traces for evaluation.
    session_id = str(uuid.uuid4())
    print(f"Session ID: {session_id}\n")
    for prompt in PROMPTS:
        print(f"Q: {prompt}")
        try:
            result = invoke_agent(config["agent_runtime_arn"], prompt, session_id, token)
            print(f"A: {result}\n")
        except Exception as e:
            print(f"Error: {e}\n")

    results = run_evaluation(config["agent_runtime_id"], session_id)
    scores = aggregate_scores(results)
    print_scores(scores, args.threshold)

    # Quality gate. An empty `scores` dict means no evaluator returned data;
    # without this guard a run that collected nothing would report success.
    if not scores:
        print("❌ FAILED: no evaluation results collected (no traces scored in time)")
        sys.exit(1)
    if any(val < args.threshold for val, _ in scores.values()):
        print(f"❌ FAILED: one or more metrics below {args.threshold}")
        sys.exit(1)
    print(f"✅ All evaluations PASSED (threshold: {args.threshold})")


if __name__ == "__main__":
    main()
