"""Arranger authorization and name resolution.

The interesting cases are the refusals and the ambiguities, because those are the
ones a model would otherwise paper over: booking against the wrong person's
record moves someone else's money, so "which Sam?" must be a question the system
asks rather than a coin it flips.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.service.arrangers import Resolution, authorized_scope, can_book_for, resolve_name
from seed import (
    ADAEZE_ID,
    MARCUS_ID,
    PRIYA_ID,
    SAM_ADEWALE_ID,
    SAM_OKONJO_ID,
    SAM_WHITFIELD_ID,
    seeded_repository,
)

GLOBEX = {"X-Tenant-Id": "globex"}
INITECH = {"X-Tenant-Id": "initech"}


@pytest.fixture
def repo():
    return seeded_repository()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(seeded_repository()))


class TestAuthorizedScope:
    def test_arranger_scope_includes_self_and_managed(self, repo):
        """Self is in scope — an arranger books their own travel too."""
        scope = {t.traveler_id for t in authorized_scope(repo, "globex", ADAEZE_ID)}
        assert ADAEZE_ID in scope
        assert {PRIYA_ID, SAM_OKONJO_ID, SAM_ADEWALE_ID} <= scope

    def test_plain_traveler_scope_is_exactly_themselves(self, repo):
        scope = authorized_scope(repo, "globex", PRIYA_ID)
        assert [t.traveler_id for t in scope] == [PRIYA_ID]

    def test_unknown_actor_has_empty_scope(self, repo):
        assert authorized_scope(repo, "globex", "trv_000000000000") == []

    def test_dangling_can_book_for_id_is_skipped_not_raised(self, repo):
        """A departed colleague narrows an arranger's scope; it must not break it.

        Marcus is in Adaeze's `can_book_for` but has no profile row, which is
        exactly the shape of a traveller who has left the company.
        """
        scope = {t.traveler_id for t in authorized_scope(repo, "globex", ADAEZE_ID)}
        assert MARCUS_ID not in scope
        assert PRIYA_ID in scope

    def test_scope_never_crosses_a_tenant(self, repo):
        """Asking for a Globex arranger under Initech resolves nobody."""
        assert authorized_scope(repo, "initech", ADAEZE_ID) == []


class TestCanBookFor:
    def test_arranger_may_book_for_managed_traveler(self, repo):
        assert can_book_for(repo, "globex", ADAEZE_ID, PRIYA_ID).allowed

    def test_anyone_may_book_for_themselves(self, repo):
        result = can_book_for(repo, "globex", PRIYA_ID, PRIYA_ID)
        assert result.allowed
        assert result.reason == "self"

    def test_plain_traveler_may_not_book_for_another(self, repo):
        assert not can_book_for(repo, "globex", PRIYA_ID, SAM_OKONJO_ID).allowed

    def test_cross_tenant_is_denied(self, repo):
        """Sam Whitfield is at Initech; no Globex arranger reaches him."""
        assert not can_book_for(repo, "globex", ADAEZE_ID, SAM_WHITFIELD_ID).allowed

    def test_unknown_and_unauthorized_are_indistinguishable(self, repo):
        """Distinguishing them would confirm an id exists to a caller with no right to know."""
        unknown = can_book_for(repo, "globex", ADAEZE_ID, "trv_000000000000")
        unauthorized = can_book_for(repo, "globex", ADAEZE_ID, SAM_WHITFIELD_ID)
        assert unknown.reason == unauthorized.reason


class TestNameResolution:
    """Two Sams inside Adaeze's authorised list, and a third at another tenant."""

    def test_unambiguous_name_resolves(self, repo):
        result = resolve_name(repo, "globex", ADAEZE_ID, "Priya")
        assert result.resolution is Resolution.UNIQUE
        assert result.traveler_id == PRIYA_ID

    def test_shared_first_name_is_ambiguous(self, repo):
        """Two matches surface as candidates; the id stays None so no caller can proceed."""
        result = resolve_name(repo, "globex", ADAEZE_ID, "Sam")
        assert result.resolution is Resolution.AMBIGUOUS
        assert {c.traveler_id for c in result.candidates} == {SAM_OKONJO_ID, SAM_ADEWALE_ID}
        assert result.traveler_id is None

    def test_candidates_carry_a_differentiator(self, repo):
        """ "Sam or Sam?" is a useless question."""
        candidates = resolve_name(repo, "globex", ADAEZE_ID, "Sam").candidates
        assert len({c.full_name for c in candidates}) == 2
        assert len({c.home_airport for c in candidates}) == 2

    def test_full_name_disambiguates(self, repo):
        result = resolve_name(repo, "globex", ADAEZE_ID, "Sam Adewale")
        assert result.resolution is Resolution.UNIQUE
        assert result.traveler_id == SAM_ADEWALE_ID

    def test_surname_alone_resolves_regardless_of_word_order(self, repo):
        result = resolve_name(repo, "globex", ADAEZE_ID, "Okonjo")
        assert result.traveler_id == SAM_OKONJO_ID

    def test_partial_surname_narrows(self, repo):
        result = resolve_name(repo, "globex", ADAEZE_ID, "Sam Ade")
        assert result.traveler_id == SAM_ADEWALE_ID

    def test_matching_is_case_insensitive(self, repo):
        assert resolve_name(repo, "globex", ADAEZE_ID, "pRIYa").traveler_id == PRIYA_ID

    def test_other_tenants_traveler_is_never_a_candidate(self, repo):
        """Sam Whitfield matches the same string and must not appear."""
        result = resolve_name(repo, "globex", ADAEZE_ID, "Sam")
        assert SAM_WHITFIELD_ID not in {c.traveler_id for c in result.candidates}

    def test_plain_traveler_resolves_only_themselves(self, repo):
        """Priya is not an arranger, so another traveller's name resolves to nobody."""
        assert resolve_name(repo, "globex", PRIYA_ID, "Sam").resolution is Resolution.NONE
        assert resolve_name(repo, "globex", PRIYA_ID, "Priya").traveler_id == PRIYA_ID

    def test_unknown_name_is_none_not_a_guess(self, repo):
        result = resolve_name(repo, "globex", ADAEZE_ID, "Bartholomew")
        assert result.resolution is Resolution.NONE
        assert result.candidates == []

    def test_blank_name_resolves_nobody(self, repo):
        """An empty string must not match everyone in scope."""
        assert resolve_name(repo, "globex", ADAEZE_ID, "   ").resolution is Resolution.NONE


