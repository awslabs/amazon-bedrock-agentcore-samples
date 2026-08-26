"""API tests.

The isolation checks live here: two tenants asking the same question get
different correct answers, the same search twice is identical, and no request can
reach another tenant's data.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

# Imported rather than recomputed. Three assertions below need the reservation reference an offer
# becomes, and spelling `bkg_<suffix>` out here would tie them to a derivation they do not own — the
# copies would keep passing while the service changed under them.
from app.service.booking import _booking_ref
from seed import ADAEZE_ID, PRIYA_ID, SAM_WHITFIELD_ID, seeded_repository

GLOBEX = {"X-Tenant-Id": "globex"}
INITECH = {"X-Tenant-Id": "initech"}
PRIYA = {**GLOBEX, "X-Traveler-Id": PRIYA_ID}
SAM = {**INITECH, "X-Traveler-Id": SAM_WHITFIELD_ID}

AIR_SEARCH = {"origin": "Dublin", "destination": "Atlanta", "depart_on": "2026-09-15"}
HOTEL_SEARCH = {"destination": "Dublin", "check_in": "2026-09-15", "check_out": "2026-09-18"}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(seeded_repository()))


class TestMeta:
    def test_health(self, client):
        assert client.get("/health").json()["status"] == "ok"

    def test_openapi_generates(self, client):
        """A valid spec, asserted on a path the tools actually call.

        This used to assert `/v1/hotels/{property_code}`, an endpoint that existed only to be
        served as an OpenAPI Gateway target. That target was never deployable here and the
        endpoint is gone, so the check moved to a route a tool really uses.
        """
        spec = client.get("/openapi.json").json()
        assert "/v1/policy/{topic}" in spec["paths"]


class TestAuthentication:
    def test_tenant_header_required(self, client):
        """Missing tenant is unauthenticated, not "all tenants"."""
        assert client.get("/v1/trips").status_code == 401

    def test_unknown_tenant_is_404_not_empty(self, client):
        """A typo must not look like a tenant with no data."""
        response = client.get("/v1/policy", headers={"X-Tenant-Id": "acme"})
        assert response.status_code == 404


class TestTenantIsolation:
    """The two curls that prove the thesis."""

    def test_same_question_two_tenants_two_answers(self, client):
        globex = client.get("/v1/policy/air", headers=GLOBEX).json()
        initech = client.get("/v1/policy/air", headers=INITECH).json()

        assert globex["core"]["cabin_rule"]["type"] == "trip_count"
        assert globex["core"]["cabin_rule"]["every_nth_trip"] == 4
        assert initech["core"]["cabin_rule"]["type"] == "never"
        assert initech["core"]["advance_purchase_days"] == 7

    def test_hotel_caps_and_currencies_differ(self, client):
        globex = client.get("/v1/policy/hotel", headers=GLOBEX).json()
        initech = client.get("/v1/policy/hotel", headers=INITECH).json()
        assert globex["core"]["hotel_nightly_cap"] == {"amount": "250.00", "currency": "USD"}
        assert initech["core"]["hotel_nightly_cap"] == {"amount": "150.00", "currency": "EUR"}

    def test_search_is_reproducible(self, client):
        first = client.post("/v1/booking/search/air", json=AIR_SEARCH, headers=GLOBEX)
        second = client.post("/v1/booking/search/air", json=AIR_SEARCH, headers=GLOBEX)
        assert first.json() == second.json()


class TestIsolation:
    def test_cannot_read_another_tenants_traveler(self, client):
        assert client.get(f"/v1/travelers/{SAM_WHITFIELD_ID}", headers=GLOBEX).status_code == 404
        assert client.get(f"/v1/travelers/{PRIYA_ID}", headers=INITECH).status_code == 404

    def test_trip_list_never_crosses_tenants(self, client):
        trips = client.get("/v1/trips", headers=INITECH).json()
        assert all(t["tenant_id"] == "initech" for t in trips)

    def test_cannot_read_another_tenants_trip(self, client):
        assert client.get("/v1/trips/trip_priya_1", headers=INITECH).status_code == 404


class TestTrips:
    def test_list_and_filter_by_status(self, client):
        in_progress = client.get(
            "/v1/trips", headers=GLOBEX, params={"traveler": PRIYA_ID, "status": "in_progress"}
        ).json()
        assert len(in_progress) == 1
        assert in_progress[0]["trip_id"] == "trip_priya_now"

    def test_hotel_segment_carries_a_geocodable_address(self, client):
        """The location tools geocode a string, so an address must be present."""
        trip = client.get("/v1/trips/trip_priya_now", headers=GLOBEX).json()
        hotel = trip["hotel_segments"][0]
        assert hotel["location"]["address"]
        assert hotel["location"]["city"] == "Dallas"


class TestProfile:
    def test_backend_returns_full_pii(self, client):
        """Curation is the tool layer's job — the backend must have it to curate."""
        priya = client.get(f"/v1/travelers/{PRIYA_ID}", headers=GLOBEX).json()
        assert priya["passports"][0]["number"]
        assert priya["payment_instruments"][0]["last_four"]

    def test_arranger_carries_can_book_for(self, client):
        adaeze = client.get(f"/v1/travelers/{ADAEZE_ID}", headers=GLOBEX).json()
        assert PRIYA_ID in adaeze["can_book_for"]


