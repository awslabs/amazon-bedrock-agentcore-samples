"""The calling tenant's own configuration.

**Why the tool layer needs this.** How far the agent may take a booking is a per-customer decision:
`confirm_in_chat` means it books on explicit confirmation, `handoff` means it assembles everything
and passes a checkout link. That difference changes which *actions* a booking summary card carries —
so the tool has to know it, and it must come from the tenant record rather than being guessed or
configured into the tool.

Deliberately scoped to the caller's own tenant, with no id in the path: there is no legitimate
reason for one customer to read another's settings, and an endpoint that takes a tenant id is an
endpoint someone will eventually call with the wrong one.
"""

from fastapi import APIRouter

from ..dependencies import TenantConfigDep
from ..models import TenantConfig

router = APIRouter(prefix="/v1/config", tags=["config"])


@router.get("", response_model=TenantConfig)
def get_config(config: TenantConfigDep) -> TenantConfig:
    """Settings for the calling tenant: currency, booking mode, escalation queue."""
    return config
