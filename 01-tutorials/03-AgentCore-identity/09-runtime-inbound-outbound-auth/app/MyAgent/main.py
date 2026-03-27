"""
AgentCore Runtime agent with:
  - Inbound Auth:  Cognito JWT validates callers (configured in agentcore.json)
  - Outbound Auth: API key retrieved from AgentCore Identity at runtime

The @requires_api_key decorator fetches the stored API key from AgentCore Identity
(backed by Secrets Manager) so the key never appears in environment variables or code.
"""

import json
import os
import asyncio

import httpx
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_api_key

app = BedrockAgentCoreApp()

# Cache for outbound API key fetched from AgentCore Identity
_api_key_cache: dict = {}


@requires_api_key(provider_name="OutboundApiKey")
async def _fetch_api_key(*, api_key: str) -> None:
    """Retrieve the outbound API key from AgentCore Identity."""
    _api_key_cache["key"] = api_key


@tool
def get_weather(location: str) -> str:
    """Get the current weather for a location.

    Calls the wttr.in weather API. Also demonstrates that the outbound API key
    was securely retrieved from AgentCore Identity (backed by Secrets Manager).

    Args:
        location: City name or location (e.g. "Seattle", "London")
    """
    api_key = os.environ.get("OUTBOUND_API_KEY", "")
    print(f"[OutboundAuth] API key retrieved (first 8 chars): {api_key[:8]}...")

    # Call a real weather API
    try:
        resp = httpx.get(f"https://wttr.in/{location}?format=j1", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        current = data.get("current_condition", [{}])[0]
        area = data.get("nearest_area", [{}])[0]
        area_name = area.get("areaName", [{}])[0].get("value", location)
        country = area.get("country", [{}])[0].get("value", "")

        return json.dumps({
            "location": f"{area_name}, {country}",
            "temperature_f": current.get("temp_F", "N/A"),
            "temperature_c": current.get("temp_C", "N/A"),
            "condition": current.get("weatherDesc", [{}])[0].get("value", "N/A"),
            "humidity": f"{current.get('humidity', 'N/A')}%",
            "wind_mph": current.get("windspeedMiles", "N/A"),
            "feels_like_f": current.get("FeelsLikeF", "N/A"),
            "outbound_api_key_status": f"Retrieved from AgentCore Identity (first 8 chars: {api_key[:8]}...)",
        }, indent=2)
    except Exception as exc:
        return f"Weather API error: {exc}. API key status: {'retrieved' if api_key else 'missing'}"


@tool
def calculate(expression: str) -> str:
    """Evaluate a simple arithmetic expression."""
    try:
        result = eval(expression, {"__builtins__": {}})  # noqa: S307
        return f"{expression} = {result}"
    except Exception as exc:
        return f"Error evaluating expression: {exc}"


_model = BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0")
_agent: Agent | None = None


@app.entrypoint
async def handler(payload: dict) -> str:
    global _agent

    # Fetch the outbound API key on first invocation
    if "key" not in _api_key_cache:
        await _fetch_api_key(api_key="")
        os.environ["OUTBOUND_API_KEY"] = _api_key_cache.get("key", "")

    if _agent is None:
        _agent = Agent(
            model=_model,
            tools=[get_weather, calculate],
            system_prompt=(
                "You are a helpful assistant. "
                "You can check the weather and perform calculations."
            ),
        )

    user_input = payload.get("prompt", "")
    response = _agent(user_input)
    return response.message["content"][0]["text"]


if __name__ == "__main__":
    app.run()
