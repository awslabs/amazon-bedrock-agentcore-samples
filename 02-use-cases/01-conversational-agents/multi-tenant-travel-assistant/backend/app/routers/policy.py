"""Policy endpoints.

Returns the tenant's policy record whole: the typed core the agent's eligibility
tool computes on, plus the loose rules the model narrates. One read serves both —
"what's my hotel cap?" and "can I expense wifi?" come from the same payload.

What lives in the knowledge base instead: exceptions, approval process, and the
prose no schema captures. That's the third tier, and it's deliberately not here.
"""

from fastapi import APIRouter, HTTPException, status

from generator import Scenario, SimulatedTimeout

from ..dependencies import RepositoryDep, ScenarioFlagsDep, TenantIdDep
from ..models import TravelPolicy
from ..service.drift import apply_to_policy

router = APIRouter(prefix="/v1/policy", tags=["policy"])


@router.get("", response_model=list[TravelPolicy])
def list_policies(
    tenant_id: TenantIdDep, repo: RepositoryDep, flags: ScenarioFlagsDep
) -> list[TravelPolicy]:
    """Every policy topic for the tenant."""
    if Scenario.TIMEOUT in flags:
        raise SimulatedTimeout("upstream policy service did not respond")
    return [apply_to_policy(policy, flags) for policy in repo.policies(tenant_id)]


@router.get("/{topic}", response_model=TravelPolicy)
def get_policy(
    topic: str, tenant_id: TenantIdDep, repo: RepositoryDep, flags: ScenarioFlagsDep
) -> TravelPolicy:
    """One topic: air, hotel, or general.

    A missing topic is a 404 rather than an empty policy — an empty policy would
    read as "no restrictions", which is the most dangerous possible default.
    """
    # **Before the read, so the scenario cannot be mistaken for a missing record.** A stalled
    # upstream and an absent policy are different answers, and the agent must not turn the first
    # into "your company has no policy".
    if Scenario.TIMEOUT in flags:
        raise SimulatedTimeout("upstream policy service did not respond")
    policy = repo.policy(tenant_id, topic)
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no {topic} policy for this tenant",
        )
    return apply_to_policy(policy, flags)
