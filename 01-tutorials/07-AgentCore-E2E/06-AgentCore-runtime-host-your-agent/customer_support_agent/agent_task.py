import logging

from bedrock_agentcore.memory import MemoryClient

from customer_support_agent.agent import CustomerSupport  # Your custom agent class
from customer_support_agent.context import CustomerSupportContext
from customer_support_agent.memory_hook_provider import MemoryHook
from customer_support_agent.tools.google import (
    create_calendar_event,
    get_calendar_events_today,
)
from customer_support_agent.utils import get_ssm_parameter

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

memory_client = MemoryClient()


async def agent_task(user_message: str, session_id: str, actor_id: str):
    agent = CustomerSupportContext.get_agent_ctx()

    response_queue = CustomerSupportContext.get_response_queue_ctx()
    gateway_access_token = CustomerSupportContext.get_gateway_token_ctx()

    if not gateway_access_token:
        raise RuntimeError("Gateway Access token is none")
    try:
        if agent is None:
            memory_hook = MemoryHook(
                memory_client=memory_client,
                memory_id=get_ssm_parameter("/app/customersupport/agentcore/memory_id"),
                actor_id=actor_id,
                session_id=session_id,
            )

            agent = CustomerSupport(
                bearer_token=gateway_access_token,
                memory_hook=memory_hook,
                tools=[get_calendar_events_today, create_calendar_event],
            )

            CustomerSupportContext.set_agent_ctx(agent)

        async for chunk in agent.stream(user_query=user_message):
            await response_queue.put(chunk)

    except Exception as e:
        logger.exception("Agent execution failed.")
        await response_queue.put(f"Error: {str(e)}")
    finally:
        await response_queue.finish()
