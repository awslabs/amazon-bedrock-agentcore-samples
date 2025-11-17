"""Data models for Code Interpreter."""

from pydantic import BaseModel, Field
from typing import Optional


class CodeIntExecutionResult(BaseModel):
    """Result model for code execution."""

    output: str
    code_int_session_id: str
    execution_time: float = Field(..., ge=0, description="Execution time in seconds")
    success: bool
    error: Optional[str] = None
