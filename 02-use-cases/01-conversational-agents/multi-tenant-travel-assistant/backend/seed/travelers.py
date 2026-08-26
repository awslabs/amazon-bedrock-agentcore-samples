"""Seed travelers and their trip history.

Three people, each chosen to exercise something specific:

- **Priya Raghunathan** (Globex, traveller) — the default persona, seeded with
  **4 international trips counted for 2026**: 3 already taken, plus the upcoming
  Singapore trip below. `count_international_trips` counts an upcoming trip once
  it exists (`CabinRule.count_upcoming` defaults to `True` — see
  `app/eligibility.py`'s docstring for why the stricter reading is the default),
  so Singapore is trip 4 and a further international booking — Tokyo, in the
  README's example — is trip 5, one short of Globex's every-4th-trip rule.
  "Can I book business class?" therefore has a **denial** with real arithmetic
  behind it: `cabin_entitlement_not_yet_earned`, not a grant.
- **Adaeze Okonkwo** (Globex, arranger) — books for Priya and one colleague, so
  she exercises the `can_book_for` path and the Cedar arranger check.
- **Sam Whitfield** (Initech, traveller) — the isolation counterpart: the same
  questions asked of him return strict answers, and his data must never surface
  under a Globex session.
- **Sam Okonjo** and **Sam Adewale** (Globex, travellers) — two people Adaeze can
  book for who share a first name. "Book a flight for Sam" is therefore genuinely
  ambiguous, and the tool must ask which rather than pick one. They also prove
  the search is scoped to *authorisation*, not to the name: Sam Whitfield at
  Initech matches the same string and must never appear as a candidate.

Traveller ids are opaque (`trv_…`) rather than readable slugs. A readable id
would be derived from a name (which changes), would collide with the next Priya,
and would leak personal data into logs, URLs and audit trails. Display names are
separate attributes; everything references the id.

Every traveller carries PII (passport number, card last-four) on purpose — the
tool layer curates it away, and it cannot do that if there is nothing to curate.
Each has one `in_progress` trip so "which hotel am I at?" context questions work.
"""

from datetime import date, datetime

from app.models import (
    CabinClass,
    Currency,
    LoyaltyProgram,
    Money,
    Passport,
    PaymentInstrument,
    Place,
    Preferences,
    Reservation,
    SeatPreference,
    TravelerProfile,
    TravelerRole,
    TravelKind,
    Trip,
    TripStatus,
)
from app.models.trip import AirSegment, HotelSegment

# Named constants so nothing downstream hardcodes an opaque id. Fixed values
# rather than generated ones: deterministic option ids depend on stable inputs,
# and a per-run UUID would make search results differ between test runs.
PRIYA_ID = "trv_31d81fa59772"
ADAEZE_ID = "trv_95c557b6c43e"
SAM_OKONJO_ID = "trv_87912ffd11c6"
SAM_ADEWALE_ID = "trv_83053b3287b1"
MARCUS_ID = "trv_bae58c01959e"
SAM_WHITFIELD_ID = "trv_bbc2e338c41a"

# The reference shared by Priya's Dallas hotel segment and its reservation record. Stated once
# because the two must agree: the itinerary is where the model learns the reference, and the
# reservation is what `cancel_reservation` resolves it against.
PRIYA_DALLAS_HOTEL_REF = "BKG-7Q2M4T"


# --- travelers -------------------------------------------------------------

PRIYA = TravelerProfile(
    tenant_id="globex",
    traveler_id=PRIYA_ID,
    full_name="Priya Raghunathan",
    email="priya.raghunathan@globex.example",
    role=TravelerRole.TRAVELER,
    preferences=Preferences(
        home_airport="ORD",
        seat=SeatPreference.AISLE,
        preferred_hotel_chains=["Marriott", "Hyatt"],
    ),
    loyalty=[LoyaltyProgram(program="United MileagePlus", tier="Gold", number="UA-2213847")],
    # **9 characters, deliberately.** CloudWatch Logs' `PassportNumber-US` managed identifier only
    # matches a 9-character value (9 digits, or a letter followed by 8 digits) — measured directly:
    # an 8-character `X4471902` is **not** detected and passes through log masking unredacted,
    # while `X44719025` is masked. A fixture shorter than the detector's pattern makes the masking
    # control look broken when it is working exactly as specified.
    passports=[Passport(country="US", number="X44719025", expires_on=date(2030, 6, 30))],
    payment_instruments=[
        PaymentInstrument(
            payment_profile_id="pp_globex_priya",
            display_label="Visa •••4821 — Globex corporate",
            last_four="4821",
        )
    ],
)

