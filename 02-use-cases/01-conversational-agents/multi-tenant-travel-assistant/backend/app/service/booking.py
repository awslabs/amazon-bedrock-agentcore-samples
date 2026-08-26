"""The offer lifecycle: hold, then confirm.

The pattern this module exists to demonstrate: **the client holds a handle, the
server holds the truth.**

A hold regenerates the option deterministically, freezes its fare, and stores it
with an expiry. Confirm takes only the handle and re-derives everything —
ownership, expiry, current fare, policy status. Nothing about the booking is
trusted from the caller, because anything a client sends can be modified.

Every failure here is an explicit refusal with its own exception type, so callers
can respond differently to "expired", "already used", and "the fare moved". A
single generic error would force the agent to guess which happened.
"""

import hashlib
import secrets
from datetime import date, datetime, timedelta

from generator import generate_air_options, generate_hotel_options
from generator.scenarios import Scenario, ScenarioFlags
from generator.seeding import air_query_parts, hotel_query_parts

from ..models import (
    OFFER_TTL_MINUTES,
    FlightOption,
    GenerationMode,
    HeldOffer,
    HotelOption,
    Money,
    OfferStatus,
    Reservation,
    ReservationStatus,
    TenantConfig,
    TravelKind,
)
from ..reference import resolve_airport
from ..repository import OfferConflictError, Repository
from .search import _policy_or_empty, resolve_origin


class OptionNotFoundError(LookupError):
    """The option id isn't in a fresh generation of that search."""


class OptionParamsMismatchError(LookupError):
    """The search parameters don't belong to this option id.

    **Distinct from `OptionNotFoundError` because the two need opposite responses.** Not-found means
    the option is genuinely gone and the caller should search again. This means the *caller* is
    inconsistent — the id encodes one query and the parameters describe another — so searching again
    would produce the same contradiction. Collapsing them made an agent apologise for lost inventory
    when it had simply mistyped a date.
    """


class OfferNotFoundError(LookupError):
    """No such hold for this tenant and traveller.

    Deliberately also covers another tenant's or traveller's handle — a copied
    `offer_id` must be indistinguishable from one that never existed.
    """


class OfferExpiredError(RuntimeError):
    """The hold lapsed before confirmation."""


class OfferAlreadyUsedError(RuntimeError):
    """The hold was already booked. Guards against a double-click booking twice."""


class PriceMovedError(RuntimeError):
    """The fare changed between hold and confirm.

    Carries both prices so the caller can show a fresh confirmation rather than
    charging a different amount silently.
    """

    def __init__(self, offer_id: str, previous: Money, current: Money):
        self.offer_id = offer_id
        self.previous = previous
        self.current = current
        super().__init__(f"price moved from {previous} to {current}")


def _regenerate_option(
    repo: Repository,
    tenant_id: str,
    config: TenantConfig,
    request,
    mode: GenerationMode,
    flags: ScenarioFlags | None = None,
    traveler_id: str | None = None,
) -> FlightOption | HotelOption:
    """Re-derive a specific option from its search parameters.

    Possible only because generation is deterministic: the same query yields the
    same options, so an option can be found again without ever storing it.
    """
    if request.kind is TravelKind.AIR:
        policy = _policy_or_empty(repo, tenant_id, "air")
        result = generate_air_options(
            tenant_id=tenant_id,
            # **The same resolution search used, or the option cannot be found again.**
            # Generation is deterministic on its query, so an origin resolved from the profile
            # at search time and left empty here seeds differently and yields different option
            # ids — surfacing as "that option is no longer available" for an option still on
            # the traveller's screen.
            origin_query=resolve_origin(repo, tenant_id, traveler_id, request.origin),
            destination_query=request.destination,
            depart_on=date.fromisoformat(request.depart_on),
            policy=policy,
            currency=config.currency,
            mode=mode,
            flags=flags,
        )
        options: list = result.options
    else:
        policy = _policy_or_empty(repo, tenant_id, "hotel")
        result = generate_hotel_options(
            tenant_id=tenant_id,
            destination_query=request.destination,
            check_in=date.fromisoformat(request.check_in),
            check_out=date.fromisoformat(request.check_out),
            policy=policy,
            currency=config.currency,
            mode=mode,
            flags=flags,
        )
        options = result.options

    for option in options:
        if option.option_id == request.option_id:
            return option

    # **A mismatch means the parameters do not belong to this option id**, and saying so is the
    # whole point of this branch.
    #
    # `option_id` is `opt_<digest of the search parameters>_<index>`, so the id and the parameters
    # are two statements about the same query — and a caller that restates the parameters can make
    # them disagree. That is not hypothetical: an agent recalling an option from an earlier turn
    # retyped the dates a year out, the backend regenerated a *different* set of options, and the
    # lookup failed. The old bare `OptionNotFoundError` read as "that room is gone" and the agent
    # apologised for lost inventory that had never existed.
    #
    # So the digest is recomputed here. It cannot fix the caller's parameters — it can only tell an
    # honest mistake ("your dates do not match this option") from real absence ("that option is no
    # longer offered"), which are the two things a caller must never confuse.
    expected = _expected_digest(tenant_id, request)
    if expected and not request.option_id.startswith(f"opt_{expected}_"):
        raise OptionParamsMismatchError(request.option_id)
    raise OptionNotFoundError(request.option_id)


