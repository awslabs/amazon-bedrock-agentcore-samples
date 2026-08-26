"""Search, held offers, and reservations.

The offer lifecycle mirrors how GDS pricing actually works: a search returns
options, pricing an option produces a **short-lived handle** with a frozen fare,
and only that handle can be ticketed. So options here are generated on demand and
never stored, while a *held offer* is real persisted state with an expiry.

That is also why a client only ever receives `offer_id`. Prices in a client
payload would be forgeable; the server re-derives the fare, re-checks ownership
and expiry, then books. Same principle as citation links: handle out, ownership
re-checked in.
"""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from .common import (
    CabinClass,
    IataCode,
    Money,
    PolicyStatus,
    TenantId,
    TravelerId,
    TravelKind,
)

# How long a priced offer stays valid. Short enough that expiry is demonstrable
# in a conversation, long enough not to trip on ordinary hesitation.
OFFER_TTL_MINUTES = 10


class SortOrder(StrEnum):
    PRICE = "price"
    DURATION = "duration"
    DEPARTURE = "departure"


class AirSearchRequest(BaseModel):
    """Origin and destination arrive as place *names* or codes.

    The tool resolves either form; the model supplies traveller intent and never
    handles internal codes.

    **`origin` is optional because a traveller does not say it.** "Find me a flight
    to London on 10 November" names no origin, and the tool declines to invent one —
    it documents that an absent origin means the traveller's home airport, read from
    their profile. Declaring it required here contradicted that and turned the
    commonest possible flight request into a 422 the model could only report as
    "I couldn't reach the flight search system". The service resolves it from the
    verified traveller; see `search_air`.
    """

    origin: str | None = None
    destination: str
    depart_on: date
    return_on: date | None = None
    cabin: CabinClass | None = None
    sort: SortOrder = SortOrder.PRICE


class HotelFilters(BaseModel):
    """Filters ride parameters — variation never becomes a new tool."""

    breakfast_included: bool | None = None
    gym: bool | None = None
    workspace: bool | None = None
    chain: str | None = None
    max_star_rating: int | None = Field(default=None, ge=1, le=5)


class HotelSearchRequest(BaseModel):
    destination: str
    check_in: date
    check_out: date
    filters: HotelFilters = Field(default_factory=HotelFilters)
    sort: SortOrder = SortOrder.PRICE


class FlightOption(BaseModel):
    """One generated itinerary option.

    `option_id` encodes the generating seed, so re-pricing the same option later
    is deterministic without storing it.
    """

    option_id: str
    carrier: str
    carrier_name: str
    flight_number: str
    depart_airport: IataCode
    depart_at: datetime
    arrive_airport: IataCode
    arrive_at: datetime
    duration_minutes: int
    stops: int
    cabin: CabinClass
    price: Money
    refundable: bool
    # Carried as a fact, not inferred downstream: `check_policy_eligibility`
    # counts international trips, and a model guessing from city names would get
    # it wrong.
    is_international: bool
    policy_status: PolicyStatus
    policy_note: str | None = None


class HotelOption(BaseModel):
    option_id: str
    property_code: str
    property_name: str
    chain: str
    address: str
    city: str
    star_rating: int
    nightly_rate: Money
    total: Money
    amenities: list[str] = Field(default_factory=list)
    is_preferred_chain: bool = False
    policy_status: PolicyStatus
    policy_note: str | None = None


class SearchSummary(BaseModel):
    """Cross-cutting counts the tool layer surfaces as `facts`.

    Aggregates belong to the whole result set rather than to any one option, so
    they are computed here — the model must never count cards itself.
    """

    total_options: int
    in_policy_options: int
    cheapest_in_policy: Money | None = None
    policy_cap: Money | None = None


class AirSearchResponse(BaseModel):
    options: list[FlightOption]
    summary: SearchSummary
    resolved_origin: IataCode
    resolved_destination: IataCode


class HotelSearchResponse(BaseModel):
    options: list[HotelOption]
    summary: SearchSummary
    resolved_city: str


class OfferStatus(StrEnum):
    HELD = "held"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class HeldOffer(BaseModel):
    """A priced hold — the fake PNR.

    The only durable artifact of a search. `frozen_price` is what the traveller
    was shown; on confirm the backend re-prices and compares, so a fare move
    surfaces as a fresh confirmation rather than a silent charge.
    """

    tenant_id: TenantId
    traveler_id: TravelerId
    offer_id: str
    kind: TravelKind
    option_id: str
    frozen_price: Money
    payment_profile_id: str
    policy_status: PolicyStatus
    held_at: datetime
    expires_at: datetime
    status: OfferStatus = OfferStatus.HELD
    description: str = ""

    # The search parameters that produced this option. Stored because confirm
    # must *re-derive* the fare rather than trust the frozen one — without these
    # the option cannot be regenerated and price drift would go undetected.
    search_params: dict[str, str] = Field(default_factory=dict)

    def is_valid_at(self, now: datetime) -> bool:
        return self.status == OfferStatus.HELD and now < self.expires_at


class ReservationStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Reservation(BaseModel):
    tenant_id: TenantId
    traveler_id: TravelerId
    booking_ref: str
    confirmation_number: str
    kind: TravelKind
    description: str
    total: Money
    status: ReservationStatus = ReservationStatus.CONFIRMED
    issued_at: datetime
    trip_id: str | None = None

    # **When the travel happens, as `YYYY-MM-DD`** — distinct from `issued_at`, which is when it was
    # booked. Carried through from the held offer's search parameters rather than re-derived, since
    # the
    # offer is the only record of what was actually searched for.
    #
    # It exists so a confirmed booking can become a calendar entry. `description` does contain a
    # date
    # in prose, and parsing it back out would be the wrong shape of fix: a date a person can read is
    # not a date a machine should re-interpret, and the value is already available structurally.
    # Optional because a reservation seeded directly by fixtures has no offer behind it.
    starts_on: str | None = None


class CancellationPenalty(BaseModel):
    item: str
    penalty: Money | None = None
    deadline: date | None = None
    note: str | None = None


class CancellationTerms(BaseModel):
    """Shown before any cancellation is executed — terms first, then confirm."""

    booking_ref: str
    penalties: list[CancellationPenalty]
    refund_estimate: Money | None = None
    fully_refundable: bool = False