ADAEZE = TravelerProfile(
    tenant_id="globex",
    traveler_id=ADAEZE_ID,
    full_name="Adaeze Okonkwo",
    email="adaeze.okonkwo@globex.example",
    role=TravelerRole.ARRANGER,
    can_book_for=[
        PRIYA_ID,
        SAM_OKONJO_ID,
        SAM_ADEWALE_ID,
        MARCUS_ID,
    ],
    preferences=Preferences(
        home_airport="LHR",
        seat=SeatPreference.WINDOW,
        preferred_hotel_chains=["Hilton"],
    ),
    loyalty=[LoyaltyProgram(program="BA Executive Club", tier="Silver", number="BA-9930215")],
    passports=[Passport(country="NG", number="A08842317", expires_on=date(2029, 3, 15))],
    payment_instruments=[
        PaymentInstrument(
            payment_profile_id="pp_globex_adaeze",
            display_label="Amex •••1006 — Globex corporate",
            last_four="1006",
        )
    ],
)

SAM = TravelerProfile(
    tenant_id="initech",
    traveler_id=SAM_WHITFIELD_ID,
    full_name="Sam Whitfield",
    email="sam.whitfield@initech.example",
    role=TravelerRole.TRAVELER,
    preferences=Preferences(
        home_airport="DUB",
        seat=SeatPreference.AISLE,
        preferred_hotel_chains=["Accor"],
    ),
    loyalty=[LoyaltyProgram(program="Aer Lingus AerClub", tier="Concierge", number="EI-5518820")],
    passports=[Passport(country="IE", number="PA9930148", expires_on=date(2031, 1, 20))],
    payment_instruments=[
        PaymentInstrument(
            payment_profile_id="pp_initech_sam",
            display_label="Mastercard •••7734 — Initech corporate",
            last_four="7734",
        )
    ],
)

SAM_OKONJO = TravelerProfile(
    tenant_id="globex",
    traveler_id=SAM_OKONJO_ID,
    full_name="Sam Okonjo",
    email="sam.okonjo@globex.example",
    role=TravelerRole.TRAVELER,
    preferences=Preferences(home_airport="JFK", seat=SeatPreference.WINDOW),
    passports=[Passport(country="US", number="X77190438", expires_on=date(2032, 4, 2))],
    payment_instruments=[
        PaymentInstrument(
            payment_profile_id="pp_globex_sam_okonjo",
            display_label="Visa •••3390 — Globex corporate",
            last_four="3390",
        )
    ],
)

SAM_ADEWALE = TravelerProfile(
    tenant_id="globex",
    traveler_id=SAM_ADEWALE_ID,
    full_name="Sam Adewale",
    email="sam.adewale@globex.example",
    role=TravelerRole.TRAVELER,
    preferences=Preferences(home_airport="SFO", seat=SeatPreference.AISLE),
    passports=[Passport(country="NG", number="A11290573", expires_on=date(2030, 8, 19))],
    payment_instruments=[
        PaymentInstrument(
            payment_profile_id="pp_globex_sam_adewale",
            display_label="Visa •••8812 — Globex corporate",
            last_four="8812",
        )
    ],
)

TRAVELERS = [PRIYA, ADAEZE, SAM, SAM_OKONJO, SAM_ADEWALE]


# --- trip construction helpers ---------------------------------------------


