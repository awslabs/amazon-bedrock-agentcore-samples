"""Trips and their segments.

`Trip` is the agent's context resolver: half the post-booking questions ("which
hotel am I at?", "chargers near my hotel") are answered by resolving a trip
first. That is why `HotelSegment` carries a full address — the location tools
geocode a place *string*, and an address resolves far more reliably than a hotel
name ("Marriott Dublin" geocodes to Dublin, Ohio).
"""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from .common import CabinClass, IataCode, Money, TenantId, TravelerId


class TripStatus(StrEnum):
    PAST = "past"
    UPCOMING = "upcoming"
    IN_PROGRESS = "in_progress"


class Place(BaseModel):
    """A geocodable location.

    The inter-tool contract: resolvers emit `address` when they have it, and the
    agent passes that string to `find_nearby` / `get_route` verbatim. Internal
    property codes stay in provenance and never become the handoff value.
    """

    name: str
    address: str | None = None
    city: str
    country: str


class AirSegment(BaseModel):
    kind: str = "air"
    carrier: str
    flight_number: str
    depart_airport: IataCode
    depart_at: datetime
    arrive_airport: IataCode
    arrive_at: datetime
    cabin: CabinClass
    is_international: bool

    @property
    def duration_minutes(self) -> int:
        return int((self.arrive_at - self.depart_at).total_seconds() // 60)


class HotelSegment(BaseModel):
    kind: str = "hotel"
    property_name: str
    property_code: str  # internal id — stays in provenance, never a handoff value
    location: Place
    check_in: date
    check_out: date
    nightly_rate: Money

    # **The reference a traveller can act on, distinct from `property_code` above.** Cancelling
    # needs the *booking's* identifier, and without it on the itinerary there was no route from
    # "cancel my hotel reservation" to `cancel_reservation` at all: no tool lists reservations, so
    # the model had nowhere to learn the reference and could only fetch trips and stop.
    #
    # Optional because a segment can describe travel that was never booked through this system — a
    # flight someone else arranged still belongs on the itinerary.
    booking_ref: str | None = None

    @property
    def nights(self) -> int:
        return (self.check_out - self.check_in).days


class Trip(BaseModel):
    """An itinerary. Segments are ordered as travelled."""

    tenant_id: TenantId
    traveler_id: TravelerId
    trip_id: str
    label: str  # e.g. "Client meeting — Atlanta"
    status: TripStatus
    starts_on: date
    ends_on: date
    destination: Place
    air_segments: list[AirSegment] = Field(default_factory=list)
    hotel_segments: list[HotelSegment] = Field(default_factory=list)
    total_cost: Money | None = None

    @property
    def is_international(self) -> bool:
        """Any international air segment makes the trip international.

        `check_policy_eligibility` counts these, so it must be a stored/derived
        fact rather than something the model infers from city names.
        """
        return any(seg.is_international for seg in self.air_segments)

    @property
    def primary_hotel(self) -> HotelSegment | None:
        """The hotel a "where am I staying?" question refers to.

        With one hotel this is unambiguous. With several the agent should ask —
        tools return the list and let the model disambiguate rather than guess.
        """
        return self.hotel_segments[0] if self.hotel_segments else None
