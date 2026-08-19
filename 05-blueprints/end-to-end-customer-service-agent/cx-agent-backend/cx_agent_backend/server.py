"""FastAPI application definition"""

from datetime import datetime
import time
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
import structlog

from cx_agent_backend.infrastructure.config.container import Container
from cx_agent_backend.infrastructure.config.settings import settings
from cx_agent_backend.presentation.api.conversation_router import (
    router as conversation_router,
)


logger = structlog.get_logger()


def create_app() -> FastAPI:
    """Create FastAPI application."""
    # Initialize container
    container = Container()

    # Create FastAPI app
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description=settings.api_description,
        debug=settings.debug,
    )

    # Wire container
    container.wire(
        modules=[
            "cx_agent_backend.presentation.api.conversation_router",
        ]
    )

    # Include routers
    app.include_router(conversation_router)

    # Add AgentCore-compliant endpoints directly to app
    @app.get("/ping")
    async def ping():
        """Container health check endpoint"""

        return {"status": "Healthy", "time_of_last_update": int(time.time())}

    @app.post("/invocations")
    async def invocations(request: dict, http_request: Request):
        """AgentCore-compatible endpoint to invoke the agent (send message & get response)"""

        # Get conversation service from container
        conversation_service = container.conversation_service()

        # Extract session information
        # session_id = http_request.headers.get("x-amzn-bedrock-agentcore-runtime-session-id")

        # Extract data from input object
        input_data = request.get("input", {})
        prompt = input_data.get("prompt")
        feedback = input_data.get("feedback")
        conversation_id_str = input_data.get("conversation_id")
        user_id = input_data.get("user_id")
        langfuse_tags = input_data.get("langfuse_tags", [])
        jwt_token = input_data.get("jwt_token")  # Extract JWT token from input

        # Convert conversation_id to UUID
        try:
            conversation_id = UUID(conversation_id_str) if conversation_id_str else None
        except (ValueError, TypeError):
            logger.exception(
                "Failed to parse provided Conversation ID '%s' to valid UUID - Treating as empty",
                conversation_id_str,
            )
            conversation_id = None

        if not prompt and not feedback:
            raise HTTPException(
                status_code=400,
                detail="Either prompt or feedback must be provided in input.",
            )

        try:
            # Process feedback if provided
            if feedback:
                feedback_score = 1 if feedback.get("score", 0) > 0.5 else 0
                await conversation_service.log_feedback(
                    user_id,
                    feedback.get("session_id"),
                    feedback.get("run_id"),
                    feedback_score,
                    feedback.get("comment"),
                )

            # If no prompt, this is feedback-only request
            if not prompt:
                return {
                    "output": {
                        "message": "Feedback received",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                }

            message, tools_used = await conversation_service.send_message(
                conversation_id=conversation_id,
                user_id=user_id,
                content=prompt,
                model=settings.default_model,
                langfuse_tags=langfuse_tags,
                jwt_token=jwt_token,
            )

            # Return agent contract format with metadata
            output = {
                "message": message.content,
                "timestamp": datetime.utcnow().isoformat(),
                "model": settings.default_model,
            }

            # Add metadata if available
            if hasattr(message, "metadata") and message.metadata:
                output["metadata"] = message.metadata
                # Extract trace_id from metadata if available
                if "trace_id" in message.metadata:
                    output["trace_id"] = message.metadata["trace_id"]
                    print(
                        f"DEBUG: Added trace_id to output: {message.metadata['trace_id']}"
                    )
                else:
                    print(
                        f"DEBUG: No trace_id in metadata. Available keys: {list(message.metadata.keys())}"
                    )
            else:
                print("DEBUG: No metadata available in message")

            print(f"DEBUG: Final output keys: {list(output.keys())}")
            return {"output": output}

        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to process request: {str(e)}"
            )

    # Store container in app state
    app.container = container

    logger.info("Application created", settings=settings.model_dump())

    return app