class TestSearch:
    def test_air_search_is_policy_annotated(self, client):
        result = client.post("/v1/booking/search/air", json=AIR_SEARCH, headers=GLOBEX).json()
        assert result["resolved_origin"] == "DUB"
        assert result["resolved_destination"] == "ATL"
        assert all("policy_status" in o for o in result["options"])

    def test_summary_carries_computed_aggregates(self, client):
        """Counts the model must never do itself."""
        result = client.post("/v1/booking/search/hotels", json=HOTEL_SEARCH, headers=GLOBEX).json()
        summary = result["summary"]
        counted = sum(1 for o in result["options"] if o["policy_status"] == "in_policy")
        assert summary["in_policy_options"] == counted

    def test_currency_follows_the_tenant(self, client):
        globex = client.post("/v1/booking/search/hotels", json=HOTEL_SEARCH, headers=GLOBEX).json()
        initech = client.post(
            "/v1/booking/search/hotels", json=HOTEL_SEARCH, headers=INITECH
        ).json()
        assert globex["options"][0]["nightly_rate"]["currency"] == "USD"
        assert initech["options"][0]["nightly_rate"]["currency"] == "EUR"

    def test_preferred_chain_flagged_from_profile(self, client):
        """Priya prefers Marriott and Hyatt — no extra round trip needed."""
        result = client.post("/v1/booking/search/hotels", json=HOTEL_SEARCH, headers=PRIYA).json()
        flagged = [o for o in result["options"] if o["is_preferred_chain"]]
        assert all(o["chain"] in {"Marriott", "Hyatt"} for o in flagged)

    def test_unsupported_airport_refuses_with_suggestions(self, client):
        """Refusal beats invention — no coordinates means no plausible duration."""
        response = client.post(
            "/v1/booking/search/air",
            json={**AIR_SEARCH, "destination": "Atlantis"},
            headers=GLOBEX,
        )
        assert response.status_code == 404
        assert response.json()["detail"]["suggestions"]

    def test_absent_origin_resolves_to_the_home_airport(self, client):
        """ "Find me a flight to London" names no origin, and must still search.

        **The commonest possible flight request used to 422.** `origin` was declared required while
        the tool deliberately omitted it — documenting that absent means "the traveller's home
        airport" — so the model could only report "I couldn't reach the flight search system".
        Priya's profile says ORD, so an originless search must return that route.
        """
        no_origin = {"destination": "London", "depart_on": "2026-11-10"}
        result = client.post("/v1/booking/search/air", json=no_origin, headers=PRIYA)
        assert result.status_code == 200, result.text
        options = result.json()["options"]
        assert options, "an originless search returned no options"
        assert all(o["depart_airport"] == "ORD" for o in options), [
            o["depart_airport"] for o in options
        ]

    def test_absent_origin_without_a_profile_asks_rather_than_guessing(self, client):
        """No traveller header means no home airport, and a guessed hub is worse than a question.

        A plausible itinerary from the wrong city is the failure mode avoided here: it looks
        correct and is unusable. 400 with a question, not 422 — the request was legitimate.
        """
        response = client.post(
            "/v1/booking/search/air",
            json={"destination": "London", "depart_on": "2026-11-10"},
            headers=GLOBEX,
        )
        assert response.status_code == 400
        assert "flying from" in response.json()["detail"]["message"]


