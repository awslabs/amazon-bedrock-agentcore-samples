"""Entry requirements — visa rules for a passport/destination pair.

**The passport country is read server-side from the traveller's profile, never accepted as input.**
Two reasons, and the second is the one that matters: it is PII the model has no need to handle, and
a caller who could supply it could get an answer for the wrong document. "Do I need a visa?" is a
question about *this* traveller's passport.

**A missing pair is "not on file", never "no visa required".** That distinction is the whole point
of this endpoint. An absent row means the demo has no data — and narrating that as "you're fine to
travel" is the failure mode that strands someone at a border. So the 404 is deliberate and the tool
is required to relay it as uncertainty.

Fictional data. A production system reads this from a licensed provider (IATA Timatic, Sherpa)
behind the same contract; the shape does not change.
"""

from fastapi import APIRouter, HTTPException, status

from ..dependencies import RepositoryDep, TenantIdDep, TravelerIdDep
from ..models import EntryRequirement
from ..reference import entry_requirement

router = APIRouter(prefix="/v1/entry-requirements", tags=["entry"])


@router.get("/{destination_country}", response_model=EntryRequirement)
def get_entry_requirement(
    destination_country: str,
    tenant_id: TenantIdDep,
    traveler_id: TravelerIdDep,
    repo: RepositoryDep,
) -> EntryRequirement:
    """Entry rules for the calling traveller's passport into `destination_country`."""
    if not traveler_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Traveler-Id is required — entry rules depend on the traveller's passport",
        )

    traveler = repo.traveler(tenant_id, traveler_id)
    if traveler is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="traveler not found")

    passports = traveler.passports or []
    if not passports:
        # Cannot answer rather than guess a nationality. A default passport country would produce a
        # confident answer for a document the traveller does not hold.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no passport on file for this traveller, so entry rules cannot be determined",
        )

    # The first passport on file. A dual-national holding two would need the tool to ask which, and
    # that is a product decision rather than something to assume here — noted rather than silently
    # picking the "best" one.
    passport_country = passports[0].country

    found = entry_requirement(passport_country, destination_country)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": (
                    f"no entry rules on file for a {passport_country} passport entering "
                    f"{destination_country.upper()}"
                ),
                # Named explicitly so the tool cannot mistake absence for permission.
                "meaning": "unknown, not unrestricted",
                "passport_country": passport_country,
            },
        )
    return found
