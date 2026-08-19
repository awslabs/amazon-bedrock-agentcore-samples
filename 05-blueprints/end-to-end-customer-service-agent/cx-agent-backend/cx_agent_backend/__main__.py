"""Main entrypoint for running the agent server (uvicorn-fronted FastAPI)"""

import uvicorn

from cx_agent_backend.infrastructure.config.settings import settings
from cx_agent_backend.server import create_app

uvicorn.run(
    create_app(),
    host=settings.host,
    port=settings.port,
    reload=settings.debug,
    log_level=settings.log_level.lower(),
)