class TestOfferLifecycle:
    def _first_option(self, client, headers):
        result = client.post("/v1/booking/search/air", json=AIR_SEARCH, headers=headers).json()
        return result["options"][0]

    def _hold(self, client, headers=PRIYA):
        option = self._first_option(client, headers)
        return client.post(
            "/v1/booking/hold",
            json={
                "kind": "air",
                "option_id": option["option_id"],
                "origin": "Dublin",
                "destination": "Atlanta",
                "depart_on": "2026-09-15",
            },
            headers=headers,
        )

    def test_hold_returns_a_handle_and_expiry(self, client):
        body = self._hold(client).json()
        assert body["offer_id"].startswith("off_")
        assert body["expires_at"]
        assert body["display_price"]["currency"] == "USD"

    def test_two_holds_on_the_same_option_are_separate_offers(self, client):
        """Holding twice gives two handles, and the **first one still confirms**.

        `offer_id` used to be derived from the option id, so a second hold overwrote the first row
        at
        the same key — and confirming the first handle then hit a row that was a different offer or
        already consumed, reported as **404**. That reads as an expired or foreign handle, and
        because
        it only happens when the same option is held twice it survived the whole exit suite
        intermittently.

        Different option ids could collide the same way: `opt_f1062d6656_1` and `opt_062d6656_1`
        both
        truncated to the same ten characters.
        """
        first = self._hold(client).json()["offer_id"]
        second = self._hold(client).json()["offer_id"]
        assert first != second, "two holds must not share an id"

        # The older handle is still valid — nothing overwrote it.
        response = client.post("/v1/booking/confirm", json={"offer_id": first}, headers=PRIYA)
        assert response.status_code == 200
        assert response.json()["confirmation_number"]

    def test_hold_rejects_an_option_id_that_contradicts_the_dates(self, client):
        """A real option id with the wrong dates is 422, not 404.

        **The distinction is the point.** An option id encodes the search that produced it, so
        parameters that disagree with it describe a different query — the option was never offered
        under *these* dates. Reporting 404 ("no longer available") sends the caller searching again
        and apologising for inventory that never existed, which is what an agent recalling an option
        from an earlier turn actually did after it retyped the year.
        """
        option = self._first_option(client, PRIYA)
        response = client.post(
            "/v1/booking/hold",
            json={
                "kind": "air",
                "option_id": option["option_id"],
                "origin": "Dublin",
                "destination": "Atlanta",
                # A year out from the search — the mistake the model actually made.
                "depart_on": "2024-09-15",
            },
            headers=PRIYA,
        )
        assert response.status_code == 422
        assert "does not belong" in response.json()["detail"]

    def test_hold_still_reports_a_genuinely_unknown_option_as_not_found(self, client):
        """The paired case, or the check above would pass on a backend that 422s everything.

        A well-formed id whose digest matches these parameters but whose index does not exist is
        genuinely absent — a 404, and it must stay distinguishable from the mismatch above.
        """
        option = self._first_option(client, PRIYA)
        digest = option["option_id"].rsplit("_", 1)[0]
        response = client.post(
            "/v1/booking/hold",
            json={
                "kind": "air",
                # Same query, an index far beyond what generation produces.
                "option_id": f"{digest}_999",
                "origin": "Dublin",
                "destination": "Atlanta",
                "depart_on": "2026-09-15",
            },
            headers=PRIYA,
        )
        assert response.status_code == 404

    def test_hold_accepts_an_equivalent_phrasing_of_the_destination(self, client):
        """`DUB` and `Dublin` seed the same query, so neither is a mismatch.

        Guards the obvious over-correction: comparing raw strings instead of resolved codes would
        reject a caller who simply said the city a different way.
        """
        option = self._first_option(client, PRIYA)
        response = client.post(
            "/v1/booking/hold",
            json={
                "kind": "air",
                "option_id": option["option_id"],
                "origin": "DUB",
                "destination": "ATL",
                "depart_on": "2026-09-15",
            },
            headers=PRIYA,
        )
        assert response.status_code == 200

    def test_hold_requires_a_traveler(self, client):
        option = self._first_option(client, GLOBEX)
        response = client.post(
            "/v1/booking/hold",
            json={
                "kind": "air",
                "option_id": option["option_id"],
                "origin": "Dublin",
                "destination": "Atlanta",
                "depart_on": "2026-09-15",
            },
            headers=GLOBEX,
        )
        assert response.status_code == 400

    def test_confirm_books_the_held_offer(self, client):
        offer_id = self._hold(client).json()["offer_id"]
        reservation = client.post(
            "/v1/booking/confirm", json={"offer_id": offer_id}, headers=PRIYA
        ).json()
        assert reservation["confirmation_number"].startswith("TRV")
        assert reservation["status"] == "confirmed"

    def test_confirm_is_idempotent_rather_than_replayable(self, client):
        """A repeated confirmation returns the same booking, and books only once.

        **This asserted a 409, and the 409 was the defect.** Booking once was always correct;
        telling the caller "that hold is no longer valid, nothing has been charged" was not, because
        the charge had happened. A lost response looks exactly like a failure from the client, so a
        retry is the right thing for a client to do — and a refusal answers it with the opposite of
        the truth about someone's money.

        Returning the existing reservation satisfies both halves: one booking, and a truthful answer
        to whoever asks twice. `booking_ref` is derived from the offer, so it was already the
        idempotency key — nothing new had to be introduced to look the earlier attempt up.
        """
        offer_id = self._hold(client).json()["offer_id"]
        first = client.post("/v1/booking/confirm", json={"offer_id": offer_id}, headers=PRIYA)
        second = client.post("/v1/booking/confirm", json={"offer_id": offer_id}, headers=PRIYA)
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert second.json()["booking_ref"] == first.json()["booking_ref"]
        assert second.json()["confirmation_number"] == first.json()["confirmation_number"]
        # Asserted on stored rows too, because two 200s that left two reservations would satisfy
        # everything above while being the original bug.
        stored = [
            r
            for r in client.app.state.repository.reservations("globex")
            if r.booking_ref == first.json()["booking_ref"]
        ]
        assert len(stored) == 1, f"{len(stored)} reservations for one hold"

    def test_another_tenant_cannot_use_the_handle(self, client):
        """A copied `offer_id` is indistinguishable from one that never existed."""
        offer_id = self._hold(client).json()["offer_id"]
        response = client.post("/v1/booking/confirm", json={"offer_id": offer_id}, headers=SAM)
        assert response.status_code == 404

    def test_unknown_handle_is_404(self, client):
        response = client.post(
            "/v1/booking/confirm", json={"offer_id": "off_fabricated"}, headers=PRIYA
        )
        assert response.status_code == 404


