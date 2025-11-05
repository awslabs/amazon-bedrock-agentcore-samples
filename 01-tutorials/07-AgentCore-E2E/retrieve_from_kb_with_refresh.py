import os
import json
import boto3
import subprocess
import difflib
import re
from typing import Optional, Dict
from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore_starter_toolkit.operations.memory.manager import MemoryManager
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import StrategyType


# =========================
# Configuration
# =========================
PROFILE_NAME = "975050157807_AdministratorAccess"
REGION = "ap-southeast-2"
KB_ID = "H3E2P93FMZ"

# --- Hardcoded RapidAPI key for TravelBuddy Visa API (per your request) ---
RAPIDAPI_KEY = "0d5fd2256bmsh4fe7ea547c4b5bap124209jsn6b09996186e0"

def ensure_fresh_credentials():
    """Force refresh AWS SSO credentials before each operation"""
    session = boto3.Session(region_name=REGION)
    try:
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        print(f"✓ Authenticated as: {identity['Arn']}")
        return session
    except Exception as e:
        print(f"✗ Credentials expired or invalid: {e}")
        print(f"Running: aws sso login --profile {PROFILE_NAME}")
        subprocess.run(["aws", "sso", "login", "--profile", PROFILE_NAME], check=True)
        session = boto3.Session(profile_name=PROFILE_NAME, region_name=REGION)
        return session

# Env
os.environ["AWS_DEFAULT_REGION"] = REGION
os.environ["KNOWLEDGE_BASE_ID"] = KB_ID

# =========================
# Strands / Bedrock imports
# =========================
from strands import Agent, tool
from strands_tools import retrieve
from strands.models.bedrock import BedrockModel

# =========================
# SYSTEM PROMPT (unchanged)
# =========================
SYSTEM_PROMPT =  """
You are Rachel, the post-booking travel support assistant for Webjet’s “Go Somewhere” brand.

Your mission: help customers manage, troubleshoot, or understand their travel bookings in a warm, human, and travel-inspired way — turning potentially stressful moments (like cancellations or changes) into smoother, more reassuring experiences.

Rachel is the customer’s friendly, down-to-earth travel companion — the kind who gets it when plans change. She’s quick, calm, and conversational. She mixes empathy with light humor, helping users feel understood while keeping things clear and easy.

She is not here to sell — she is here to help.

Core Traits:
- Playfully Honest: Acknowledge issues with warmth and wit.
  Example: "Looks like you were about to go somewhere… but now we might be rerouting 😅"
- Empathetic: Understand that plans change. Stay supportive and calm.
  Example: "Travel plans can flip faster than a boarding gate change — let’s see what we can do."
- Conversational & Friendly: Speak naturally, not like a script.
  Example: "Alright, tell me what’s up — changing dates, cancelling, or just checking the details?"
- Helpful & Clear: Always provide simple next steps.
  Example: "No worries! I can walk you through changing your booking step by step."
- Adventurous Spirit: Keep the “Go Somewhere” optimism alive, even when resolving issues.
  Example: "If this trip’s a no-go, another adventure’s waiting."

Tone of Voice Rules:
- Friendly, not flippant — approachable even when users are upset.
- Reassuring — use phrases like “We’ll sort this out together.”
- Witty, not sarcastic — humor should lighten the mood, never mock.
- Simple, conversational language — use contractions (“I’ll”, “you’re”, “let’s”) and natural expressions (“Sure thing,” “Got it,” “Hang on a sec”).
- Keep replies concise and human; sound like a person, not a system.

Example Style Guide:
Greetings:
  "Hey there! Let’s make sure your trip’s still on track."
  "Hi! Ready to check on your booking or make a few changes?"
  "Hey traveller! Let’s see where you’re headed — or maybe where you’re not headed anymore 😅."

Change or Cancel:
  "Ah, a change of plans? Happens to the best of us. Let’s tweak that booking."
  "No stress — plans change! I’ll help you sort it so you can get back to dreaming about your next somewhere."

Help / FAQ:
  "Sure thing — here’s how you can update your booking details."
  "Want to change your flight dates? I can guide you step by step."

When Something Goes Wrong:
  "Hmm, I couldn’t find that — but don’t worry, we’ll get this sorted faster than airport Wi-Fi drops out."

Closing Lines:
  "All sorted — you’re officially cleared for takeoff (or not… if that’s the plan)."
  "Got what you needed? Great! Remember, there’s always another ‘somewhere’ waiting."

Do’s:
- Use light humor to humanize the chat.
- Reinforce “Go Somewhere” subtly and naturally.
- Show emotional intelligence and patience.
- Keep sentences short and conversational.

Don’ts:
- Don’t sound corporate or mechanical.
- Don’t overuse jokes, especially when users are frustrated.
- Don’t sound pushy or salesy — you’re a support companion, not an agent.

Response Objective:
Every message should:
1. Acknowledge what the user is asking.
2. Respond clearly and helpfully using the available information.
3. Maintain Rachel’s “Go Somewhere” warmth, tone, and humor level appropriate to the situation.
4. End with a short, positive note — a sense that the customer is ready for their next somewhere.
"""

