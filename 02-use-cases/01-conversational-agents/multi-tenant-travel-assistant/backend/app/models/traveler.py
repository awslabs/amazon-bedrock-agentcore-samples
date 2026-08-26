"""Traveler profile — the system-of-record view.

**This model is deliberately PII-rich.** Passport numbers and payment references
belong here because a real TMC profile store holds them, and because the tool
layer needs something real to curate: `get_traveler_profile` returns passport
*country* and a masked payment label, never these fields. If PII never leaves
the Lambda, it cannot leak into model context, a card, or a log.

Declared preferences live here. *Observed* preferences ("always books the 6am
flight") are AgentCore Memory's job — this is the system of record, memory is
the personalization layer on top.
"""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from .common import CabinClass, CountryCode, IataCode, TenantId, TravelerId


class TravelerRole(StrEnum):
    """Who a traveler may act for.

    TRAVELER — themselves only.
    ARRANGER — themselves plus everyone in `can_book_for`. Cedar validates the
               target against that list; the model never asserts it.
    """

    TRAVELER = "traveler"
    ARRANGER = "arranger"


class SeatPreference(StrEnum):
    WINDOW = "window"
    AISLE = "aisle"
    NO_PREFERENCE = "no_preference"


class LoyaltyProgram(BaseModel):
    """Frequent-flyer / hotel-chain membership. `number` is PII."""

    program: str
    tier: str | None = None
    number: str  # PII — never leaves the backend


class Passport(BaseModel):
    """Only `country` is safe to surface.

    `check_entry_requirements` needs the issuing country; nothing downstream ever
    needs the number, so the tool layer drops it.
    """

    country: CountryCode
    number: str  # PII — never leaves the backend
    expires_on: date


class PaymentInstrument(BaseModel):
    """A corporate card held centrally.

    Card data never enters the agent, the model, or a tool argument — tools pass
    `payment_profile_id` and the backend records the charge. `display_label` is
    the only user-facing form.
    """

    payment_profile_id: str
    display_label: str  # e.g. "Visa •••4821 — corporate"
    last_four: str  # PII-adjacent — never leaves the backend


class Preferences(BaseModel):
    """Declared preferences — what the traveler entered in a form."""

    home_airport: IataCode | None = None
    seat: SeatPreference = SeatPreference.NO_PREFERENCE
    preferred_hotel_chains: list[str] = Field(default_factory=list)
    preferred_cabin: CabinClass | None = None
    dietary_notes: str | None = None


class TravelerProfile(BaseModel):
    """Full record as the TMC stores it. Curated by the tool layer before use."""

    tenant_id: TenantId
    traveler_id: TravelerId
    full_name: str
    email: str
    role: TravelerRole = TravelerRole.TRAVELER

    # Populated for arrangers only; empty for plain travelers.
    can_book_for: list[TravelerId] = Field(default_factory=list)

    preferences: Preferences = Field(default_factory=Preferences)
    loyalty: list[LoyaltyProgram] = Field(default_factory=list)
    passports: list[Passport] = Field(default_factory=list)
    payment_instruments: list[PaymentInstrument] = Field(default_factory=list)

    @property
    def primary_passport(self) -> Passport | None:
        """First passport on file.

        A traveler with two passports is a genuine ambiguity — the agent should
        ask which one applies rather than guess, so tools surface the list and
        only fall back to this when there is exactly one.
        """
        return self.passports[0] if self.passports else None
