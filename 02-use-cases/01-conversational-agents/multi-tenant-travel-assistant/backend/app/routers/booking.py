"""Search and booking.

Two shapes of behaviour live here, and the difference matters:

**Search** is computed per request and never stored. The same query returns the
same options, because eval assertions and cost baselines depend on it.

**Booking** is stateful, and deliberately so. Pricing an option writes a *held
offer* — a frozen fare with an expiry, the mock equivalent of a GDS PNR. Only the
`offer_id` goes to the client; on confirm the server re-prices, re-checks
ownership and expiry, then books. A price in a client payload would be forgeable,
so none is ever sent.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ..dependencies import (
    GenerationModeDep,
    RepositoryDep,
    ScenarioFlagsDep,
    TenantConfigDep,
    TenantIdDep,
    TravelerIdDep,
)
from ..models import (
    OFFER_TTL_MINUTES,
    AirSearchRequest,
    AirSearchResponse,
    CancellationTerms,
    HeldOffer,
    HotelSearchRequest,
    HotelSearchResponse,
    Money,
    OfferStatus,
    Reservation,
    ReservationStatus,
    TravelKind,
)
from ..reference import AmbiguousPlaceError, UnknownPlaceError
from ..repository import Repository
from ..service import booking as booking_service
from ..service import search as search_service

router = APIRouter(prefix="/v1/booking", tags=["booking"])


class HoldRequest(BaseModel):
    """Price and hold one option from a previous search."""

    kind: TravelKind
    option_id: str
    # The search parameters are echoed so the option can be regenerated. Nothing
    # is trusted from the client beyond identifiers.
    origin: str | None = None
    destination: str
    depart_on: str | None = None
    check_in: str | None = None
    check_out: str | None = None


class HoldResponse(BaseModel):
    """What the client receives: a handle, an expiry, and a display price.

    The price is shown so a card can render it, but it is never accepted back —
    confirm re-derives it server-side.
    """

    offer_id: str
    expires_at: datetime
    display_price: Money
    description: str
    policy_status: str


class ConfirmRequest(BaseModel):
    """Only the handle. Everything else is re-derived."""

    offer_id: str


@router.post("/search/air", response_model=AirSearchResponse)
def search_air(
    request: AirSearchRequest,
    tenant_id: TenantIdDep,
    config: TenantConfigDep,
    repo: RepositoryDep,
    mode: GenerationModeDep,
    flags: ScenarioFlagsDep,
    traveler_id: TravelerIdDep = None,
) -> AirSearchResponse:
    """Policy-annotated flight options.

    An unsupported airport is a 404 with suggestions, never an invented route —
    a plausible-looking wrong duration would discredit every other answer.

    **The traveller matters here, not just the tenant.** An entitlement cabin rule
    ("business on every 4th international trip") is answered from *travel history*,
    so without the traveller the annotation silently falls back to not-entitled and
    every option reads as economy-only. Omitting it is not a smaller answer, it is a
    wrong one — which is why it arrives on the same verified header as everywhere else.
    """
    try:
        return search_service.search_air(repo, tenant_id, config, request, mode, traveler_id, flags)
    except search_service.MissingOriginError:
        # 400 with a question in it, not a 422. The tool omits `origin` by design, so a
        # schema-shaped
        # rejection would tell the model it had built a bad call when what is actually missing is a
        # fact only the traveller has.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Which airport are you flying from?"},
        ) from None
    except AmbiguousPlaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"'{exc.query}' could be more than one place — which did you mean?",
                "candidates": exc.candidates,
            },
        ) from None
    except UnknownPlaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"'{exc.query}' is not a supported airport in this demo",
                "suggestions": exc.suggestions,
            },
        ) from None


@router.post("/search/hotels", response_model=HotelSearchResponse)
def search_hotels(
    request: HotelSearchRequest,
    tenant_id: TenantIdDep,
    config: TenantConfigDep,
    repo: RepositoryDep,
    mode: GenerationModeDep,
    flags: ScenarioFlagsDep,
    traveler_id: TravelerIdDep = None,
) -> HotelSearchResponse:
    """Policy-annotated hotel options.

    Preferred chains come from the traveller's profile when one is supplied, so
    "my preferred hotels" needs no extra round trip.
    """
    try:
        return search_service.search_hotels(
            repo, tenant_id, config, request, mode, traveler_id, flags
        )
    except AmbiguousPlaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"'{exc.query}' could be more than one place — which did you mean?",
                "candidates": exc.candidates,
            },
        ) from None
    except UnknownPlaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"'{exc.query}' is not a supported destination in this demo",
                "suggestions": exc.suggestions,
            },
        ) from None


@router.post("/hold", response_model=HoldResponse)
def hold_offer(
    request: HoldRequest,
    tenant_id: TenantIdDep,
    config: TenantConfigDep,
    repo: RepositoryDep,
    mode: GenerationModeDep,
    flags: ScenarioFlagsDep,
    traveler_id: TravelerIdDep = None,
) -> HoldResponse:
    """Freeze a fare and return a handle.

    Requires a traveller: a hold belongs to someone, and confirm checks that the
    caller is that someone.
    """
    if not traveler_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Traveler-Id is required to hold an offer",
        )
    try:
        offer = booking_service.hold(
            repo, tenant_id, config, traveler_id, request, mode, _now(), flags
        )
    # **Caught before the not-found handler, because it is the more specific diagnosis.** A caller
    # whose parameters contradict the option id must not be told the option is gone: it never
    # existed
    # under those parameters, so searching again reproduces the contradiction rather than resolving
    # it. 422 rather than 404 — the request is unprocessable, not the resource absent.
    except booking_service.OptionParamsMismatchError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "that option id does not belong to the search details supplied — re-send the exact "
                "destination and dates from the search that produced it"
            ),
        ) from None
    except booking_service.OptionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="that option is no longer available; search again",
        ) from None
    except AmbiguousPlaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"'{exc.query}' could be more than one place — which did you mean?",
                "candidates": exc.candidates,
            },
        ) from None
    except UnknownPlaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"'{exc.query}' is not supported", "suggestions": exc.suggestions},
        ) from None

    return HoldResponse(
        offer_id=offer.offer_id,
        expires_at=offer.expires_at,
        display_price=offer.frozen_price,
        description=offer.description,
        policy_status=offer.policy_status.value,
    )


@router.post("/confirm", response_model=Reservation)
def confirm_booking(
    request: ConfirmRequest,
    tenant_id: TenantIdDep,
    config: TenantConfigDep,
    repo: RepositoryDep,
    mode: GenerationModeDep,
    flags: ScenarioFlagsDep,
    traveler_id: TravelerIdDep = None,
) -> Reservation:
    """Book a held offer.

    Every failure mode here is a deliberate refusal rather than a best effort:
    a foreign or unknown handle, an expired hold, a consumed hold, or a fare that
    has moved. The last one returns 409 with the new price so the agent can ask
    again — it must never silently charge a different amount.
    """
    if not traveler_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Traveler-Id is required to confirm",
        )
    try:
        return booking_service.confirm(
            repo, tenant_id, config, traveler_id, request.offer_id, mode, _now(), flags
        )
    except booking_service.OfferNotFoundError:
        # Also covers another tenant's or traveller's handle: indistinguishable
        # from a handle that never existed, which is the point.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="offer not found"
        ) from None
    except booking_service.OfferExpiredError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="that offer has expired; please search again",
        ) from None
    except booking_service.OfferAlreadyUsedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="that offer has already been booked",
        ) from None
    except booking_service.PriceMovedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "the fare changed before confirmation",
                "previous_price": str(exc.previous),
                "current_price": str(exc.current),
                "offer_id": exc.offer_id,
            },
        ) from None


@router.get("/reservations", response_model=list[Reservation])
def list_reservations(
    tenant_id: TenantIdDep,
    repo: RepositoryDep,
    traveler_id: TravelerIdDep = None,
) -> list[Reservation]:
    return repo.reservations(tenant_id, traveler_id)


@router.get("/reservations/{booking_ref}/cancellation-terms", response_model=CancellationTerms)
def cancellation_terms(
    booking_ref: str,
    tenant_id: TenantIdDep,
    repo: RepositoryDep,
) -> CancellationTerms:
    """Terms are shown before any cancellation happens — never after."""
    reservation = _require_reservation(repo, tenant_id, booking_ref)
    return booking_service.cancellation_terms(reservation)


@router.post("/reservations/{booking_ref}/cancel", response_model=Reservation)
def cancel_reservation(
    booking_ref: str,
    tenant_id: TenantIdDep,
    repo: RepositoryDep,
) -> Reservation:
    """Cancel a booking. Idempotent: cancelling twice is not an error."""
    reservation = _require_reservation(repo, tenant_id, booking_ref)
    if reservation.status is ReservationStatus.CANCELLED:
        return reservation
    reservation.status = ReservationStatus.CANCELLED
    repo.put_reservation(reservation)
    return reservation


def _require_reservation(repo: Repository, tenant_id: str, booking_ref: str) -> Reservation:
    reservation = repo.reservation(tenant_id, booking_ref)
    if reservation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reservation not found")
    return reservation


def _now() -> datetime:
    """Naive UTC, matching the datetimes the generator produces."""
    return datetime.now(UTC).replace(tzinfo=None)


__all__ = ["router", "OFFER_TTL_MINUTES", "HeldOffer", "OfferStatus", "timedelta"]