def _hotel(
    name: str,
    code: str,
    city: str,
    country: str,
    ci: date,
    co: date,
    rate: int,
    booking_ref: str | None = None,
) -> HotelSegment:
    return HotelSegment(
        property_name=name,
        property_code=code,
        location=Place(name=name, address=f"1 Central Plaza, {city}", city=city, country=country),
        check_in=ci,
        check_out=co,
        nightly_rate=Money(amount=rate, currency=Currency.USD),
        booking_ref=booking_ref,
    )


def _trip(
    traveler: str,
    trip_id: str,
    label: str,
    status: TripStatus,
    starts: date,
    ends: date,
    dest: Place,
    air: list[AirSegment],
    hotels: list[HotelSegment] | None = None,
    tenant: str = "globex",
) -> Trip:
    return Trip(
        tenant_id=tenant,
        traveler_id=traveler,
        trip_id=trip_id,
        label=label,
        status=status,
        starts_on=starts,
        ends_on=ends,
        destination=dest,
        air_segments=air,
        hotel_segments=hotels or [],
    )


def _flight(
    depart: datetime,
    arrive: datetime,
    dep: str,
    arr: str,
    carrier: str,
    fn: str,
    *,
    international: bool,
) -> AirSegment:
    return AirSegment(
        carrier=carrier,
        flight_number=fn,
        depart_airport=dep,
        depart_at=depart,
        arrive_airport=arr,
        arrive_at=arrive,
        cabin=CabinClass.ECONOMY,
        is_international=international,
    )


# --- Priya: 3 international trips already taken, plus an in-progress domestic one ---
# The count that matters is international + within the calendar year, and an upcoming trip
# counts too (`count_upcoming` — see `app/eligibility.py`). With the Singapore trip below already
# on the books, a further international booking is trip 5: one short of Globex's every-4th-trip
# rule, so the eligibility question below is answered with a denial, not a grant.

PRIYA_TRIPS = [
    _trip(
        PRIYA_ID,
        "trip_priya_1",
        "Client kickoff — London",
        TripStatus.PAST,
        date(2026, 2, 10),
        date(2026, 2, 13),
        Place(name="London", city="London", country="GB"),
        [
            _flight(
                datetime(2026, 2, 10, 8, 0),
                datetime(2026, 2, 10, 16, 30),
                "ORD",
                "LHR",
                "UA",
                "UA928",
                international=True,
            )
        ],
        [
            _hotel(
                "Hilton London",
                "h_lon_01",
                "London",
                "GB",
                date(2026, 2, 10),
                date(2026, 2, 13),
                210,
            )
        ],
    ),
    _trip(
        PRIYA_ID,
        "trip_priya_2",
        "Supplier review — Frankfurt",
        TripStatus.PAST,
        date(2026, 4, 21),
        date(2026, 4, 24),
        Place(name="Frankfurt", city="Frankfurt", country="DE"),
        [
            _flight(
                datetime(2026, 4, 21, 9, 15),
                datetime(2026, 4, 21, 18, 40),
                "ORD",
                "FRA",
                "LH",
                "LH431",
                international=True,
            )
        ],
        [
            _hotel(
                "Marriott Frankfurt",
                "h_fra_01",
                "Frankfurt",
                "DE",
                date(2026, 4, 21),
                date(2026, 4, 24),
                190,
            )
        ],
    ),
    _trip(
        PRIYA_ID,
        "trip_priya_3",
        "Board meeting — Toronto",
        TripStatus.PAST,
        date(2026, 6, 9),
        date(2026, 6, 11),
        Place(name="Toronto", city="Toronto", country="CA"),
        [
            _flight(
                datetime(2026, 6, 9, 7, 30),
                datetime(2026, 6, 9, 10, 45),
                "ORD",
                "YYZ",
                "AC",
                "AC552",
                international=True,
            )
        ],
        [
            _hotel(
                "Hyatt Regency Toronto",
                "h_yyz_01",
                "Toronto",
                "CA",
                date(2026, 6, 9),
                date(2026, 6, 11),
                205,
            )
        ],
    ),
    # In-progress domestic trip — used by "which hotel am I at?" context cases.
    _trip(
        PRIYA_ID,
        "trip_priya_now",
        "Regional office — Dallas",
        TripStatus.IN_PROGRESS,
        date(2026, 9, 14),
        date(2026, 9, 17),
        Place(name="Dallas", city="Dallas", country="US"),
        [
            _flight(
                datetime(2026, 9, 14, 6, 45),
                datetime(2026, 9, 14, 9, 5),
                "ORD",
                "DFW",
                "AA",
                "AA1187",
                international=False,
            )
        ],
        [
            _hotel(
                "Marriott Dallas Downtown",
                "h_dfw_01",
                "Dallas",
                "US",
                date(2026, 9, 14),
                date(2026, 9, 17),
                178,
                booking_ref=PRIYA_DALLAS_HOTEL_REF,
            )
        ],
    ),
    # Upcoming international trip — counted, so it is the 4th, not a 4th still to come.
    _trip(
        PRIYA_ID,
        "trip_priya_next",
        "Regional summit — Singapore",
        TripStatus.UPCOMING,
        date(2026, 11, 3),
        date(2026, 11, 7),
        Place(name="Singapore", city="Singapore", country="SG"),
        [
            _flight(
                datetime(2026, 11, 3, 22, 10),
                datetime(2026, 11, 4, 20, 30),
                "ORD",
                "SIN",
                "SQ",
                "SQ35",
                international=True,
            )
        ],
    ),
]

