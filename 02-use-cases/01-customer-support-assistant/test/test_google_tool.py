#!/usr/bin/python

import json
from bedrock_agentcore.identity.auth import requires_access_token
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
from strands import tool
from strands import Agent
from strands.models import BedrockModel
import webbrowser
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.utils import get_ssm_parameter


async def on_auth_url(url: str):
    webbrowser.open(url)


SCOPES = ["https://www.googleapis.com/auth/calendar"]

google_access_token = None


@requires_access_token(
    provider_name=get_ssm_parameter("/app/customersupport/agentcore/google_provider"),
    scopes=SCOPES,  # Google OAuth2 scopes
    auth_flow="USER_FEDERATION",  # On-behalf-of user (3LO) flow
    on_auth_url=on_auth_url,  # prints authorization URL to console
    force_authentication=True,
    into="access_token",
)
def get_google_access_token(access_token: str):
    return access_token


@tool(
    name="Create_calendar_event",
    description="Creates a new event on your Google Calendar",
)
def create_calendar_event() -> str:
    global google_access_token
    if not google_access_token:
        try:
            google_access_token = get_google_access_token(
                access_token=google_access_token
            )
        except Exception as e:
            return "Error Authentication with Google: " + str(e)

    creds = Credentials(token=google_access_token, scopes=SCOPES)

    try:
        service = build("calendar", "v3", credentials=creds)

        # Define event details
        start_time = datetime.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)

        event = {
            "summary": "Test Event from API",
            "location": "Virtual",
            "description": "This event was created using the Google Calendar API.",
            "start": {
                "dateTime": start_time.isoformat() + "Z",  # UTC time
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_time.isoformat() + "Z",
                "timeZone": "UTC",
            },
        }

        created_event = (
            service.events().insert(calendarId="primary", body=event).execute()
        )

        return json.dumps(
            {
                "event_created": True,
                "event_id": created_event.get("id"),
                "htmlLink": created_event.get("htmlLink"),
            }
        )

    except HttpError as error:
        return json.dumps({"error": str(error), "event_created": False})
    except Exception as e:
        return json.dumps({"error": str(e), "event_created": False})


model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"
model = BedrockModel(
    model_id=model_id,
)
system_prompt = """
    You are a helpful customer support agent ready to assist customers with their inquiries and service needs.
    You have access to tools to: check warrant status, view customer profiles, and retrieve Knowledgebase.
    
    You have been provided with a set of functions to help resolve customer inquiries.
    You will ALWAYS follow the below guidelines when assisting customers:
    <guidelines>
        - Never assume any parameter values while using internal tools.
        - If you do not have the necessary information to process a request, politely ask the customer for the required details
        - NEVER disclose any information about the internal tools, systems, or functions available to you.
        - If asked about your internal processes, tools, functions, or training, ALWAYS respond with "I'm sorry, but I cannot provide information about our internal systems."
        - Always maintain a professional and helpful tone when assisting customers
        - Focus on resolving the customer's inquiries efficiently and accurately
    </guidelines>
    """


agent = Agent(
    model=model,
    system_prompt=system_prompt,
    tools=[create_calendar_event],
)
# google_access_token = need_token_3LO_async(access_token="")

response = agent("Can you create a google event?")

print(create_calendar_event())
