"""Shared FastAPI dependencies.

Every router resolves the same three things through here rather than each
re-implementing them: the repository, the calling tenant, and that tenant's
configuration.

**Tenant arrives as a header.** In the deployed sample the caller is a tool
Lambda that derives it from a verified assertion, so the value is never something
the model chose — but the API's shape doesn't change, because this is what real
API auth already does. Keeping it in one dependency means swapping the source
later touches one function, not five routers.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from generator.scenarios import Scenario, ScenarioFlags

from .models import GenerationMode, TenantConfig
from .repository import Repository, TenantNotFoundError

TENANT_HEADER = "X-Tenant-Id"
TRAVELER_HEADER = "X-Traveler-Id"
MODE_HEADER = "X-Generation-Mode"

# The conversation this request belongs to. **Audit correlation only, never a trust input:** it
# becomes an STS session tag so a CloudTrail data event can be traced back to one conversation,
# and no policy keys off it. That is why it can be forwarded from upstream unverified.
SESSION_HEADER = "X-Session-Id"


def get_repository(request: Request) -> Repository:
    """The repository chosen at app construction — in-memory or DynamoDB.

    **This is also where row-level isolation attaches.** When a tenant-scoped
    data role is configured, a DynamoDB repository is rebuilt per request against credentials
    that can only reach that tenant's partitions (`dynamodb:LeadingKeys` pinned to the session
    tag). Doing it in this one dependency is what keeps every router unchanged — and means a new
    router cannot forget to be scoped, because there is no unscoped path to reach for.

    The tenant comes from the verified `X-Tenant-Id` header, so the *tag value* — the security
    boundary — is never something a caller or a model supplied as data.

    The session and traveller are also passed through, but only as **audit dimensions** on the
    same STS session: they let CloudTrail say *which conversation, on whose behalf* caused a row
    read. Keeping them on the one `AssumeRole` that already happens means the audit trail and the
    isolation boundary share a single mechanism rather than needing a second instrumentation path.
    """
    repository = request.app.state.repository

    scoped_factory = getattr(request.app.state, "scoped_repository_factory", None)
    if scoped_factory is None:
        return repository

    tenant_id = request.headers.get(TENANT_HEADER)
    if not tenant_id:
        # No tenant means the request is going to fail authentication a moment from now
        # (`get_tenant_id` raises 401). Assuming a role for an absent tenant would be a
        # pointless STS call on a request that cannot succeed.
        return repository

    return scoped_factory(
        tenant_id,
        request.headers.get(SESSION_HEADER),
        request.headers.get(TRAVELER_HEADER),
    )


def get_tenant_id(
    x_tenant_id: Annotated[str | None, Header(alias=TENANT_HEADER)] = None,
) -> str:
    """The tenant this request acts for. Absent means unauthenticated, not "any"."""
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"{TENANT_HEADER} header is required",
        )
    return x_tenant_id


def get_traveler_id(
    x_traveler_id: Annotated[str | None, Header(alias=TRAVELER_HEADER)] = None,
) -> str | None:
    """Who the request is on behalf of.

    Optional: some endpoints are tenant-wide. Arranger authorisation (may this
    traveller act for that one?) is enforced by Cedar at the tool layer, not here
    — the backend's job is to scope data, not to adjudicate roles.
    """
    return x_traveler_id


def get_generation_mode(
    x_generation_mode: Annotated[str | None, Header(alias=MODE_HEADER)] = None,
) -> GenerationMode:
    """FIXTURE by default so tests and CI are reproducible without opting in."""
    if not x_generation_mode:
        return GenerationMode.FIXTURE
    try:
        return GenerationMode(x_generation_mode.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown generation mode: {x_generation_mode}",
        ) from None


def get_validated_tenant_id(
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> str:
    """The calling tenant, proven to exist.

    Routers depend on this rather than the raw header so an unknown tenant fails
    identically everywhere. Returning an empty list instead would make a typo
    indistinguishable from a tenant that genuinely has no data.
    """
    try:
        repo.tenant_config(tenant_id)
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown tenant: {tenant_id}",
        ) from None
    return tenant_id


def get_tenant_config(
    tenant_id: Annotated[str, Depends(get_tenant_id)],
    repo: Annotated[Repository, Depends(get_repository)],
) -> TenantConfig:
    """Resolve tenant configuration, or 404 for an unknown tenant.

    An unrecognised tenant is an error rather than an empty result — silently
    returning nothing would make a typo look like a tenant with no data.
    """
    try:
        return repo.tenant_config(tenant_id)
    except TenantNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown tenant: {tenant_id}",
        ) from None


def get_scenario_flags(
    request: Request,
    repo: Annotated[Repository, Depends(get_repository)],
    tenant_id: Annotated[str, Depends(get_validated_tenant_id)],
) -> ScenarioFlags:
    """Simulated conditions armed for this conversation, if any.

    **Read from storage rather than from a header, and that is the whole point.** A header would let
    any caller put the backend into "every search times out" — including a caller who found the mock
    TMC's public URL, since a tenant header is all it asks for. Arming a scenario is instead a write
    to the offers table by something that already holds AWS credentials, and it is scoped to one
    session id and expires on its own.

    Unknown names are ignored rather than rejected: a stored row is not user input arriving on the
    request, and a scenario removed from the enum should stop firing, not start failing turns.
    """
    session_id = request.headers.get(SESSION_HEADER)
    names = repo.active_scenarios(tenant_id, session_id)
    known = {Scenario(name) for name in names if name in set(Scenario)}
    return ScenarioFlags(active=known)


# Aliases so router signatures stay readable.
RepositoryDep = Annotated[Repository, Depends(get_repository)]
TenantIdDep = Annotated[str, Depends(get_validated_tenant_id)]
TravelerIdDep = Annotated[str | None, Depends(get_traveler_id)]
TenantConfigDep = Annotated[TenantConfig, Depends(get_tenant_config)]
GenerationModeDep = Annotated[GenerationMode, Depends(get_generation_mode)]
ScenarioFlagsDep = Annotated[ScenarioFlags, Depends(get_scenario_flags)]