SAM_TRIPS = [
    _trip(
        SAM_WHITFIELD_ID,
        "trip_sam_1",
        "Trade show — Barcelona",
        TripStatus.PAST,
        date(2026, 3, 3),
        date(2026, 3, 6),
        Place(name="Barcelona", city="Barcelona", country="ES"),
        [
            _flight(
                datetime(2026, 3, 3, 7, 0),
                datetime(2026, 3, 3, 10, 30),
                "DUB",
                "BCN",
                "EI",
                "EI562",
                international=True,
            )
        ],
        [
            _hotel(
                "Novotel Barcelona",
                "h_bcn_01",
                "Barcelona",
                "ES",
                date(2026, 3, 3),
                date(2026, 3, 6),
                120,
            )
        ],
        tenant="initech",
    ),
    _trip(
        SAM_WHITFIELD_ID,
        "trip_sam_now",
        "Partner visit — Amsterdam",
        TripStatus.IN_PROGRESS,
        date(2026, 9, 15),
        date(2026, 9, 18),
        Place(name="Amsterdam", city="Amsterdam", country="NL"),
        [
            _flight(
                datetime(2026, 9, 15, 6, 30),
                datetime(2026, 9, 15, 9, 50),
                "DUB",
                "AMS",
                "EI",
                "EI602",
                international=True,
            )
        ],
        [
            _hotel(
                "Ibis Amsterdam Centre",
                "h_ams_01",
                "Amsterdam",
                "NL",
                date(2026, 9, 15),
                date(2026, 9, 18),
                140,
            )
        ],
        tenant="initech",
    ),
]

TRIPS = PRIYA_TRIPS + SAM_TRIPS


# **A reservation that exists to be cancelled, because nothing else in the fixtures is
# cancellable.** Every other reservation here is created by holding and confirming an offer, so a
# fresh deployment has none — and "cancel my hotel reservation" had no reachable answer.
# `Reservation` already anticipates this case: its `starts_on` is optional precisely because "a
# reservation seeded directly by fixtures has no offer behind it".
#
# Hotel rather than air so the terms come back fully refundable, which is the more useful thing to
# demonstrate: the two-stage cancellation shows terms first and then cancels, and free cancellation
# makes the two stages visibly distinct rather than looking like one destructive call.
RESERVATIONS = [
    Reservation(
        tenant_id="globex",
        traveler_id=PRIYA_ID,
        booking_ref=PRIYA_DALLAS_HOTEL_REF,
        confirmation_number="MAR8830142",
        kind=TravelKind.HOTEL,
        description="Marriott Dallas Downtown, 14-17 September 2026, 3 nights",
        total=Money(amount=534, currency=Currency.USD),
        issued_at=datetime(2026, 8, 20, 14, 32),
        trip_id="trip_priya_now",
        starts_on="2026-09-14",
    )
]
