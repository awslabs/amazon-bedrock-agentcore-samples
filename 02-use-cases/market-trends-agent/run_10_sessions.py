#!/usr/bin/env python3
"""
Run 10 diverse sessions against the market_trends_agent_v2 runtime.
Each session covers a different user persona and market scenario.
"""

import boto3
import json
import os
import time
import uuid
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

AGENT_ARN = os.environ.get(
    "AGENT_ARN",
    open(".agent_arn").read().strip() if os.path.exists(".agent_arn") else "",
)
REGION = os.environ.get("AWS_REGION", "us-west-2")

SESSIONS = [
    {
        "id": "S01",
        "desc": "Tech sector deep-dive – growth broker",
        "messages": [
            "Hi, I'm Sarah Chen from Morgan Stanley. I specialize in growth-oriented tech investing for high-net-worth clients with aggressive risk tolerance. Can you pull the latest stock data for NVDA and MSFT and give me a trend summary?",
        ],
    },
    {
        "id": "S02",
        "desc": "Healthcare & biotech sector inquiry",
        "messages": [
            "I'm James Patel, a portfolio manager at Fidelity focused on healthcare and biotech. I have a moderate risk appetite. What are the latest market trends for healthcare stocks like JNJ and PFE? Also search for recent news on biotech drug approvals.",
        ],
    },
    {
        "id": "S03",
        "desc": "Renewable energy sector analysis",
        "messages": [
            "Hello, I'm Linda Torres from BlackRock's ESG desk. My clients are very interested in clean energy. Can you get me current data on ENPH and FSLR, and search for news about renewable energy market developments in 2025?",
        ],
    },
    {
        "id": "S04",
        "desc": "Emerging markets / international focus",
        "messages": [
            "I'm Wei Zhang from Vanguard's international equity team. I'm looking at emerging markets exposure. Can you search for recent news on emerging market trends and economic developments in Asia and Latin America? Also check market trends for EEM.",
        ],
    },
    {
        "id": "S05",
        "desc": "Macro / Fed rates & fixed income",
        "messages": [
            "This is Robert Kim, a macro strategist at JPMorgan. I'm tracking Fed rate decisions and their impact on equity valuations. Can you search for the latest news on Federal Reserve policy and interest rate outlooks? How are financials like BAC and GS performing?",
        ],
    },
    {
        "id": "S06",
        "desc": "Value investing / dividend stocks",
        "messages": [
            "Hi, I'm Margaret Liu from Berkshire Advisory. I focus on deep value investing with a low risk tolerance and long time horizon. Please get me stock data for KO and JNJ, and tell me about recent dividend news for value investors.",
        ],
    },
    {
        "id": "S07",
        "desc": "Small-cap growth opportunities",
        "messages": [
            "I'm Alex Rivera, an analyst at ARK Invest specializing in small-cap disruptive innovation. High risk tolerance. Can you search for news on small-cap tech and biotech stocks with breakout potential? Also look at CRSP and ARKG trends.",
        ],
    },
    {
        "id": "S08",
        "desc": "Consumer discretionary & retail trends",
        "messages": [
            "Hello, I'm Diana Foster from T. Rowe Price, covering consumer discretionary. Moderate risk profile. Can you pull data on AMZN and TSLA, and search for recent news on consumer spending trends and retail sector performance?",
        ],
    },
    {
        "id": "S09",
        "desc": "Semiconductor supply chain concerns",
        "messages": [
            "I'm Tom Nakamura from Sequoia Capital. I'm researching semiconductor supply chain risks for tech portfolio companies. Can you search for recent news on semiconductor shortages and supply chain disruptions? Also get me data on AMD and INTC.",
        ],
    },
    {
        "id": "S10",
        "desc": "Portfolio diversification & sector rotation",
        "messages": [
            "Hi, I'm Patricia Owens from Wells Fargo Advisors. I work with retirees who need balanced, diversified portfolios. Conservative risk profile. Can you give me an overview of current sector rotation trends and get stock data for SPY and BRK-B? Also search for news about defensive investing strategies.",
        ],
    },
]


def invoke_agent(client, session_id: str, prompt: str) -> str:
    payload = json.dumps({"prompt": prompt}).encode("utf-8")
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_ARN,
            runtimeSessionId=session_id,
            payload=payload,
        )
        content_type = response.get("contentType", "")
        if "event-stream" in content_type:
            chunks = []
            for line in response["response"].iter_lines(chunk_size=10):
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        line = line[6:]
                    chunks.append(line)
            return "\n".join(chunks)
        else:
            raw = response.get("response")
            if raw:
                data = raw.read().decode("utf-8")
                try:
                    return json.loads(data)
                except Exception:
                    return data
            return str(response)
    except Exception as e:
        return f"ERROR: {e}"


def main():
    client = boto3.client("bedrock-agentcore", region_name=REGION)
    results = []

    for session in SESSIONS:
        sid = session["id"]
        desc = session["desc"]
        runtime_session_id = str(uuid.uuid4())  # 36 chars, satisfies min=33

        logger.info(f"\n{'='*60}")
        logger.info(f"[{sid}] {desc}")
        logger.info(f"Session ID: {runtime_session_id}")

        session_result = {"session_id": sid, "desc": desc, "runtime_session_id": runtime_session_id, "turns": []}

        for i, msg in enumerate(session["messages"], 1):
            logger.info(f"  Turn {i}: {msg[:100]}...")
            response = invoke_agent(client, runtime_session_id, msg)
            resp_preview = str(response)[:300]
            logger.info(f"  Response: {resp_preview}{'...' if len(str(response)) > 300 else ''}")
            session_result["turns"].append({"turn": i, "prompt": msg, "response": str(response)})
            if i < len(session["messages"]):
                time.sleep(3)

        results.append(session_result)
        logger.info(f"[{sid}] DONE")
        time.sleep(5)  # brief pause between sessions

    # Save results
    out_file = "session_results_10.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"\nAll 10 sessions complete. Results saved to {out_file}")

    success = sum(1 for r in results if all("ERROR" not in t["response"] for t in r["turns"]))
    logger.info(f"Successful sessions: {success}/10")


if __name__ == "__main__":
    main()
