#!/usr/bin/env python3
"""
Run 60 sessions (20 per persona) against market_trends_agent_v2 runtime.
Personas from the demo talk track:
  - Marcus Rivera  : Energy (XOM, CVX), value investing
  - Sarah Chen     : Healthcare, ESG, GLP-1 drugs
  - Yuval Bing     : Tech (NVDA, MSFT, AMD), AI infrastructure
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

# ---------------------------------------------------------------------------
# Session definitions — 20 per persona, single-turn per session
# ---------------------------------------------------------------------------

MARCUS_SESSIONS = [
    {
        "id": "MR01",
        "msg": "Hi, I'm Marcus Rivera from Steadfast Capital. I specialize in value investing in the energy sector. Can you pull the latest stock data for XOM and CVX and give me a trend summary?",
    },
    {
        "id": "MR02",
        "msg": "Marcus Rivera here. I'd like a crude oil market update. Search for recent news on oil prices, OPEC output decisions, and how that's affecting energy majors.",
    },
    {
        "id": "MR03",
        "msg": "I'm Marcus Rivera. Can you compare the dividend yields and price performance of XOM vs CVX? Also find news on energy sector capital allocation.",
    },
    {
        "id": "MR04",
        "msg": "Marcus Rivera, Steadfast Capital. Get me the current price and 52-week performance for the Energy Select Sector ETF (XLE), and search for energy sector rotation news.",
    },
    {
        "id": "MR05",
        "msg": "Hi, Marcus Rivera. I'm evaluating midstream pipeline companies for yield-focused clients. Pull data for KMI and search for natural gas pipeline infrastructure news.",
    },
    {
        "id": "MR06",
        "msg": "Marcus Rivera here. What's the latest on natural gas prices and LNG export trends? Search for news on US LNG export capacity and demand from Europe and Asia.",
    },
    {
        "id": "MR07",
        "msg": "I'm Marcus Rivera. My clients want to know how the clean energy transition is impacting traditional oil majors. Search for news on energy transition strategy from XOM, CVX, and BP.",
    },
    {
        "id": "MR08",
        "msg": "Marcus Rivera, Steadfast Capital. Get me current stock data for OXY (Occidental Petroleum) and search for news on Warren Buffett's energy holdings and his thesis.",
    },
    {
        "id": "MR09",
        "msg": "Hi, I'm Marcus Rivera. I'm looking at geopolitical risk to energy supply chains. Search for news on Middle East tensions and their market impact on crude oil prices.",
    },
    {
        "id": "MR10",
        "msg": "Marcus Rivera here. Can you pull data for PSX (Phillips 66) and VLO (Valero), and search for recent news on US refinery margins and crack spreads?",
    },
    {
        "id": "MR11",
        "msg": "I'm Marcus Rivera. My value portfolio needs a sector risk check. Search for news about regulatory risks to fossil fuel companies — EPA rules, carbon taxes, and SEC climate disclosure requirements.",
    },
    {
        "id": "MR12",
        "msg": "Marcus Rivera, Steadfast Capital. Pull data for COP (ConocoPhillips) and search for news on Permian Basin production growth and its impact on oil supply.",
    },
    {
        "id": "MR13",
        "msg": "Hi, I'm Marcus Rivera. How are energy stocks performing relative to the S&P 500 this year? Get data on XOM and search for energy sector vs broader market comparison news.",
    },
    {
        "id": "MR14",
        "msg": "Marcus Rivera here. I need to evaluate SLB (Schlumberger) for oilfield services exposure. Pull current stock data and search for oilfield services sector trends.",
    },
    {
        "id": "MR15",
        "msg": "I'm Marcus Rivera. Search for recent news on oil price forecasts from Goldman Sachs, Morgan Stanley, and the EIA. What's the consensus for crude in Q3 2025?",
    },
    {
        "id": "MR16",
        "msg": "Marcus Rivera, Steadfast Capital. Pull stock data for ET (Energy Transfer) and search for news on pipeline dividend sustainability and midstream sector outlook.",
    },
    {
        "id": "MR17",
        "msg": "Hi, I'm Marcus Rivera. I'm considering adding uranium exposure for the nuclear energy renaissance. Search for news on uranium prices and nuclear energy stocks like CCJ.",
    },
    {
        "id": "MR18",
        "msg": "Marcus Rivera here. Get me the latest on natural gas utility stocks — pull data for LNG (Cheniere) and search for news on US natural gas demand from data centers and AI.",
    },
    {
        "id": "MR19",
        "msg": "I'm Marcus Rivera. My clients are asking about energy inflation as a hedge. Search for news on commodity inflation, energy price trends, and which energy stocks benefit most.",
    },
    {
        "id": "MR20",
        "msg": "Marcus Rivera, Steadfast Capital. Give me a comprehensive energy sector briefing — pull data for XOM and CVX, search for OPEC news, and summarize the sector outlook for the next quarter.",
    },
]

SARAH_SESSIONS = [
    {
        "id": "SC01",
        "msg": "Hi, I'm Sarah Chen from Apex Healthcare Advisors. I focus on healthcare and ESG investing. Can you give me a healthcare sector briefing with current data on JNJ and search for recent healthcare market trends?",
    },
    {
        "id": "SC02",
        "msg": "Sarah Chen here. My clients are very interested in GLP-1 obesity drugs. Search for the latest news on Novo Nordisk and Eli Lilly's GLP-1 pipeline and competitive dynamics.",
    },
    {
        "id": "SC03",
        "msg": "I'm Sarah Chen. Can you pull stock data for NVO (Novo Nordisk) and LLY (Eli Lilly), and search for news on the obesity drug market size and growth projections?",
    },
    {
        "id": "SC04",
        "msg": "Sarah Chen, Apex Healthcare Advisors. I need ESG ETF data. Pull performance data for a healthcare ESG theme and search for news on ESG investing in healthcare and pharma.",
    },
    {
        "id": "SC05",
        "msg": "Hi, I'm Sarah Chen. Search for recent FDA drug approval news and biotech pipeline updates. Which biotech companies have had major approvals or rejections this month?",
    },
    {
        "id": "SC06",
        "msg": "Sarah Chen here. Pull stock data for UNH (UnitedHealth Group) and search for news on health insurance sector performance and managed care trends.",
    },
    {
        "id": "SC07",
        "msg": "I'm Sarah Chen. My ESG clients want to screen out companies with low social scores. Search for news on pharmaceutical company ESG ratings and controversies in 2025.",
    },
    {
        "id": "SC08",
        "msg": "Sarah Chen, Apex Healthcare Advisors. Get me data on MDT (Medtronic) and SYK (Stryker), and search for medical device sector trends and aging population demand drivers.",
    },
    {
        "id": "SC09",
        "msg": "Hi, I'm Sarah Chen. Search for recent news on pharma M&A activity — which major acquisitions or deal announcements are shaping the pharmaceutical landscape?",
    },
    {
        "id": "SC10",
        "msg": "Sarah Chen here. I'm evaluating cancer immunotherapy stocks. Search for news on checkpoint inhibitors, CAR-T therapy advances, and companies like BMY and MRK.",
    },
    {
        "id": "SC11",
        "msg": "I'm Sarah Chen. Pull current data for ABBV (AbbVie) and search for news on its drug pipeline beyond Humira and how it's managing biosimilar competition.",
    },
    {
        "id": "SC12",
        "msg": "Sarah Chen, Apex Healthcare Advisors. Search for news on CRISPR and gene editing therapy approvals. Get data on CRSP and EDIT for my innovation-focused healthcare sleeve.",
    },
    {
        "id": "SC13",
        "msg": "Hi, I'm Sarah Chen. My clients are asking about digital health trends. Search for news on telemedicine platforms, remote patient monitoring, and health tech stocks.",
    },
    {
        "id": "SC14",
        "msg": "Sarah Chen here. Pull stock data for CVS Health and search for news on pharmacy benefit managers and their regulatory challenges in 2025.",
    },
    {
        "id": "SC15",
        "msg": "I'm Sarah Chen. I want to understand healthcare infrastructure REIT exposure. Search for news on medical office and hospital REITs, and pull data for WELL (Welltower).",
    },
    {
        "id": "SC16",
        "msg": "Sarah Chen, Apex Healthcare Advisors. Search for news on AI in drug discovery and which pharmaceutical companies are partnering with AI firms for R&D acceleration.",
    },
    {
        "id": "SC17",
        "msg": "Hi, I'm Sarah Chen. Can you pull data for PFE (Pfizer) and search for recent news on Pfizer's post-COVID strategy and pipeline recovery?",
    },
    {
        "id": "SC18",
        "msg": "Sarah Chen here. I need a mental health sector update. Search for news on mental health biotech companies, psychedelic therapy stocks, and behavioral health trends.",
    },
    {
        "id": "SC19",
        "msg": "I'm Sarah Chen. Search for news on Medicare and Medicaid reimbursement policy changes and how they're affecting hospital and health system stocks.",
    },
    {
        "id": "SC20",
        "msg": "Sarah Chen, Apex Healthcare Advisors. Give me a comprehensive healthcare briefing — pull data for JNJ and LLY, search for GLP-1 news and biotech approvals, and summarize the sector outlook.",
    },
]

YUVAL_SESSIONS = [
    {
        "id": "YB01",
        "msg": "Hi, I'm Yuval Bing from Horizon Ventures. I focus on AI and semiconductor stocks. Pull data for NVDA and AMD and give me a comparison of their AI chip positioning.",
    },
    {
        "id": "YB02",
        "msg": "Yuval Bing here. Search for the latest news on NVIDIA's data center GPU demand, Blackwell architecture ramp, and supply constraints going into H2 2025.",
    },
    {
        "id": "YB03",
        "msg": "I'm Yuval Bing. Get me current stock data for MSFT and search for news on Azure AI growth, Microsoft Copilot enterprise adoption, and OpenAI partnership developments.",
    },
    {
        "id": "YB04",
        "msg": "Yuval Bing, Horizon Ventures. Search for news on hyperscaler AI capex spending — what are Microsoft, Amazon, Google, and Meta budgeting for AI infrastructure in 2025?",
    },
    {
        "id": "YB05",
        "msg": "Hi, I'm Yuval Bing. Pull data for AMD and search for news on AMD's AI accelerator roadmap — MI300X traction, competition with NVDA in data centers, and enterprise wins.",
    },
    {
        "id": "YB06",
        "msg": "Yuval Bing here. I want to understand semiconductor equipment exposure. Pull data for AMAT (Applied Materials) and search for news on semiconductor capex cycles and equipment demand.",
    },
    {
        "id": "YB07",
        "msg": "I'm Yuval Bing. Search for news on AI chip export controls — US restrictions on NVIDIA exports to China and the impact on revenue outlook and alternative chip strategies.",
    },
    {
        "id": "YB08",
        "msg": "Yuval Bing, Horizon Ventures. Get data on SMCI (Super Micro Computer) and search for news on AI server demand, rack-scale cooling technology, and data center build-out.",
    },
    {
        "id": "YB09",
        "msg": "Hi, I'm Yuval Bing. Search for the latest MSFT earnings news — revenue breakdown by segment, cloud growth rates, and analyst reactions to AI monetization progress.",
    },
    {
        "id": "YB10",
        "msg": "Yuval Bing here. Pull data for INTC (Intel) and search for news on Intel's foundry strategy, 18A process node, and whether it can compete with TSMC and Samsung.",
    },
    {
        "id": "YB11",
        "msg": "I'm Yuval Bing. I'm tracking AI model company stocks. Search for news on Anthropic, OpenAI valuation, and publicly traded AI software companies like PLTR and AI.",
    },
    {
        "id": "YB12",
        "msg": "Yuval Bing, Horizon Ventures. Get data on GOOGL and search for news on Google DeepMind's Gemini progress, TPU custom silicon advantages, and cloud AI competitive positioning.",
    },
    {
        "id": "YB13",
        "msg": "Hi, I'm Yuval Bing. Search for news on AI infrastructure power demand — data center electricity consumption, nuclear power partnerships, and energy stocks benefiting from AI.",
    },
    {
        "id": "YB14",
        "msg": "Yuval Bing here. Pull data for TSM (TSMC) and search for news on TSMC's Arizona fab progress, advanced packaging capacity, and its role in the AI supply chain.",
    },
    {
        "id": "YB15",
        "msg": "I'm Yuval Bing. My clients want enterprise software exposure. Pull data for CRM (Salesforce) and search for news on AI agents in enterprise software and Salesforce AgentForce traction.",
    },
    {
        "id": "YB16",
        "msg": "Yuval Bing, Horizon Ventures. Search for news on cybersecurity spending trends driven by AI threats — what are CrowdStrike, Palo Alto Networks, and Zscaler showing in growth?",
    },
    {
        "id": "YB17",
        "msg": "Hi, I'm Yuval Bing. I want to evaluate quantum computing as a thematic sleeve. Search for news on IBM Quantum, Google quantum, and publicly traded quantum computing stocks.",
    },
    {
        "id": "YB18",
        "msg": "Yuval Bing here. Pull data for AVGO (Broadcom) and search for news on custom AI chip development — Broadcom's XPU programs with Google and Meta.",
    },
    {
        "id": "YB19",
        "msg": "I'm Yuval Bing. Search for news on AI PC and edge AI trends — Intel Meteor Lake, Qualcomm Snapdragon X, and what the AI PC refresh cycle means for semiconductor demand.",
    },
    {
        "id": "YB20",
        "msg": "Yuval Bing, Horizon Ventures. Give me a comprehensive AI and semiconductor briefing — pull data for NVDA and MSFT, search for AI capex and chip competition news, and summarize the sector outlook.",
    },
]

ALL_SESSIONS = MARCUS_SESSIONS + SARAH_SESSIONS + YUVAL_SESSIONS


def invoke_agent(client, runtime_session_id: str, prompt: str) -> str:
    payload = json.dumps({"prompt": prompt}).encode("utf-8")
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_ARN,
            runtimeSessionId=runtime_session_id,
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
    errors = []

    total = len(ALL_SESSIONS)
    logger.info(f"Starting {total} sessions against {AGENT_ARN}")

    for i, session in enumerate(ALL_SESSIONS, 1):
        sid = session["id"]
        msg = session["msg"]
        runtime_session_id = str(uuid.uuid4())  # 36 chars

        persona = "Marcus Rivera" if sid.startswith("MR") else ("Sarah Chen" if sid.startswith("SC") else "Yuval Bing")
        logger.info(f"[{i:02d}/{total}] [{sid}] {persona} — {msg[:80]}...")

        response = invoke_agent(client, runtime_session_id, msg)
        is_error = str(response).startswith("ERROR:")
        status = "ERROR" if is_error else "OK"
        preview = str(response)[:200]

        logger.info(f"  [{status}] {preview}{'...' if len(str(response)) > 200 else ''}")

        results.append({
            "session_id": sid,
            "persona": persona,
            "runtime_session_id": runtime_session_id,
            "prompt": msg,
            "response": str(response),
            "status": status,
        })

        if is_error:
            errors.append(sid)

        # Pace to avoid throttling: 5s between sessions
        if i < total:
            time.sleep(5)

    # Save results
    out_file = "session_results_60.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    ok = total - len(errors)
    logger.info(f"\n{'='*60}")
    logger.info(f"All {total} sessions complete. Results saved to {out_file}")
    logger.info(f"Successful: {ok}/{total}")
    if errors:
        logger.warning(f"Errors in: {errors}")


if __name__ == "__main__":
    main()
