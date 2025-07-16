import os
import uuid
import asyncio
import logging
from bedrock_agentcore.identity.auth import requires_access_token
from agent import CustomerSupport  # Your custom agent class
from datetime import datetime, timedelta
import json
from strands import tool
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from scripts.utils import get_ssm_parameter

from tools.agent_core_memory import AgentCoreMemoryToolProvider
from memory_hook_provider import MemoryHook
from bedrock_agentcore.memory import MemoryClient

from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Environment flags
os.environ["STRANDS_OTEL_ENABLE_CONSOLE_EXPORT"] = "true"
os.environ["STRANDS_TOOL_CONSOLE_MODE"] = "enabled"

os.environ["KNOWLEDGE_BASE_ID"] = get_ssm_parameter(
    "/app/customersupport/knowledge_base/knowledge_base_id"
)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bedrock app and global agent instance
app = BedrockAgentCoreApp()

agent = None  # Will be initialized with access token
gateway_access_token = None
google_access_token = None

memory_client = MemoryClient()


# Queue for streaming responses
class StreamingQueue:
    def __init__(self):
        self.finished = False
        self.queue = asyncio.Queue()

    async def put(self, item):
        await self.queue.put(item)

    async def finish(self):
        self.finished = True
        await self.queue.put(None)

    async def stream(self):
        while True:
            item = await self.queue.get()
            if item is None and self.finished:
                break
            yield item


response_queue = StreamingQueue()


@tool(
    name="Create_calendar_event",
    description="Creates a new event on your Google Calendar",
)
def create_calendar_event() -> str:
    global google_access_token

    print("create_calendar_event invoked")
    print(f"google_access_token: {google_access_token}")

    if not google_access_token:
        return "Google Calendar authentication is required."

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
def get_calendar_events_today() -> str:
    global google_access_token

    print("get_calendar_events_today invoked")

    print(f"google_access_token: {google_access_token}")

    # Check if we already have a token
    if not google_access_token:
        return "Google Calendar authentication is required."

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


@requires_access_token(
    provider_name=get_ssm_parameter("/app/customersupport/agentcore/cognito_provider"),
    scopes=[],  # Optional unless required
    auth_flow="M2M",
)
async def _get_access_token_manually(*, access_token: str):
    global gateway_access_token
    gateway_access_token = access_token
    return access_token  # Update the global access token


async def on_auth_url(url: str):
    print(f"Authorization url: {url}")
    await response_queue.put(f"Authorization url: {url}")


SCOPES = ["https://www.googleapis.com/auth/calendar"]


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


async def agent_task(
    user_message: str, session_id: str, actor_id: str, access_token: str
):
    global agent
    global google_access_token

    if not access_token:
        raise RuntimeError("access_token is none")
    try:
        if agent is None:
            provider = AgentCoreMemoryToolProvider(
                memory_id=get_ssm_parameter("/app/customersupport/agentcore/memory_id"),
                actor_id=actor_id,
                session_id=session_id,
                namespace=f"summaries/{actor_id}/{session_id}",
            )

            memory_hook = MemoryHook(
                memory_client=memory_client,
                memory_id=get_ssm_parameter("/app/customersupport/agentcore/memory_id"),
                actor_id=actor_id,
                session_id=session_id,
            )

            agent = CustomerSupport(
                bearer_token=access_token,
                memory_hook=memory_hook,
                tools=[get_calendar_events_today, create_calendar_event]
                + provider.tools,
            )

        auth_keywords = ["authentication"]
        needs_auth = False
        async for chunk in agent.stream(user_query=user_message, session_id=session_id):
            needs_auth = any(
                keyword.lower() in chunk.lower() for keyword in auth_keywords
            )
            if needs_auth:
                break
            else:
                await response_queue.put(chunk)

        if needs_auth:
            # Trigger the 3LO authentication flow
            try:
                google_access_token = await need_token_3LO_async(access_token="")

                # Retry the agent call now that we have authentication
                async for chunk in agent.stream(
                    user_query=user_message, session_id=session_id
                ):
                    await response_queue.put(chunk)

            except Exception as auth_error:
                # print("Exception occurred:")
                # traceback.print_exc()
                print("auth_error:", auth_error)

    except Exception as e:
        logger.exception("Agent execution failed.")
        await response_queue.put(f"Error: {str(e)}")
    finally:
        await response_queue.finish()


@app.entrypoint
async def invoke(payload, context):
    user_message = payload["prompt"]
    actor_id = payload["actor_id"]

    session_id = context.session_id or str(uuid.uuid4())

    access_token = await _get_access_token_manually()

    task = asyncio.create_task(
        agent_task(
            user_message=user_message,
            session_id=session_id,
            access_token=access_token,
            actor_id=actor_id,
        )
    )

    async def stream_output():
        async for item in response_queue.stream():
            yield item
        await task  # Ensure task completion

    return stream_output()


if __name__ == "__main__":
    app.run()
