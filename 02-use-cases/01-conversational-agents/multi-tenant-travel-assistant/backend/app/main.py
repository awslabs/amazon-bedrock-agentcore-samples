"""The mock TMC API.

Stands in for the travel platform a corporate travel management company already
runs. Nothing in `agent/`, `tools/`, or `frontend/` imports from here — tool
Lambdas call it over HTTP, exactly as they would call a real one. Replacing this
folder with your own API is the intended path.

The repository is injected at construction, so the same app serves tests
(in-memory, seeded) and deployment (DynamoDB) without a branch in the routers.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from generator import SimulatedTimeout

from .repository import InMemoryRepository, Repository
from .routers import ALL_ROUTERS

API_TITLE = "AnyCompany Travel — Mock TMC API"
API_VERSION = "1.0.0"

DESCRIPTION = """\
Mock travel platform for this sample: trips, bookings, traveler profiles,
and policy for two fictional corporate tenants.

Tenant arrives as an `X-Tenant-Id` header. In the deployed sample the caller is a
tool Lambda that derives it from a verified assertion — never from anything the
model chose.
"""


def create_app(repository: Repository | None = None) -> FastAPI:
    """Build the app around a repository.

    Defaults to a seeded in-memory store so `uvicorn app.main:app` and the test
    suite both work with no AWS credentials and no deployed stack.
    """
    app = FastAPI(title=API_TITLE, version=API_VERSION, description=DESCRIPTION)
    app.state.repository = repository or _seeded_default()

    for router in ALL_ROUTERS:
        app.include_router(router)

    @app.exception_handler(SimulatedTimeout)
    def _simulated_timeout(request: Request, exc: SimulatedTimeout) -> JSONResponse:
        """A simulated stall, returned as the gateway timeout it stands in for.

        **Registered once here rather than caught per route**, because a stall is specific to no
        endpoint, and a route that forgot the `except` would return 500 — which the tool layer
        reports as "the system is broken" rather than "it did not answer in time". That distinction
        is what suite G checks: the honest response to a timeout is a bounded retry and then a
        handoff, and the agent picks that path from the status it sees.
        """
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"detail": {"message": str(exc), "retryable": True}},
        )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": API_TITLE, "version": API_VERSION}

    return app


def _seeded_default() -> Repository:
    """Imported lazily so `app` doesn't depend on the seed package at module load."""
    from seed import seed

    return seed(InMemoryRepository())


app = create_app()
