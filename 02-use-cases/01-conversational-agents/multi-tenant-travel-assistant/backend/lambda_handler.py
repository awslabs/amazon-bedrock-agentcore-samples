"""Lambda entry point for the mock TMC API.

Mangum adapts the ASGI app to Lambda's event model, so the same FastAPI
application serves `uvicorn` locally and API Gateway when deployed — no
per-environment branch in any router.

Storage is chosen here rather than inside the app: DynamoDB when table names are
present in the environment, otherwise the seeded in-memory store. That keeps the
app itself agnostic and makes local runs work with no configuration.

**Row-level isolation is also wired here.** When a tenant-scoped data role is
configured, a factory is attached that rebuilds the repository per request against credentials
scoped to that request's tenant. Wiring it at the edge rather than inside the app keeps
`app/` free of AWS assumptions — the in-memory path is untouched, so the whole test suite still
runs with no credentials.
"""

import os

from mangum import Mangum

from app.main import create_app


def _repository():
    """DynamoDB when configured, seeded in-memory otherwise."""
    prefix = os.environ.get("TABLE_PREFIX")
    if not prefix:
        from app.repository import InMemoryRepository
        from seed import seed

        return seed(InMemoryRepository())

    from app.dynamo_repository import DynamoRepository

    return DynamoRepository(table_prefix=prefix)


def _scoped_repository_factory():
    """Per-request tenant-scoped repositories, or `None` when row-scoping is off.

    Returning `None` rather than a pass-through factory keeps the decision visible in one
    place: `get_repository` falls back to the shared instance, and local runs behave exactly as
    before.

    The repository object is cheap — `boto3.resource` plus six `Table` handles — and the
    underlying credentials are cached per distinct session, so the per-request cost is object
    construction rather than an STS call.
    """
    prefix = os.environ.get("TABLE_PREFIX")
    if not prefix:
        return None

    from app.tenant_credentials import is_enabled, scoped_dynamodb

    if not is_enabled():
        # **Fail the cold start rather than serve every tenant from the function's own role.**
        #
        # `TABLE_PREFIX` set means DynamoDB mode — a deployed backend. In that mode row-scoping is
        # the isolation boundary, and the execution role's own grants are deliberately broad *across
        # tenants* (see `mock-tmc-api.ts`) because one backend serves every customer. So returning
        # `None` here used to mean: no scoped credentials, fall back to the shared repository, and
        # answer every request with credentials that can read any tenant's rows — with no error and
        # no log line saying the boundary was not in effect.
        #
        # That is the one direction this must never fail in. An absent `TENANT_DATA_ROLE_ARN` is a
        # misconfiguration, and a misconfiguration that silently removes tenant isolation is worse
        # than an outage: the deploy goes green and every check that does not specifically probe
        # `LeadingKeys` still passes.
        #
        # Local and in-memory runs are unaffected — they have no `TABLE_PREFIX`, so they returned
        # `None` above. The seed script is unaffected too: it constructs its own repository and
        # never imports this module.
        raise RuntimeError(
            "TABLE_PREFIX is set (DynamoDB mode) but tenant row-scoping is not configured: "
            "TENANT_DATA_ROLE_ARN is missing. Refusing to start rather than serving requests with "
            "credentials that reach every tenant's partitions."
        )

    from app.dynamo_repository import DynamoRepository

    def factory(tenant_id: str, session_id: str | None = None, traveler_id: str | None = None):
        """Tenant scopes the credentials; session and traveller label them for the audit trail."""
        return DynamoRepository(
            table_prefix=prefix,
            dynamodb_resource=scoped_dynamodb(tenant_id, session_id, traveler_id),
        )

    return factory


def _build_app():
    app = create_app(_repository())
    # Read by `get_repository`; absent means "no row-scoping configured".
    app.state.scoped_repository_factory = _scoped_repository_factory()
    return app


# Built once per container, reused across invocations — the reference fixtures and
# any DynamoDB clients are then paid for on cold start only.
handler = Mangum(_build_app(), lifespan="off")