class TestCancellation:
    def test_terms_are_available_before_cancelling(self, client):
        # Book something first.
        option = client.post("/v1/booking/search/air", json=AIR_SEARCH, headers=PRIYA).json()[
            "options"
        ][0]
        offer = client.post(
            "/v1/booking/hold",
            json={
                "kind": "air",
                "option_id": option["option_id"],
                "origin": "Dublin",
                "destination": "Atlanta",
                "depart_on": "2026-09-15",
            },
            headers=PRIYA,
        ).json()
        booking = client.post(
            "/v1/booking/confirm", json={"offer_id": offer["offer_id"]}, headers=PRIYA
        ).json()

        terms = client.get(
            f"/v1/booking/reservations/{booking['booking_ref']}/cancellation-terms",
            headers=PRIYA,
        ).json()
        assert terms["penalties"]

        cancelled = client.post(
            f"/v1/booking/reservations/{booking['booking_ref']}/cancel", headers=PRIYA
        ).json()
        assert cancelled["status"] == "cancelled"


class TestOriginResolutionSurvivesTheBookingPath:
    """An option found without an origin must still be holdable.

    **The bug this pins was introduced by making `origin` optional.** Options are never stored —
    they are regenerated from their search parameters, which works only because generation is
    deterministic on its query. Search resolved an absent origin to the traveller's home airport;
    the hold left it empty, seeded differently, produced different option ids, and answered
    "that option is no longer available; search again" for one the traveller was looking at.
    A 404 telling someone to search again for something that cannot be found again is the worst
    shape of this failure, and only a hold-after-originless-search exercises it.
    """

    def test_hold_succeeds_for_an_option_found_without_an_origin(self, client):
        found = client.post(
            "/v1/booking/search/air",
            json={"destination": "London", "depart_on": "2026-11-10"},
            headers=PRIYA,
        ).json()["options"][0]
        held = client.post(
            "/v1/booking/hold",
            json={
                "kind": "air",
                "option_id": found["option_id"],
                "destination": "London",
                "depart_on": "2026-11-10",
            },
            headers=PRIYA,
        )
        assert held.status_code == 200, held.text
        # The price survived the round trip, so the regenerated option is the one that was shown —
        # a different origin would have produced a different fare, not just a different id.
        assert held.json()["display_price"]["amount"] == found["price"]["amount"]
        assert "ORD-LHR" in held.json()["description"]


