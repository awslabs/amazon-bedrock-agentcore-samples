"""Tool-layer failures.

Distinct types because the *caller* handles them differently, not for taxonomy's
sake: a refusal is something the model should tell the user about, while a
configuration error is something an operator must fix. Collapsing them would mean
the model apologising for a missing environment variable.
"""


class ToolError(Exception):
    """Base for anything a tool can fail with."""


class MissingIdentityError(ToolError):
    """No verified tenant on the request.

    Never surfaced to the model as a normal answer. It means the interceptor did not
    run or its headers were not forwarded — an infrastructure fault, and one that
    must fail loudly rather than degrade into an unscoped read.
    """


class BackendError(ToolError):
    """The backend refused or failed.

    Carries the status so the handler can distinguish "not found" (an answer the
    model can convey) from "500" (a failure it should admit to rather than paper
    over).
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status
