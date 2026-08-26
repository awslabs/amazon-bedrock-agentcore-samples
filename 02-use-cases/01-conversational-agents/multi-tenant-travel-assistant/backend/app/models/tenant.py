"""Per-tenant configuration.

Runtime-changeable settings, unlike the static reference fixtures: `booking_mode`
decides whether a traveller confirms inside the conversation or is handed to a
checkout page, and that is a genuine per-customer difference rather than a
product decision. Keeping it as data means the same code demonstrates both.
"""

from enum import StrEnum

from pydantic import BaseModel

from .common import Currency, TenantId


class BookingMode(StrEnum):
    """How far the agent may take a booking.

    CONFIRM_IN_CHAT — the agent shows a summary and books on explicit
        confirmation. Still never auto-books: a person clicks confirm.
    HANDOFF — the agent assembles everything and hands over a checkout link,
        which is the more conservative pattern many programmes start with.

    Fully autonomous booking is out of scope by design, not by omission.
    """

    CONFIRM_IN_CHAT = "confirm_in_chat"
    HANDOFF = "handoff"


class TenantConfig(BaseModel):
    tenant_id: TenantId
    display_name: str
    currency: Currency
    booking_mode: BookingMode
    home_country: str
    support_queue: str | None = None
    """Where `escalate_to_human` routes. Absent means escalation is unavailable
    for this tenant, which the agent must say rather than pretend to transfer."""
