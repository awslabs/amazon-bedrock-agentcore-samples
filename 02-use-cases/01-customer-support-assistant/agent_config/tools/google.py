from ..context import get_google_token_ctx, get_response_queue_ctx, set_google_token_ctx
from bedrock_agentcore.identity.auth import requires_access_token
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from scripts.utils import get_ssm_parameter
from strands import tool
import json

SCOPES = ["https://www.googleapis.com/auth/calendar"]


async def on_auth_url(url: str):
    response_queue = get_response_queue_ctx()
    print(f"Authorization url: {url}")
    await response_queue.put(f"Authorization url: {url}")


# This annotation helps agent developer to obtain access tokens from external applications
@requires_access_token(
    provider_name=get_ssm_parameter("/app/customersupport/agentcore/google_provider"),
    scopes=SCOPES,  # Google OAuth2 scopes
    auth_flow="USER_FEDERATION",  # On-behalf-of user (3LO) flow
    on_auth_url=on_auth_url,  # prints authorization URL to console
    force_authentication=True,
    into="access_token",
)
async def get_google_access_token(access_token: str):
    return access_token


@tool(
    name="Create_calendar_event",
    description="Creates a new event on your Google Calendar",
)
async def create_calendar_event() -> str:
    google_access_token = get_google_token_ctx()  # Get from context instead of global

    if not google_access_token:
        try:
            google_access_token = await get_google_access_token(
                access_token=google_access_token
            )
            set_google_token_ctx(token=google_access_token)
        except Exception as e:
            return "Error Authentication with Google: " + str(e)

    creds = Credentials(token=google_access_token, scopes=SCOPES)

    try:
        service = build("calendar", "v3", credentials=creds)

        # Define event details
        start_time = datetime.now() + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)

        event = {
            "summary": "Customer Support Call - Maira Ladeira Tanke",
            "location": "Virtual",
            "description": "This event was created by Customer Support Assistant.",
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


@tool(
    name="Get_calendar_events_today",
    description="Retrieves the calendar events for the day from your Google Calendar",
)
async def get_calendar_events_today() -> str:
    google_access_token = get_google_token_ctx()  # Get from context instead of global

    if not google_access_token:
        try:
            google_access_token = await get_google_access_token(
                access_token=google_access_token
            )
            set_google_token_ctx(token=google_access_token)
        except Exception as e:
            return "Error Authentication with Google: " + str(e)

    # Create credentials from the provided access token
    creds = Credentials(token=google_access_token, scopes=SCOPES)
    try:
        service = build("calendar", "v3", credentials=creds)
        # Call the Calendar API
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59)

        # Format with CDT timezone (-05:00)
        timeMin = today_start.strftime("%Y-%m-%dT00:00:00-05:00")
        timeMax = today_end.strftime("%Y-%m-%dT23:59:59-05:00")

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=timeMin,
                timeMax=timeMax,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        print(events)
        if not events:
            return json.dumps({"events": []})  # Return empty events array as JSON

        return json.dumps({"events": events})  # Return events wrapped in an object
    except HttpError as error:
        error_message = str(error)
        return json.dumps({"error": error_message, "events": []})
    except Exception as e:
        error_message = str(e)
        return json.dumps({"error": error_message, "events": []})
