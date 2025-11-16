from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InternalError,
    InvalidParamsError,
    Part,
    TaskState,
    TextPart,
)
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
import logging

logger = logging.getLogger(__name__)


class MonitoringAgentExecutor(AgentExecutor):
    """
    Agent executor for the Strands-based monitoring agent
    """

    def __init__(self):
        """Initialize the executor"""
        self._agent = None
        self._active_tasks = {}
        logger.info("MonitoringAgentExecutor initialized")

    async def _get_agent(self):
        """Get the agent instance (initialized in main.py)"""
        # Import here to avoid circular dependency
        from main import _a2a_server

        if _a2a_server is None:
            raise RuntimeError("Agent not initialized")

        return _a2a_server.agent

    async def _execute_streaming(
        self, agent, user_message: str, updater: TaskUpdater, task_id: str
    ) -> None:
        """Execute agent with streaming and update task status incrementally."""
        accumulated_text = ""

        try:
            # Use the strands agent's run method
            response = agent.run(user_message)

            # Get the final response text
            if hasattr(response, 'content') and response.content:
                for content_block in response.content:
                    if hasattr(content_block, 'text'):
                        accumulated_text += content_block.text

            # Send final update
            if accumulated_text:
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(
                        accumulated_text,
                        updater.context_id,
                        updater.task_id,
                    ),
                )

                # Add final result as artifact
                await updater.add_artifact(
                    [Part(root=TextPart(text=accumulated_text))],
                    name="agent_response",
                )

            await updater.complete()

        except Exception as e:
            logger.error(f"Error in streaming execution: {e}", exc_info=True)
            raise

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Execute the agent's logic for a given request context.
        """
        # Extract session and actor IDs from headers
        session_id = None

        if context.call_context:
            headers = context.call_context.state.get("headers", {})
            session_id = headers.get("x-amzn-bedrock-agentcore-runtime-session-id")
            actor_id = headers.get("x-amzn-bedrock-agentcore-runtime-custom-actorid")

        if not actor_id:
            logger.error("Actor ID is not set")
            raise ServerError(error=InvalidParamsError())

        if not session_id:
            logger.error("Session ID is not set")
            raise ServerError(error=InvalidParamsError())

        # Get or create task
        task = context.current_task
        if not task:
            logger.info("No current task, creating new task")
            task = new_task(context.message)  # type: ignore
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        task_id = context.task_id

        try:
            logger.info(f"Executing task {task.id}")

            # Extract user input
            user_message = context.get_user_input()
            if not user_message:
                logger.error("No user message found in context")
                raise ServerError(error=InvalidParamsError())

            logger.info(f"User message: '{user_message}'")

            # Get the agent instance
            agent = await self._get_agent()

            # Mark task as active
            self._active_tasks[task_id] = True

            # Execute the agent
            logger.info("Calling agent...")
            await self._execute_streaming(agent, user_message, updater, task_id)

            logger.info(f"Task {task_id} completed successfully")

        except ServerError:
            # Re-raise ServerError as-is
            raise
        except Exception as e:
            logger.error(f"Error executing task {task_id}: {e}", exc_info=True)
            raise ServerError(error=InternalError()) from e
        finally:
            # Clean up task from active tasks
            self._active_tasks.pop(task_id, None)

    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Request the agent to cancel an ongoing task.
        """
        task_id = context.task_id
        logger.info(f"Cancelling task {task_id}")

        try:
            # Mark task as cancelled
            self._active_tasks[task_id] = False

            task = context.current_task
            if task:
                updater = TaskUpdater(event_queue, task.id, task.context_id)
                await updater.cancel()
                logger.info(f"Task {task_id} cancelled successfully")
            else:
                logger.warning(f"No task found for task_id {task_id}")

        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}", exc_info=True)
            raise ServerError(error=InternalError()) from e
