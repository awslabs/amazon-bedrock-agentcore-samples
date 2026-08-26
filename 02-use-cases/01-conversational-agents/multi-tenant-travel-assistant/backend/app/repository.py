"""Storage seam.

Two implementations sit behind one protocol: an in-memory store for tests and
local development, and a DynamoDB store for deployed use. Routers depend on the
protocol, never on either implementation, so the whole backend can be exercised
with `uv run pytest` before anything is deployed — a reader clones the repo and
sees the two-tenant contrast working without spending a cent.

**Every read is tenant-scoped, and that is not a convenience.** The signature
makes it impossible to fetch a traveller without saying which tenant you are
acting for, which is the shape the IAM layer enforces later: DynamoDB partition
keys are `TENANT#<id>` and `dynamodb:LeadingKeys` constrains that exact value.
Application-level scoping like this is the *first* line, not the only one —
The IAM condition exists precisely because app-level checks can be
argued around by a prompt-injected agent, and IAM cannot.
"""

from datetime import datetime
from typing import Protocol, runtime_checkable

from .models import (
    HeldOffer,
    OfferStatus,
    Reservation,
    TenantConfig,
    TravelerProfile,
    TravelPolicy,
    Trip,
)


class OfferConflictError(RuntimeError):
    """The offer was not in the state the caller believed it was.

    **Raised by storage, not by a check in application code, and that distinction is the point.**
    `confirm` reads the offer, decides it is holdable, and writes. Between the read and the write
    another request can do exactly the same thing — so a status check in Python is advice, not a
    guarantee, and two concurrent confirms both pass it. This is what a *conditional* write reports
    when it loses that race, which is the only place the answer can be authoritative.

    The service maps it onto the same 409 a sequential double-confirm already produced, so the
    contract does not change: the second confirmation is refused. What changes is that it is now
    refused when the two arrive at once, which is when money is actually at stake.
    """


class TenantNotFoundError(LookupError):
    """Raised for an unknown tenant — never silently treated as empty."""


@runtime_checkable
class Repository(Protocol):
    """What the routers need from storage. Deliberately small."""

    def tenant_config(self, tenant_id: str) -> TenantConfig: ...

    def policy(self, tenant_id: str, topic: str) -> TravelPolicy | None: ...

    def policies(self, tenant_id: str) -> list[TravelPolicy]: ...

    def traveler(self, tenant_id: str, traveler_id: str) -> TravelerProfile | None: ...

    def travelers(self, tenant_id: str) -> list[TravelerProfile]: ...

    def trips(self, tenant_id: str, traveler_id: str | None = None) -> list[Trip]: ...

    def trip(self, tenant_id: str, trip_id: str) -> Trip | None: ...

    def put_offer(self, offer: HeldOffer) -> None: ...

    def offer(self, tenant_id: str, offer_id: str) -> HeldOffer | None: ...

    def put_reservation(self, reservation: Reservation) -> None: ...

    def reservation(self, tenant_id: str, booking_ref: str) -> Reservation | None: ...

    def reservations(self, tenant_id: str, traveler_id: str | None = None) -> list[Reservation]: ...

    def consume_offer(self, offer: HeldOffer, reservation: Reservation) -> None: ...

    def active_scenarios(self, tenant_id: str, session_id: str | None) -> set[str]: ...

    def put_scenarios(self, tenant_id: str, session_id: str, scenarios: set[str]) -> None: ...