def _expected_digest(tenant_id: str, request) -> str | None:
    """The digest `option_id` would carry if `request`'s parameters produced it.

    `None` when the parameters are too incomplete to seed a query at all — in which case the caller
    gets the plain not-found, since there is nothing to compare against.
    """
    try:
        if request.kind is TravelKind.AIR:
            # Resolved through `resolve_airport`, exactly as the generator does — "Dublin", "dublin
            # airport" and "DUB" all seed the same query, so comparing raw strings would report a
            # mismatch for a caller who simply phrased the city differently.
            parts = air_query_parts(
                tenant_id,
                resolve_airport(request.origin or "").code,
                resolve_airport(request.destination).code,
                date.fromisoformat(request.depart_on),
            )
        else:
            parts = hotel_query_parts(
                tenant_id,
                resolve_airport(request.destination).city,
                date.fromisoformat(request.check_in),
                date.fromisoformat(request.check_out),
            )
    except (AttributeError, TypeError, ValueError, LookupError):
        return None
    # Same construction as `generator.seeding.option_id`, minus the index — which is the part that
    # identifies *which* option within the query rather than the query itself.
    return hashlib.blake2b("|".join(parts).encode(), digest_size=5).hexdigest()


def _describe(option: FlightOption | HotelOption) -> str:
    if isinstance(option, FlightOption):
        return (
            f"{option.carrier_name} {option.flight_number} "
            f"{option.depart_airport}-{option.arrive_airport} "
            f"{option.depart_at:%d %b %H:%M} ({option.cabin.value})"
        )
    return f"{option.property_name}, {option.city} ({option.star_rating}-star)"


def _price_of(option: FlightOption | HotelOption) -> Money:
    return option.price if isinstance(option, FlightOption) else option.total


def hold(
    repo: Repository,
    tenant_id: str,
    config: TenantConfig,
    traveler_id: str,
    request,
    mode: GenerationMode,
    now: datetime,
    flags: ScenarioFlags | None = None,
) -> HeldOffer:
    """Freeze a fare and persist the hold."""
    option = _regenerate_option(repo, tenant_id, config, request, mode, flags, traveler_id)
    price = _price_of(option)

    traveler = repo.traveler(tenant_id, traveler_id)
    payment_profile_id = (
        traveler.payment_instruments[0].payment_profile_id
        if traveler and traveler.payment_instruments
        else "pp_unknown"
    )

    offer = HeldOffer(
        tenant_id=tenant_id,
        traveler_id=traveler_id,
        # **A hold is a distinct event, so its id must be unique — including two holds on the
        # *same* option.**
        #
        # This was `off_{option_id[-10:]}`, derived from the option. Two problems, and the second is
        # the one that bit: different options can collide (`opt_f1062d6656_1` and `opt_062d6656_1`
        # both truncate to `062d6656_1`), and re-holding the same option overwrites the earlier row
        # at
        # the same key. Either way a `confirm` on the first handle finds a row that is now a
        # different
        # offer — or one already consumed — and reports **404**, which reads as an expired or
        # foreign
        # handle. Intermittent by nature, so it survived a full exit suite more than once.
        #
        # Random rather than derived: an offer is a moment in time, not a property of an option, and
        # nothing needs to recompute this id from anything else. `token_hex(5)` is 40 bits — plenty
        # for a row that lives ten minutes, and opaque, which a client-held handle should be.
        offer_id=f"off_{secrets.token_hex(5)}",
        kind=request.kind,
        option_id=request.option_id,
        frozen_price=price,
        payment_profile_id=payment_profile_id,
        policy_status=option.policy_status,
        held_at=now,
        # **`EXPIRED_OFFER` lands a hold that is already dead**, rather than asking a test to wait
        # ten minutes. The row is still written, and that is the point: `confirm` must find it and
        # answer "that hold expired, shall I search again?" — an offer that was never stored is a
        # 404, which reads to the agent as a handle that never existed and invites it to retry the
        # whole booking instead of re-searching.
        expires_at=(
            now - timedelta(minutes=1)
            if flags and Scenario.EXPIRED_OFFER in flags
            else now + timedelta(minutes=OFFER_TTL_MINUTES)
        ),
        description=_describe(option),
        search_params={
            k: v
            for k, v in {
                "kind": request.kind.value,
                "origin": request.origin,
                "destination": request.destination,
                "depart_on": request.depart_on,
                "check_in": request.check_in,
                "check_out": request.check_out,
            }.items()
            if v is not None
        },
    )
    repo.put_offer(offer)
    return offer


