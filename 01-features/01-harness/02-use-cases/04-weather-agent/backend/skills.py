"""Skills — generate weather forecast reports as XLSX spreadsheets.

Uses AgentCore's Git-based skill fetching: the harness downloads the xlsx skill
from GitHub at invocation time — no container change or manual installation needed.
"""

import sys
from pathlib import Path

import boto3
from botocore.config import Config

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from utils.client import get_agentcore_client

from resources import REGION

MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"


def generate_weather_report(harness_arn: str, session_id: str, city: str = "the cities discussed") -> dict:
    """Generate a weather forecast XLSX report using the xlsx skill fetched from Git."""
    client = get_agentcore_client(config=Config(read_timeout=360))

    prompt = (
        f"Create an Excel spreadsheet with a 7-day weather forecast for {city}. "
        f"The first row must be a title: '{city} - 7-Day Weather Forecast' merged across all columns. "
        "Then include columns for: Day, Condition, High (°F), Low (°F), Wind (mph), Humidity (%), UV Index. "
        "Add realistic weather data that varies day to day. "
        "Include a summary row at the bottom with averages. "
        "Apply formatting: bold title, bold headers, alternating row colors, conditional formatting "
        "(red for high temps > 90°F, blue for low temps < 40°F). "
        "Save it as /tmp/weather_forecast.xlsx"
    )

    # Invoke with xlsx skill fetched from Git (no pre-installation needed)
    response = client.invoke_harness(
        harnessArn=harness_arn,
        runtimeSessionId=session_id,
        skills=[
            {"git": {"url": "https://github.com/anthropics/skills", "path": "skills/xlsx"}}
        ],
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        model={"bedrockModelConfig": {"modelId": MODEL_ID}},
        timeoutSeconds=300,
    )

    agent_text = ""
    for event in response["stream"]:
        if "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            if "text" in delta:
                agent_text += delta["text"]

    # Download the file from the VM
    b64_data = ""
    resp = client.invoke_agent_runtime_command(
        agentRuntimeArn=harness_arn,
        runtimeSessionId=session_id,
        body={"command": "base64 /tmp/weather_forecast.xlsx 2>/dev/null"},
    )
    for event in resp["stream"]:
        if "chunk" in event and "contentDelta" in event["chunk"]:
            delta = event["chunk"]["contentDelta"]
            if "stdout" in delta:
                b64_data += delta["stdout"]

    b64_clean = b64_data.strip().replace("\n", "")
    if b64_clean:
        return {
            "success": True,
            "file_data": b64_clean,
            "filename": "weather_forecast.xlsx",
            "agent_response": agent_text[:500],
        }
    else:
        return {
            "success": False,
            "error": "No file generated",
            "agent_response": agent_text[:500],
        }