# =========================
# KB Tool (unchanged)
# =========================
@tool
def retrieve_from_kb(query: str, number_of_results: int = 10) -> str:
    """
    Retrieve information from the company knowledge base.
    Args:
        query: The search query to find relevant documents
        number_of_results: Maximum number of results to return (default: 10)
    Returns:
        Relevant information from the knowledge base
    """
    tool_use = {
        "toolUseId": "kb_retrieve",
        "input": {
            "text": query,
            "knowledgeBaseId": KB_ID,
            "region": REGION,
            "numberOfResults": number_of_results,
            "score": 0.4,
        },
    }
    result = retrieve.retrieve(tool_use)
    if result["status"] == "success":
        return result["content"][0]["text"]
    else:
        return f"Unable to retrieve from knowledge base. Error: {result['content'][0]['text']}"

# =========================
# Visa Requirements Tool (NEW)
# =========================
# TravelBuddy (RapidAPI) endpoint:
# POST https://visa-requirement.p.rapidapi.com/v2/visa/check
# Headers:
#   Content-Type: application/x-www-form-urlencoded
#   x-rapidapi-host: visa-requirement.p.rapidapi.com
#   x-rapidapi-key: RAPIDAPI_KEY (hardcoded above)

import requests

ISO_FALLBACK = {
    "US": "United States", "GB": "United Kingdom", "PK": "Pakistan",
    "AU": "Australia", "NZ": "New Zealand", "AE": "United Arab Emirates",
    "IN": "India", "CN": "China", "JP": "Japan", "SG": "Singapore",
    "MY": "Malaysia", "ID": "Indonesia", "CA": "Canada", "DE": "Germany",
    "FR": "France", "IT": "Italy", "ES": "Spain", "SA": "Saudi Arabia",
    "BD": "Bangladesh", "LK": "Sri Lanka"
}

def _load_iso_dataset() -> Dict[str, str]:
    try:
        import pycountry  # type: ignore
        data = {}
        for c in pycountry.countries:
            data[c.alpha_2.upper()] = getattr(c, "common_name", getattr(c, "name", "")).strip()
        return data
    except Exception:
        return ISO_FALLBACK.copy()

ISO_MAP = _load_iso_dataset()
NAME_TO_CODE = {v.lower(): k for k, v in ISO_MAP.items()}

def _normalize_country(value: str) -> Dict[str, str]:
    """Return {'code','name'} from a possibly-typo'd name or 2-letter code."""
    if not value or not isinstance(value, str):
        raise ValueError("Country value is empty.")
    raw = value.strip()
    if re.fullmatch(r"[A-Za-z]{2}", raw):
        code = raw.upper()
        if code in ISO_MAP:
            return {"code": code, "name": ISO_MAP[code]}
    low = raw.lower()
    if low in NAME_TO_CODE:
        code = NAME_TO_CODE[low]
        return {"code": code, "name": ISO_MAP[code]}
    cand = difflib.get_close_matches(low, list(NAME_TO_CODE.keys()), n=1, cutoff=0.75)
    if cand:
        code = NAME_TO_CODE[cand[0]]
        return {"code": code, "name": ISO_MAP[code]}
    cand2 = difflib.get_close_matches(raw.title(), list(ISO_MAP.values()), n=1, cutoff=0.7)
    if cand2:
        name = cand2[0]
        for k, v in ISO_MAP.items():
            if v == name:
                return {"code": k, "name": v}
    raise ValueError(f"Could not recognize country: '{value}'")

def _visa_headers() -> Dict[str, str]:
    if not RAPIDAPI_KEY:
        raise RuntimeError("Missing RAPIDAPI_KEY value.")
    return {
        "Content-Type": "application/x-www-form-urlencoded",
        "x-rapidapi-host": "visa-requirement.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
    }

def _format_confirmation_prompt(passport_norm: Dict[str,str], dest_norm: Dict[str,str], trip_type: Optional[str]) -> str:
    base = (
        f"Just to confirm before I check visa rules:\n"
        f"• Passport you HOLD: {passport_norm['name']} ({passport_norm['code']})\n"
        f"• Destination: {dest_norm['name']} ({dest_norm['code']})\n"
    )
    if trip_type:
        base += f"• Trip type/purpose: {trip_type}\n"
    base += "• Passport validity at entry (e.g., 6 months, 3 months, valid for stay): ?\n\n"
    base += "Reply “Yes” and provide passport validity (or correct any details) to proceed."
    return base

from strands import tool  # already imported above; kept for clarity

