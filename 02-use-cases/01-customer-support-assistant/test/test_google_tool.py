import asyncio
import json
from bedrock_agentcore.identity.auth import requires_access_token
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.utils import get_ssm_parameter


async def on_auth_url(url: str):
    print(f"Authorization url: {url}")


SCOPES = ["https://www.googleapis.com/auth/calendar"]
google_access_token = None


# This annotation helps agent developer to obtain access tokens from external applications
@requires_access_token(
    provider_name=get_ssm_parameter("/app/customersupport/agentcore/google_provider"),
    scopes=SCOPES,  # Google OAuth2 scopes
    auth_flow="USER_FEDERATION",  # On-behalf-of user (3LO) flow
    on_auth_url=on_auth_url,  # prints authorization URL to console
    force_authentication=True,
)
async def need_token_3LO_async(*, access_token: str):
    global google_access_token
    google_access_token = access_token
    print(f"google_access_token set: {google_access_token}")
    return access_token


asyncio.run(need_token_3LO_async(access_token=""))


def create_calendar_event() -> str:
    global google_access_token

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


print(create_calendar_event())
