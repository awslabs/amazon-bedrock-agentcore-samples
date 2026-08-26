"""PII curation unit tests — no AWS, no network.

The curation functions are pure over a raw backend record, so the leak lessons are pinned
here rather than only in a live integration run. The label-digit case is the one that
actually escaped a field-level allowlist.
"""

from tools.profile.handler import _loyalty, _passports, _payment, _preferences, _strip_digit_groups

RAW_PRIYA = {
    "full_name": "Priya Raghunathan",
    "passports": [{"country": "US", "number": "X4471902", "expires_on": "2030-06-30"}],
    "loyalty": [{"program": "United MileagePlus", "tier": "Gold", "number": "UA-2213847"}],
    "payment_instruments": [
        {
            "payment_profile_id": "pp_globex_priya",
            "display_label": "Visa •••4821 — Globex corporate",
            "last_four": "4821",
        }
    ],
    "preferences": {"home_airport": "ORD", "preferred_hotel_chains": ["Marriott"]},
}


class TestPassports:
    def test_country_kept_number_dropped(self):
        out = _passports(RAW_PRIYA["passports"])
        assert out[0]["country"] == "US"
        assert "number" not in out[0]

    def test_expiry_kept(self):
        assert _passports(RAW_PRIYA["passports"])[0]["expires_on"] == "2030-06-30"


class TestLoyalty:
    def test_tier_kept_number_dropped(self):
        out = _loyalty(RAW_PRIYA["loyalty"])
        assert out[0]["tier"] == "Gold"
        assert "number" not in out[0]
        assert "UA-2213847" not in str(out)


class TestPayment:
    def test_reference_kept(self):
        out = _payment(RAW_PRIYA["payment_instruments"])
        assert out[0]["payment_profile_id"] == "pp_globex_priya"

    def test_last_four_field_dropped(self):
        assert "last_four" not in _payment(RAW_PRIYA["payment_instruments"])[0]

    def test_label_digits_stripped(self):
        """The bug that escaped the allowlist: digits inside a human-readable label."""
        label = _payment(RAW_PRIYA["payment_instruments"])[0]["label"]
        assert "4821" not in label
        assert "Visa" in label and "Globex" in label  # still identifies the card


class TestStripDigits:
    def test_strips_card_run(self):
        assert "4821" not in _strip_digit_groups("Visa •••4821 — Globex corporate")

    def test_keeps_short_runs_out(self):
        # 3+ digits go; the point is to be blunt on backend-composed strings.
        assert _strip_digit_groups("Amex ••••1006 corporate").count("1006") == 0

    def test_none_stays_none(self):
        assert _strip_digit_groups(None) is None

    def test_no_digits_unchanged(self):
        assert _strip_digit_groups("Corporate travel card") == "Corporate travel card"


class TestPreferences:
    def test_declared_prefs_pass_through(self):
        out = _preferences(RAW_PRIYA["preferences"])
        assert out["home_airport"] == "ORD"
        assert out["preferred_hotel_chains"] == ["Marriott"]


class TestProfileCard:
    """The card is the curated view, and must withhold exactly what `facts` withholds.

    **This is the surface most likely to leak, because it is the one that renders.** The curation
    helpers above are careful; a card assembled from the raw backend response would walk straight
    around all of them, and it would look right on screen while doing it. So the assertion is not
    "the card has four fields" but "none of the three secrets appears anywhere in it".
    """

    def _card(self):
        facts = {
            "full_name": RAW_PRIYA["full_name"],
            "preferences": _preferences(RAW_PRIYA["preferences"]),
            "loyalty": _loyalty(RAW_PRIYA["loyalty"]),
            "passports": _passports(RAW_PRIYA["passports"]),
            "payment_methods": _payment(RAW_PRIYA["payment_instruments"]),
        }
        return {
            "traveler_name": facts.get("full_name"),
            "home_airport": (facts.get("preferences") or {}).get("home_airport"),
            "loyalty": facts.get("loyalty") or [],
            "passport_country": next(
                (p.get("country") for p in facts.get("passports") or [] if p.get("country")), None
            ),
        }

    def test_contract_fields_are_all_present(self):
        """`REQUIRED_DATA[CardType.PROFILE]` is the contract the frontend renders against."""
        from shared.cards import REQUIRED_DATA, CardType

        assert set(self._card()) >= REQUIRED_DATA[CardType.PROFILE]

    def test_carries_the_identifying_values(self):
        data = self._card()
        assert data["traveler_name"] == "Priya Raghunathan"
        assert data["home_airport"] == "ORD"
        assert data["passport_country"] == "US"

    def test_withholds_every_number(self):
        """Passport number, loyalty number, card digits — none may reach the rendered card."""
        rendered = str(self._card())
        assert "X4471902" not in rendered
        assert "UA-2213847" not in rendered
        assert "4821" not in rendered