def _booking_ref(offer_id: str) -> str:
    """The reservation ref for an offer — deterministic, and therefore the idempotency key.

    Stated in one place because two callers now depend on it agreeing: the reservation `confirm`
    creates, and the lookup that answers "did an earlier attempt already create it?". Two copies of
    this expression would make a retry silently miss the reservation it was looking for, and refuse
    a booking that exists.

    **Carries the offer's whole 40 bits, not 32 of them.** This read `offer_id[-8:]`, which dropped
    two of the ten hex characters `token_hex(5)` produces — and once a replay returns the existing
    reservation instead of refusing, discarded entropy stops being cosmetic. Two *different* offers
    colliding on a truncated suffix would resolve to one `sk`, and the second confirmation would
    read the first's row and hand that booking back as though it were a replay of its own: the wrong
    itinerary, reported as success. Under the old 409 contract the same collision merely failed the
    condition and refused, so widening this is what keeps the idempotent path fail-safe rather than
    fail-wrong. `removeprefix` rather than a slice, so the intent is "the offer's id" instead of a
    character count that has to be kept in step with the generator.
    """
    return f"bkg_{offer_id.removeprefix('off_')}"


def confirm(
    repo: Repository,
    tenant_id: str,
    config: TenantConfig,
    traveler_id: str,
    offer_id: str,
    mode: GenerationMode,
    now: datetime,
    flags: ScenarioFlags | None = None,
) -> Reservation:
    """Book a held offer after re-deriving everything about it."""
    offer = repo.offer(tenant_id, offer_id)

    # Ownership: a handle belonging to someone else is treated as nonexistent.
    if offer is None or offer.traveler_id != traveler_id:
        raise OfferNotFoundError(offer_id)

    if offer.status is OfferStatus.CONSUMED:
        # **A retry of a confirmation that already succeeded returns the same reservation.**
        #
        # This raised unconditionally, producing a 409 and a tool message reading "Nothing has been
        # charged" — a false statement about a traveller's money, in the one case where being wrong
        # about it matters. A lost response is indistinguishable from a failure at the client, so a
        # retry is *correct* client behaviour, and must not be answered with the opposite of it.
        #
        # **No new idempotency key was needed, because `booking_ref` is already derived from the
        # offer.** One offer can only produce one reservation ref, so the key existed all along;
        # it was simply never used to answer "did my earlier attempt land?".
        #
        # Ownership is not assumed: a mismatched `traveler_id` was rejected above, so reaching here
        # means this traveller held the offer. Checking the reservation's own `traveler_id` as well
        # costs nothing and keeps this correct if the ref derivation ever changes.
        existing = repo.reservation(tenant_id, _booking_ref(offer_id))
        if existing is not None and existing.traveler_id == traveler_id:
            return existing
        # Consumed, but no reservation under this traveller — a genuinely spent hold rather than a
        # lost response. Refused, exactly as before.
        raise OfferAlreadyUsedError(offer_id)
    if not offer.is_valid_at(now):
        offer.status = OfferStatus.EXPIRED
        repo.put_offer(offer)
        raise OfferExpiredError(offer_id)

    # Re-price: what was shown may no longer be true.
    current = _current_price(repo, tenant_id, config, offer, mode, flags)
    if current is not None and current.amount != offer.frozen_price.amount:
        raise PriceMovedError(offer.offer_id, offer.frozen_price, current)

    reservation = Reservation(
        tenant_id=tenant_id,
        traveler_id=traveler_id,
        booking_ref=_booking_ref(offer.offer_id),
        confirmation_number=f"TRV{offer.offer_id[-6:].upper()}",
        kind=offer.kind,
        description=offer.description,
        total=offer.frozen_price,
        status=ReservationStatus.CONFIRMED,
        issued_at=now,
        # A flight starts on its departure date, a hotel stay on check-in. Both live in the offer's
        # stored search parameters, so neither is inferred from the description's prose.
        starts_on=offer.search_params.get("depart_on") or offer.search_params.get("check_in"),
    )
    # **The write that used to be two unconditional puts.** Everything above is read-then-check,
    # which is advice rather than a guarantee: another request can pass the same checks in the same
    # instant. `consume_offer` transitions the offer only if it is still held and creates the
    # reservation only if it does not exist, in one transaction — so a double-click or a retried
    # POST loses here instead of booking twice.
    try:
        repo.consume_offer(offer, reservation)
    except OfferConflictError:
        # Consumed between the read above and this write — the two-at-once case, which is when money
        # is actually at stake. Same resolution as the sequential retry above: if the winner's
        # reservation is there, this caller asked for a booking that now exists, so return it. Both
        # requests then receive the same answer, which is what idempotent means here.
        existing = repo.reservation(tenant_id, reservation.booking_ref)
        if existing is not None and existing.traveler_id == traveler_id:
            return existing
        raise OfferAlreadyUsedError(offer_id) from None

    return reservation