class TestSeededScenarios:
    """Suite G's conditions, armed per session rather than per tenant.

    **Session scope is the safety property.** A tenant-wide switch would leave the deployed demo in
    "every search times out" for whoever arrived next; scoping to a session id, which is unguessable
    and expires on its own, means an eval run can only affect its own conversation.
    """

    HEADERS = {**PRIYA, "X-Session-Id": "test-scenarios"}

    def _arm(self, client, *names):
        client.app.state.repository.put_scenarios("globex", "test-scenarios", set(names))

    def test_no_scenario_is_the_default(self, client):
        self._arm(client)
        cap = client.get("/v1/policy/hotel", headers=self.HEADERS).json()
        assert cap["core"]["hotel_nightly_cap"]["amount"] == "250.00"

    def test_timeout_is_a_gateway_timeout_not_a_missing_policy(self, client):
        """504, never 404. "Your company has no policy" is the dangerous misreading of a stall."""
        self._arm(client, "timeout")
        assert client.get("/v1/policy/hotel", headers=self.HEADERS).status_code == 504

    def test_lowered_cap_flips_a_verdict_that_was_in_policy(self, client):
        """The scenario the tool-not-context rule rests on: 240 was fine at 250, and is not
        at 200."""
        self._arm(client)
        before = client.post(
            "/v1/eligibility",
            json={
                "check": "hotel",
                "nightly_rate": {"amount": "240.00", "currency": "USD"},
                "star_rating": 4,
            },
            headers=self.HEADERS,
        ).json()
        assert before["eligible"] is True

        self._arm(client, "policy_cap_lowered")
        after = client.post(
            "/v1/eligibility",
            json={
                "check": "hotel",
                "nightly_rate": {"amount": "240.00", "currency": "USD"},
                "star_rating": 4,
            },
            headers=self.HEADERS,
        ).json()
        assert after["eligible"] is False
        assert after["reason_code"] == "hotel_out_of_policy"

    def test_a_scenario_does_not_leak_to_another_session(self, client):
        """The property that makes arming safe on a live deployment."""
        self._arm(client, "timeout")
        other = {**PRIYA, "X-Session-Id": "someone-else"}
        assert client.get("/v1/policy/hotel", headers=other).status_code == 200

    def test_zero_availability_returns_no_options_rather_than_inventing_them(self, client):
        self._arm(client, "no_availability")
        result = client.post(
            "/v1/booking/search/hotels",
            json={"destination": "Amsterdam", "check_in": "2026-12-05", "check_out": "2026-12-08"},
            headers=self.HEADERS,
        ).json()
        assert result["options"] == []

    def test_expired_offer_is_found_and_reported_expired_not_missing(self, client):
        """410, not 404. A hold that never existed invites re-booking; an expired one invites
        re-searching, and only one of those is correct."""
        clean = {**PRIYA, "X-Session-Id": "clean-for-hold"}
        found = client.post(
            "/v1/booking/search/hotels",
            json={"destination": "Amsterdam", "check_in": "2026-12-05", "check_out": "2026-12-08"},
            headers=clean,
        ).json()["options"][0]

        self._arm(client, "expired_offer")
        held = client.post(
            "/v1/booking/hold",
            json={
                "kind": "hotel",
                "option_id": found["option_id"],
                "destination": "Amsterdam",
                "check_in": "2026-12-05",
                "check_out": "2026-12-08",
            },
            headers=self.HEADERS,
        )
        assert held.status_code == 200, held.text
        confirmed = client.post(
            "/v1/booking/confirm",
            json={"offer_id": held.json()["offer_id"]},
            headers=self.HEADERS,
        )
        assert confirmed.status_code == 410

    def test_price_drift_refuses_to_charge_the_new_amount(self, client):
        """409 carrying both prices, so the agent can ask again rather than charge silently."""
        clean = {**PRIYA, "X-Session-Id": "clean-for-drift"}
        found = client.post(
            "/v1/booking/search/air",
            json={"destination": "London", "depart_on": "2026-11-10"},
            headers=clean,
        ).json()["options"][0]
        held = client.post(
            "/v1/booking/hold",
            json={
                "kind": "air",
                "option_id": found["option_id"],
                "destination": "London",
                "depart_on": "2026-11-10",
            },
            headers=clean,
        )
        assert held.status_code == 200, held.text

        self._arm(client, "price_drift")
        confirmed = client.post(
            "/v1/booking/confirm", json={"offer_id": held.json()["offer_id"]}, headers=self.HEADERS
        )
        assert confirmed.status_code == 409
        detail = confirmed.json()["detail"]
        assert detail["previous_price"] != detail["current_price"]


