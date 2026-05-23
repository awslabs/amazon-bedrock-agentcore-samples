#!/usr/bin/env python3
"""
Run a batch evaluation over the 60 sessions from session_results_60.json
against the market_trends_agent_v2 runtime.
"""

import boto3
import json
import time
import uuid
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REGION = "us-west-2"
RUNTIME_ID = "market_trends_agent_v2-HJRTuc597J"
AGENT_NAME = "market_trends_agent_v2"
LOG_GROUP = f"/aws/bedrock-agentcore/runtimes/{RUNTIME_ID}-DEFAULT"
SERVICE_NAME = f"{AGENT_NAME}.DEFAULT"
SPANS_LOG_GROUP = "aws/spans"
RESULTS_LOG_GROUP = "/aws/bedrock-agentcore/evaluations/batch-evaluations/results/default"

TERMINAL_EVAL = {"COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"}

dp = boto3.client("bedrock-agentcore", region_name=REGION)
logs_client = boto3.client("logs", region_name=REGION)


def load_session_ids(path="session_results_60.json") -> list[str]:
    with open(path) as f:
        results = json.load(f)
    ids = [r["runtime_session_id"] for r in results]
    logger.info(f"Loaded {len(ids)} session IDs from {path}")
    return ids


def poll(eval_id: str, interval: int = 30, timeout: int = 1200) -> dict:
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        result = dp.get_batch_evaluation(batchEvaluationId=eval_id)
        status = result.get("status", "UNKNOWN")
        attempt += 1
        logger.info(f"  [{attempt:3d}] status={status}")
        if status in TERMINAL_EVAL:
            return result
        time.sleep(interval)
    raise TimeoutError(f"Timed out after {timeout}s")


def fetch_scores_from_cw(batch_eval_id: str) -> dict:
    """Fall back to CloudWatch when API evaluatorSummaries is empty."""
    log_stream = f"run-{batch_eval_id}"
    try:
        events = logs_client.get_log_events(
            logGroupName=RESULTS_LOG_GROUP,
            logStreamName=log_stream,
            startFromHead=True,
        ).get("events", [])
        by_eval: dict = defaultdict(list)
        for e in events:
            try:
                rec = json.loads(e["message"])
                attrs = rec.get("attributes") or rec
                eid = attrs.get("gen_ai.evaluation.name")
                score = attrs.get("gen_ai.evaluation.score.value")
                if eid and score is not None and rec.get("name") == "gen_ai.evaluation.result":
                    by_eval[eid].append(float(score))
            except Exception:
                pass
        return {eid: sum(v) / len(v) for eid, v in by_eval.items() if v}
    except Exception as e:
        logger.warning(f"CloudWatch score fetch failed: {e}")
        return {}


def main():
    session_ids = load_session_ids()

    eval_name = f"mt_v2_eval_{uuid.uuid4().hex[:6]}"
    logger.info(f"Starting batch evaluation: {eval_name}")
    logger.info(f"Sessions: {len(session_ids)}")
    logger.info(f"Log group: {LOG_GROUP}")

    eval_resp = dp.start_batch_evaluation(
        batchEvaluationName=eval_name,
        evaluators=[
            {"evaluatorId": "Builtin.GoalSuccessRate"},
            {"evaluatorId": "Builtin.Helpfulness"},
            {"evaluatorId": "Builtin.Correctness"},
            {"evaluatorId": "Builtin.ToolSelectionAccuracy"},
        ],
        dataSourceConfig={
            "cloudWatchLogs": {
                "serviceNames": [SERVICE_NAME],
                "logGroupNames": [SPANS_LOG_GROUP, LOG_GROUP],
                "filterConfig": {"sessionIds": session_ids},
            }
        },
        clientToken=str(uuid.uuid4()),
    )

    eval_id = eval_resp["batchEvaluationId"]
    logger.info(f"Batch evaluation started: {eval_id}")
    logger.info("Polling for completion (typically 5–10 min for 60 sessions)...")

    result = poll(eval_id)
    status = result.get("status")
    logger.info(f"Final status: {status}")

    # Try API response first, fall back to CloudWatch
    scores: dict = {}
    er = result.get("evaluationResults", {})
    for s in er.get("evaluatorSummaries", []):
        avg = s.get("statistics", {}).get("averageScore")
        if avg is not None:
            scores[s["evaluatorId"]] = avg

    if not scores:
        logger.info("Reading scores from CloudWatch...")
        scores = fetch_scores_from_cw(eval_id)

    print(f"\n{'=' * 55}")
    print(f"Batch Evaluation: {eval_name}")
    print(f"ID:               {eval_id}")
    print(f"Status:           {status}")
    print(f"Sessions:         {len(session_ids)}")
    print(f"{'=' * 55}")
    print(f"{'Evaluator':<45} {'Score':>8}")
    print("-" * 55)
    for eid, score in sorted(scores.items()):
        print(f"{eid:<45} {score:>8.4f}")
    print(f"{'=' * 55}\n")

    # Save state
    out = {"eval_name": eval_name, "eval_id": eval_id, "status": status, "scores": scores}
    with open("batch_eval_v2_result.json", "w") as f:
        json.dump(out, f, indent=2)
    logger.info("Results saved to batch_eval_v2_result.json")


if __name__ == "__main__":
    main()
