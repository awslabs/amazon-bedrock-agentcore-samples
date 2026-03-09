# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""OAuth callback service - FastAPI application."""

import logging

from fastapi import FastAPI

from backend.oauth_callback.app.config import get_settings
from backend.oauth_callback.app.routers import callback, health

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = FastAPI(
    title="OAuth Callback Service",
    description="Handles OAuth2 3LO callbacks from AgentCore Identity",
    version="1.0.0",
)

app.include_router(callback.router)
app.include_router(health.router)
