"""Pydantic models for the mock TMC backend.

These are the *backend's* API contract — full records, PII included. They are
not the agent's contract: tool Lambdas curate these into `{cards, facts}` before
anything reaches model context. Nothing in `frontend/` or `shared/` imports from
here; the frontend only ever sees cards.
"""

from .booking import (
    OFFER_TTL_MINUTES,
    AirSearchRequest,
    AirSearchResponse,
    CancellationPenalty,
    CancellationTerms,
    FlightOption,
    HeldOffer,
    HotelFilters,
    HotelOption,
    HotelSearchRequest,
    HotelSearchResponse,
    OfferStatus,
    Reservation,
    ReservationStatus,
    SearchSummary,
    SortOrder,
)
from .common import (
    TENANT_KEY_PREFIX,
    CabinClass,
    CountryCode,
    Currency,
    GenerationMode,
    IataCode,
    Money,
    PolicyStatus,
    TenantId,
    TravelerId,
    TravelKind,
    tenant_pk,
)
from .eligibility import EligibilityRequest, EligibilityVerdict
from .policy import (
    CabinRule,
    CabinRuleType,
    PolicyCore,
    PolicyRule,
    TravelPolicy,
)
from .reference import Airport, EntryRequirement, EntryRequirementKind
from .tenant import BookingMode, TenantConfig
from .traveler import (
    LoyaltyProgram,
    Passport,
    PaymentInstrument,
    Preferences,
    SeatPreference,
    TravelerProfile,
    TravelerRole,
)
from .trip import AirSegment, HotelSegment, Place, Trip, TripStatus

__all__ = [
    "OFFER_TTL_MINUTES",
    "TENANT_KEY_PREFIX",
    "AirSearchRequest",
    "AirSearchResponse",
    "AirSegment",
    "Airport",
    "BookingMode",
    "CabinClass",
    "EligibilityRequest",
    "EligibilityVerdict",
    "CabinRule",
    "CabinRuleType",
    "CancellationPenalty",
    "CancellationTerms",
    "CountryCode",
    "Currency",
    "EntryRequirement",
    "EntryRequirementKind",
    "FlightOption",
    "GenerationMode",
    "HeldOffer",
    "HotelFilters",
    "HotelOption",
    "HotelSearchRequest",
    "HotelSearchResponse",
    "HotelSegment",
    "IataCode",
    "LoyaltyProgram",
    "Money",
    "OfferStatus",
    "Passport",
    "PaymentInstrument",
    "Place",
    "PolicyCore",
    "PolicyRule",
    "PolicyStatus",
    "Preferences",
    "Reservation",
    "ReservationStatus",
    "SearchSummary",
    "SeatPreference",
    "SortOrder",
    "TenantConfig",
    "TenantId",
    "TravelPolicy",
    "TravelKind",
    "Trip",
    "TripStatus",
    "TravelerId",
    "TravelerProfile",
    "TravelerRole",
    "tenant_pk",
]