def _current_price(
    repo: Repository,
    tenant_id: str,
    config: TenantConfig,
    offer: HeldOffer,
    mode: GenerationMode,
    flags: ScenarioFlags | None = None,
) -> Money | None:
    """Today's price for the held option, re-derived from its search parameters.

    `None` when the option can no longer be generated at all (inventory gone). A
    hold is short-lived, so proceeding at the frozen price beats refusing a valid
    booking because a re-check was inconclusive.
    """
    params = offer.search_params
    if not params:
        return None

    request = _StoredSearch(offer.option_id, params)
    try:
        option = _regenerate_option(
            repo, tenant_id, config, request, mode, flags, offer.traveler_id
        )
    except (OptionNotFoundError, LookupError, ValueError):
        return None
    return _price_of(option)


class _StoredSearch:
    """Adapts a stored `search_params` dict back to what `_regenerate_option`
    expects, so hold and confirm share one regeneration path."""

    def __init__(self, option_id: str, params: dict[str, str]):
        self.option_id = option_id
        self.kind = TravelKind(params["kind"])
        self.origin = params.get("origin")
        self.destination = params["destination"]
        self.depart_on = params.get("depart_on")
        self.check_in = params.get("check_in")
        self.check_out = params.get("check_out")


__all__ = [
    "OfferAlreadyUsedError",
    "OptionParamsMismatchError",
    "OfferExpiredError",
    "OfferNotFoundError",
    "OptionNotFoundError",
    "PriceMovedError",
    "cancellation_terms",
    "confirm",
    "hold",
]


def cancellation_terms(reservation: Reservation):
    """Penalties for cancelling, shown before anything is cancelled."""
    from ..models import CancellationPenalty, CancellationTerms

    refundable = reservation.kind is TravelKind.HOTEL
    if refundable:
        return CancellationTerms(
            booking_ref=reservation.booking_ref,
            penalties=[
                CancellationPenalty(
                    item=reservation.description,
                    penalty=None,
                    note="Free cancellation until 48 hours before arrival",
                )
            ],
            refund_estimate=reservation.total,
            fully_refundable=True,
        )

    penalty = Money(
        amount=round(reservation.total.amount / 2, 2), currency=reservation.total.currency
    )
    return CancellationTerms(
        booking_ref=reservation.booking_ref,
        penalties=[
            CancellationPenalty(
                item=reservation.description,
                penalty=penalty,
                note="50% penalty within 14 days of departure",
            )
        ],
        refund_estimate=Money(
            amount=reservation.total.amount - penalty.amount,
            currency=reservation.total.currency,
        ),
        fully_refundable=False,
    )