class TestConfirmIsRaceSafe:
    """Two confirmations of one hold must produce one booking, however they arrive.

    **`test_confirm_is_not_replayable` above only ever tested the sequential case**, and passed on a
    status check in Python that two concurrent requests both satisfy. `confirm` reads the offer,
    decides it is holdable, re-prices, then writes — so between the read and the write another
    request can do the same thing, and before `consume_offer` both wrote. Two reservations, and in a
    real system two charges.

    The invariant is one reservation and one refusal, and it is asserted on the *stored* rows rather
    than on the responses: a 409 that still left a second booking behind would satisfy a
    response-only assertion while being exactly the bug.
    """

    def _held_offer(self, client):
        option = client.post(
            "/v1/booking/search/hotels",
            json={"destination": "Amsterdam", "check_in": "2026-12-05", "check_out": "2026-12-08"},
            headers=PRIYA,
        ).json()["options"][0]
        held = client.post(
            "/v1/booking/hold",
            json={
                "kind": "hotel",
                "option_id": option["option_id"],
                "destination": "Amsterdam",
                "check_in": "2026-12-05",
                "check_out": "2026-12-08",
            },
            headers=PRIYA,
        )
        assert held.status_code == 200, held.text
        return held.json()["offer_id"]

    def test_concurrent_confirms_book_once(self, monkeypatch, client):
        """Both requests are forced inside the read-check-write window at once.

        **Threads alone do not reproduce this, and a test that only used threads is worse than no
        test.** Written that way first, it passed with the conditional write removed: the window
        between reading the offer and writing it is a few microseconds of dict access, so the two
        requests serialise by luck and the second is caught by the ordinary status check. It looked
        like a concurrency test and proved the sequential path twice.

        So the window is held open deliberately. `_current_price` runs after the status check and
        before the write — the re-pricing step — so delaying it puts both requests past the check
        and neither past the write, which is the interleaving that produced two bookings.
        """
        import concurrent.futures
        import time

        from app.service import booking as booking_service

        real_price = booking_service._current_price

        def slow_price(*args, **kwargs):
            time.sleep(0.3)
            return real_price(*args, **kwargs)

        monkeypatch.setattr(booking_service, "_current_price", slow_price)

        offer_id = self._held_offer(client)

        def confirm():
            return client.post(
                "/v1/booking/confirm", json={"offer_id": offer_id}, headers=PRIYA
            ).status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(confirm), pool.submit(confirm)]
            statuses = sorted(f.result() for f in futures)

        # **Both succeed now, and the invariant moved to the stored rows where it belongs.** This
        # asserted `[200, 409]`, which conflated two things: that only one booking is created (the
        # real requirement) and that the loser is told it failed (wrong — the booking it asked for
        # exists). The loser now reads the winner's reservation back and returns it, so the count
        # below is the assertion that carries the meaning.
        assert statuses == [200, 200], statuses
        reservations = [
            r
            for r in client.app.state.repository.reservations("globex")
            if r.booking_ref == _booking_ref(offer_id)
        ]
        assert len(reservations) == 1, f"{len(reservations)} reservations for one hold"

    def test_the_offer_is_spent_even_though_only_one_writer_won(self, client):
        """The winner's transition must have landed, or the hold could be confirmed again later."""
        from app.models import OfferStatus

        offer_id = self._held_offer(client)
        assert (
            client.post(
                "/v1/booking/confirm", json={"offer_id": offer_id}, headers=PRIYA
            ).status_code
            == 200
        )
        offer = client.app.state.repository.offer("globex", offer_id)
        assert offer.status is OfferStatus.CONSUMED

    def test_a_conflict_leaves_no_partial_write(self, client):
        """An offer consumed with no reservation is the worst outcome available.

        That traveller has spent their hold and has nothing to show for it, and cannot retry.
        Asserted here because the in-memory store makes the pair atomic by construction and the
        real one uses `TransactWriteItems` — a refactor that split them breaks this test rather
        than a production booking.
        """
        offer_id = self._held_offer(client)
        client.post("/v1/booking/confirm", json={"offer_id": offer_id}, headers=PRIYA)
        second = client.post("/v1/booking/confirm", json={"offer_id": offer_id}, headers=PRIYA)
        # 200 rather than 409: the replay is answered with the booking that exists. What this test
        # is for is the pair below — consumed offer *and* a reservation — not the status.
        assert second.status_code == 200

        repo = client.app.state.repository
        assert repo.offer("globex", offer_id).status.value == "consumed"
        assert [r for r in repo.reservations("globex") if r.booking_ref == _booking_ref(offer_id)]

    def test_consuming_an_offer_that_is_not_held_is_refused_by_storage(self, client):
        """The contract the in-memory store exists to cover, asserted directly.

        The route-level tests above prove the behaviour; this proves the *storage* rule, which is
        what `DynamoRepository` implements with a `ConditionExpression`. Without it here, the
        condition would live only in code no test exercises.
        """
        from datetime import datetime

        from app.models import Reservation
        from app.repository import OfferConflictError

        offer_id = self._held_offer(client)
        repo = client.app.state.repository
        offer = repo.offer("globex", offer_id)
        reservation = Reservation(
            tenant_id="globex",
            traveler_id=PRIYA_ID,
            booking_ref=_booking_ref(offer_id),
            confirmation_number="TRVTEST",
            kind=offer.kind,
            description=offer.description,
            total=offer.frozen_price,
            issued_at=datetime(2026, 12, 1, 12, 0),
        )
        repo.consume_offer(offer, reservation)
        with pytest.raises(OfferConflictError):
            repo.consume_offer(offer, reservation)