class InMemoryRepository:
    """Dict-backed store for tests, local dev, and the seeded fixtures.

    Keys mirror the DynamoDB layout (`TENANT#<id>` as the outer key) so the
    DynamoDB implementation is a mechanical translation rather than a redesign.
    """

    def __init__(self) -> None:
        self._configs: dict[str, TenantConfig] = {}
        self._policies: dict[tuple[str, str], TravelPolicy] = {}
        self._travelers: dict[tuple[str, str], TravelerProfile] = {}
        self._trips: dict[tuple[str, str], Trip] = {}
        self._offers: dict[tuple[str, str], HeldOffer] = {}
        self._reservations: dict[tuple[str, str], Reservation] = {}
        self._scenarios: dict[tuple[str, str], set[str]] = {}

    # --- writes (used by the seed script and the booking flow) ---

    def put_tenant_config(self, config: TenantConfig) -> None:
        self._configs[config.tenant_id] = config

    def put_policy(self, policy: TravelPolicy) -> None:
        self._policies[(policy.tenant_id, policy.topic)] = policy

    def put_traveler(self, traveler: TravelerProfile) -> None:
        self._travelers[(traveler.tenant_id, traveler.traveler_id)] = traveler

    def put_trip(self, trip: Trip) -> None:
        self._trips[(trip.tenant_id, trip.trip_id)] = trip

    def put_offer(self, offer: HeldOffer) -> None:
        self._offers[(offer.tenant_id, offer.offer_id)] = offer

    def put_reservation(self, reservation: Reservation) -> None:
        self._reservations[(reservation.tenant_id, reservation.booking_ref)] = reservation

    def consume_offer(self, offer: HeldOffer, reservation: Reservation) -> None:
        """Mark the offer consumed and store its reservation, or raise.

        **The in-memory store models the condition deliberately, even though a dict has no
        concurrency.** Every test in this repo runs against this class, so a guarantee implemented
        only in `DynamoRepository` is a guarantee with no test coverage — the next refactor drops it
        and nothing fails. What is asserted here is the *contract*: consuming an offer that is not
        held is an error. That the real store enforces it atomically is proven once, against the
        deployment.
        """
        stored = self._offers.get((offer.tenant_id, offer.offer_id))
        if stored is None or stored.status is not OfferStatus.HELD:
            raise OfferConflictError(offer.offer_id)
        if (reservation.tenant_id, reservation.booking_ref) in self._reservations:
            raise OfferConflictError(offer.offer_id)
        stored.status = OfferStatus.CONSUMED
        self._reservations[(reservation.tenant_id, reservation.booking_ref)] = reservation

    def put_scenarios(self, tenant_id: str, session_id: str, scenarios: set[str]) -> None:
        self._scenarios[(tenant_id, session_id)] = set(scenarios)

    def active_scenarios(self, tenant_id: str, session_id: str | None) -> set[str]:
        if not session_id:
            return set()
        return set(self._scenarios.get((tenant_id, session_id), set()))

    # --- reads (all tenant-scoped) ---

    def tenant_config(self, tenant_id: str) -> TenantConfig:
        if tenant_id not in self._configs:
            raise TenantNotFoundError(tenant_id)
        return self._configs[tenant_id]

    def policy(self, tenant_id: str, topic: str) -> TravelPolicy | None:
        return self._policies.get((tenant_id, topic))

    def policies(self, tenant_id: str) -> list[TravelPolicy]:
        return [p for (t, _), p in self._policies.items() if t == tenant_id]

    def traveler(self, tenant_id: str, traveler_id: str) -> TravelerProfile | None:
        return self._travelers.get((tenant_id, traveler_id))

    def travelers(self, tenant_id: str) -> list[TravelerProfile]:
        return [p for (t, _), p in self._travelers.items() if t == tenant_id]

    def trips(self, tenant_id: str, traveler_id: str | None = None) -> list[Trip]:
        found = [trip for (t, _), trip in self._trips.items() if t == tenant_id]
        if traveler_id is not None:
            found = [trip for trip in found if trip.traveler_id == traveler_id]
        return sorted(found, key=lambda trip: trip.starts_on)

    def trip(self, tenant_id: str, trip_id: str) -> Trip | None:
        return self._trips.get((tenant_id, trip_id))

    def offer(self, tenant_id: str, offer_id: str) -> HeldOffer | None:
        return self._offers.get((tenant_id, offer_id))

    def reservation(self, tenant_id: str, booking_ref: str) -> Reservation | None:
        return self._reservations.get((tenant_id, booking_ref))

    def reservations(self, tenant_id: str, traveler_id: str | None = None) -> list[Reservation]:
        found = [r for (t, _), r in self._reservations.items() if t == tenant_id]
        if traveler_id is not None:
            found = [r for r in found if r.traveler_id == traveler_id]
        return found

    # --- maintenance ---

    def expire_offers(self, now: datetime) -> int:
        """Mark lapsed holds expired.

        DynamoDB does this with a TTL attribute; in memory it is explicit so
        tests can advance the clock rather than wait.
        """
        expired = 0
        for offer in self._offers.values():
            if offer.status is OfferStatus.HELD and now >= offer.expires_at:
                offer.status = OfferStatus.EXPIRED
                expired += 1
        return expired
