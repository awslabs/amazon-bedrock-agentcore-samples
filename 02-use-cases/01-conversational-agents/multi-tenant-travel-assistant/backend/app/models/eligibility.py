"""Eligibility request and response models.

The response is deliberately a **verdict**, not the inputs to one. `eligible` is decided in
`service/policy_check.py`; `computation` shows the arithmetic so a user can check it rather than
being asked to trust it.

`reason_code` is a stable string the eval gate asserts on, and `rule_quote` is the policy text the
agent may read aloud — quoted rather than paraphrased, because a paraphrase of a policy rule is a
new policy statement and the user may act on it.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from .common import CabinClass, Money


class EligibilityRequest(BaseModel):
    """One eligibility question.

    Every field is optional except the kind of check, because the three checks need different
    inputs and a single required set would force callers to invent values. The endpoint validates
    the combination and refuses an incomplete one rather than assuming a default — an assumed
    threshold is how a policy answer becomes quietly wrong.
    """

    # air | hotel | advance_purchase
    check: str

    # Air
    cabin: CabinClass | None = None
    flight_hours: float | None = Field(default=None, ge=0)
    # Alternative to flight_hours: derive it from a real trip's longest air segment.
    trip_id: str | None = None
    depart_on: date | None = None

    # Hotel
    nightly_rate: Money | None = None
    star_rating: int | None = Field(default=None, ge=1, le=5)

    # Evaluated as of this date; defaults to today server-side. Explicit so a test can pin it.
    as_of: date | None = None


class EligibilityVerdict(BaseModel):
    """A decided answer with its arithmetic shown."""

    eligible: bool
    reason_code: str
    rule_quote: str
    request_label: str
    computation: str | None = None
    trips_until_entitled: int | None = None