class TestArrangerApi:
    def test_list_authorized_travelers(self, client):
        body = client.get(f"/v1/arrangers/{ADAEZE_ID}/travelers", headers=GLOBEX).json()
        assert {c["traveler_id"] for c in body} >= {PRIYA_ID, SAM_OKONJO_ID, SAM_ADEWALE_ID}

    def test_listing_never_leaks_pii(self, client):
        """The response names people; it must not carry their passports."""
        body = client.get(f"/v1/arrangers/{ADAEZE_ID}/travelers", headers=GLOBEX).json()
        assert all(set(c) == {"traveler_id", "full_name", "home_airport"} for c in body)

    def test_non_arranger_gets_only_themselves(self, client):
        body = client.get(f"/v1/arrangers/{PRIYA_ID}/travelers", headers=GLOBEX).json()
        assert [c["traveler_id"] for c in body] == [PRIYA_ID]

    def test_unknown_arranger_is_empty_not_404(self, client):
        """ "You may act for nobody" is the right answer, and it leaks nothing."""
        response = client.get("/v1/arrangers/trv_000000000000/travelers", headers=GLOBEX)
        assert response.status_code == 200
        assert response.json() == []

    def test_can_book_returns_200_for_a_denial(self, client):
        """A denial is an answer, not an HTTP error — the caller's job is to ask."""
        response = client.get(f"/v1/arrangers/{PRIYA_ID}/can-book/{SAM_OKONJO_ID}", headers=GLOBEX)
        assert response.status_code == 200
        assert response.json()["allowed"] is False

    def test_can_book_allows_managed_traveler(self, client):
        body = client.get(f"/v1/arrangers/{ADAEZE_ID}/can-book/{PRIYA_ID}", headers=GLOBEX).json()
        assert body["allowed"] is True

    def test_resolve_ambiguous_name_is_200_with_candidates(self, client):
        body = client.get(
            f"/v1/arrangers/{ADAEZE_ID}/resolve", params={"name": "Sam"}, headers=GLOBEX
        ).json()
        assert body["resolution"] == "ambiguous"
        assert len(body["candidates"]) == 2

    def test_resolve_requires_a_name(self, client):
        response = client.get(
            f"/v1/arrangers/{ADAEZE_ID}/resolve", params={"name": ""}, headers=GLOBEX
        )
        assert response.status_code == 422

    def test_tenant_header_still_required(self, client):
        assert client.get(f"/v1/arrangers/{ADAEZE_ID}/travelers").status_code == 401

    def test_arranger_from_another_tenant_resolves_nobody(self, client):
        """Adaeze's id under an Initech session must not reach her Globex scope."""
        body = client.get(f"/v1/arrangers/{ADAEZE_ID}/travelers", headers=INITECH).json()
        assert body == []
