#!/usr/bin/env python3
"""
Run a system-prompt recommendation over the 60 v2 sessions,
targeting GoalSuccessRate improvement.
"""

import boto3
import json
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REGION = "us-west-2"
RUNTIME_ID = "market_trends_agent_v2-HJRTuc597J"
AGENT_NAME = "market_trends_agent_v2"
LOG_GROUP = f"/aws/bedrock-agentcore/runtimes/{RUNTIME_ID}-DEFAULT"
SERVICE_NAME = f"{AGENT_NAME}.DEFAULT"
SPANS_LOG_GROUP = "aws/spans"

TERMINAL_REC = {"COMPLETED", "FAILED"}

sts = boto3.client("sts", region_name=REGION)
ACCOUNT_ID = sts.get_caller_identity()["Account"]

LOG_GROUP_ARN = f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:log-group:{LOG_GROUP}"
SPANS_LOG_ARN = f"arn:aws:logs:{REGION}:{ACCOUNT_ID}:log-group:{SPANS_LOG_GROUP}"

dp = boto3.client("bedrock-agentcore", region_name=REGION)

CURRENT_SYSTEM_PROMPT = """\
You are a financial market intelligence analyst working with investment brokers.

CAPABILITIES:
- Provide real-time stock prices and market data via get_stock_data
- Search financial news from Bloomberg, Reuters, CNBC, WSJ, and FT via search_news
- Maintain persistent broker profiles using AgentCore Memory tools
- Deliver personalized market analysis tailored to each broker's preferences

BROKER IDENTITY:
- When a user introduces themselves, IMMEDIATELY call identify_broker(user_message)
- After identification, call get_broker_financial_profile to retrieve stored preferences
- Use update_broker_financial_interests to store new preferences or profile updates
- Always pass the identified actor_id to all memory operations

MARKET ANALYSIS WORKFLOW:
1. Identify the broker (if identity markers present in the message)
2. Retrieve their stored profile to personalize the response
3. Fetch live stock data and sector information relevant to their query
4. Search for recent news aligned to their interests
5. Synthesize a professional, data-driven response

Always use tools to retrieve live data. Do not fabricate prices, news, or profile details.\
"""


def poll(rec_id: str, interval: int = 30, timeout: int = 900) -> dict:
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        result = dp.get_recommendation(recommendationId=rec_id)
        status = result.get("status", "UNKNOWN")
        attempt += 1
        logger.info(f"  [{attempt:3d}] status={status}")
        if status in TERMINAL_REC:
            return result
        time.sleep(interval)
    raise TimeoutError(f"Timed out after {timeout}s")


def main():
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(hours=2)  # sessions ran ~25 min ago, cover last 2h

    rec_name = f"mt_v2_sp_rec_{uuid.uuid4().hex[:6]}"
    logger.info(f"Starting system-prompt recommendation: {rec_name}")
    logger.info(f"Trace window: {start_dt.strftime('%H:%M')} → {now.strftime('%H:%M')} UTC")
    logger.info(f"Log groups: {SPANS_LOG_GROUP}, {LOG_GROUP}")

    rec_resp = dp.start_recommendation(
        name=rec_name,
        type="SYSTEM_PROMPT_RECOMMENDATION",
        recommendationConfig={
            "systemPromptRecommendationConfig": {
                "systemPrompt": {"text": CURRENT_SYSTEM_PROMPT},
                "agentTraces": {
                    "cloudwatchLogs": {
                        "logGroupArns": [SPANS_LOG_ARN, LOG_GROUP_ARN],
                        "serviceNames": [SERVICE_NAME],
                        "startTime": start_dt,
                        "endTime": now,
                    }
                },
                "evaluationConfig": {
                    "evaluators": [{"evaluatorArn": ("arn:aws:bedrock-agentcore:::evaluator/Builtin.GoalSuccessRate")}]
                },
            }
        },
        clientToken=str(uuid.uuid4()),
    )

    rec_id = rec_resp["recommendationId"]
    logger.info(f"Recommendation ID: {rec_id}")
    logger.info("Polling for completion (typically 2–7 minutes)...")

    result = poll(rec_id)
    status = result.get("status")
    logger.info(f"Final status: {status}")

    rec_data = result.get("recommendationResult", {})
    sp_result = rec_data.get("systemPromptRecommendationResult", {})

    if status == "FAILED":
        reason = result.get("failureReason", "unknown")
        logger.error(f"Recommendation failed: {reason}")
        out = {"rec_name": rec_name, "rec_id": rec_id, "status": status, "failureReason": reason}
    else:
        raw = sp_result.get("recommendedSystemPrompt")
        if isinstance(raw, dict):
            raw = raw.get("text", str(raw))
        explanation = sp_result.get("explanation", "")

        print(f"\n{'=' * 70}")
        print(f"Recommendation: {rec_name}")
        print(f"ID:             {rec_id}")
        print(f"Status:         {status}")
        print(f"{'=' * 70}")
        print("\n--- RECOMMENDED SYSTEM PROMPT ---\n")
        print(raw or "(empty)")
        if explanation:
            print(f"\n--- EXPLANATION ---\n{explanation}")
        print(f"\n{'=' * 70}\n")

        out = {
            "rec_name": rec_name,
            "rec_id": rec_id,
            "status": status,
            "recommended_system_prompt": raw,
            "explanation": explanation,
        }

    with open("recommendation_v2_result.json", "w") as f:
        json.dump(out, f, indent=2)
    logger.info("Results saved to recommendation_v2_result.json")


if __name__ == "__main__":
    main()
