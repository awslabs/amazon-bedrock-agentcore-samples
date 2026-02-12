"""Message models for frontend."""

from datetime import datetime
from typing import Dict

from pydantic import BaseModel


class Message(BaseModel):
    """Message model."""

    role: str
    content: str
    timestamp: datetime
    metadata: Dict = {}