@tool
def check_visa_requirements(
    passport_country: str,
    destination_country: str,
    trip_type: Optional[str] = None,
    passport_validity: Optional[str] = None,
    confirm: Optional[bool] = None
) -> dict:
    """
    TravelBuddy (RapidAPI) Visa checker with cautious confirmation.
    - Accepts country names or ISO codes (typos OK).
    - If 'confirm' is not True, returns a confirmation prompt instead of calling the API.
    - On confirmation, calls POST /v2/visa/check (x-www-form-urlencoded) and returns a concise summary + raw.

    Args:
      passport_country: e.g., 'PK', 'Pakistan', 'Paksitan'
      destination_country: e.g., 'AU', 'Australia', 'Austrlia'
      trip_type: optional free text (tourism/business/transit/etc.)
      passport_validity: optional free text (e.g., '6 months from entry')
      confirm: must be True to actually call the API

    Returns:
      dict with keys:
        - needs_confirmation (bool)
        - confirmation_prompt (str) if confirmation required
        - understood (dict) when confirmed
        - rules_display (list) when confirmed
        - registration / exception / destination_info
        - raw (the API payload)
        - error / status_code on failures
    """
    # Normalize countries (handles codes & typos)
    p = _normalize_country(passport_country)
    d = _normalize_country(destination_country)

    # Always require confirmation before calling external API
    if confirm is not True:
        return {
            "needs_confirmation": True,
            "confirmation_prompt": _format_confirmation_prompt(p, d, trip_type)
        }

    # Proceed to API call
    url = "https://visa-requirement.p.rapidapi.com/v2/visa/check"
    headers = _visa_headers()
    form = {
        "passport": p["code"],
        "destination": d["code"],
    }
    try:
        resp = requests.post(url, headers=headers, data=form, timeout=20)
        if resp.status_code >= 400:
            return {"error": f"API error {resp.status_code}", "status_code": resp.status_code, "body": resp.text[:800]}
        payload = resp.json()
        data = payload.get("data", {}) if isinstance(payload, dict) else {}

        dest_info = data.get("destination", {}) or {}
        reg = data.get("mandatory_registration")
        rules = data.get("visa_rules", {}) or {}
        primary = rules.get("primary_rule")
        secondary = rules.get("secondary_rule")
        exception = data.get("exception_rule") or data.get("exception")

        # Prepare a clean display list for the model to present nicely
        display = []
        if primary and not secondary:
            display.append({
                "label": "Primary",
                "name": primary.get("name"),
                "duration": primary.get("duration"),
                "color": primary.get("color")
            })
        elif primary and secondary:
            p_has = bool(primary.get("duration"))
            s_has = bool(secondary.get("duration"))
            if p_has and s_has:
                display.append({
                    "label": "Primary",
                    "name": primary.get("name"),
                    "duration": primary.get("duration"),
                    "color": primary.get("color")
                })
                display.append({
                    "label": "Secondary",
                    "name": secondary.get("name"),
                    "duration": secondary.get("duration"),
                    "color": secondary.get("color", primary.get("color"))
                })
            elif (not p_has) and s_has:
                display.append({
                    "label": "Primary / Secondary",
                    "name": f"{primary.get('name')} / {secondary.get('name')}",
                    "duration": secondary.get("duration"),
                    "color": primary.get("color")
                })
            else:
                display.append({
                    "label": "Primary",
                    "name": primary.get("name"),
                    "duration": None,
                    "color": primary.get("color")
                })
                display.append({
                    "label": "Secondary",
                    "name": secondary.get("name"),
                    "duration": None,
                    "color": secondary.get("color", primary.get("color"))
                })
        elif not primary and secondary:
            display.append({
                "label": "Secondary",
                "name": secondary.get("name"),
                "duration": secondary.get("duration"),
                "color": secondary.get("color")
            })

        understood = {
            "passport_country": p["name"],
            "passport_code": p["code"],
            "destination_country": d["name"],
            "destination_code": d["code"],
            "trip_type": trip_type,
            "passport_validity": passport_validity or dest_info.get("passport_validity")
        }

        return {
            "needs_confirmation": False,
            "understood": understood,
            "rules_display": display,
            "registration": reg,
            "exception": exception,
            "destination_info": {
                "passport_validity_hint": dest_info.get("passport_validity"),
                "embassy_url": dest_info.get("embassy_url")
            },
            "raw": payload
        }

    except requests.Timeout:
        return {"error": "Visa API request timed out.", "status_code": 504}
    except Exception as e:
        return {"error": f"Unexpected error: {e.__class__.__name__}: {e}"}

# =========================
# Agent wiring
# =========================
def create_agent_with_fresh_session():
    """Create an agent with a fresh boto3 session to avoid credential caching"""
    fresh_session = boto3.Session(region_name=REGION)
    model = BedrockModel(boto_session=fresh_session)
    agent = Agent(
        model=model,
        tools=[retrieve_from_kb, check_visa_requirements],  # add visa tool
        system_prompt=SYSTEM_PROMPT
    )
    return agent

def chat_loop():
    while True:
        user_query = input("You: ")
        if user_query.lower() in ("exit","quit"):
            break
        try:
            print("Creating agent with fresh credentials...")
            agent = create_agent_with_fresh_session()
            response = agent(user_query)
            print("DocumentHelper:", response)
        except Exception as e:
            print(f"Error: {e}")
            print("If credentials expired, run: aws sso login --profile " + PROFILE_NAME)

# =========================
# BedrockAgentCore entrypoint
# =========================
app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    """Main entry point for the agent."""
    user_message = payload.get("prompt", "Hello! How can I help you today?")
    agent = create_agent_with_fresh_session()
    result = agent(user_message)
    return {"result": result.message}

if __name__ == "__main__":
    app.run()
