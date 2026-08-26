"""Citation deduplication — no AWS, no network.

**Why this exists at all.** `search_policy_knowledge` used to return citations only inside
`facts.passages` — the model's own input, never forwarded to the frontend (see `stream.py`'s
`payloads_in`/`cards_in`: only the `cards` array crosses that boundary). `documents.py`'s presign
route and the frontend's `documentUrl()` helper were both built and both unused — a citation with
nowhere to go. `_deduplicated_citations` is the piece that turns passages into the one card per
document a reader can actually click, and it is worth pinning here because the failure mode is
silent: a duplicate card is not an error, it is a second identical tile a traveller has no reason
to notice is wrong.
"""

from __future__ import annotations

from shared.cards import CardType, assert_valid, card
from tools.knowledge.handler import _deduplicated_citations

GLOBEX_CAP = {
    "text": "cap text",
    "citation": {"label": "Globex policy", "doc_id": "pol_globex_2026"},
}
GLOBEX_CABIN = {
    "text": "cabin text",
    "citation": {"label": "Globex policy", "doc_id": "pol_globex_2026"},
}
INITECH_CAP = {
    "text": "initech cap",
    "citation": {"label": "Initech policy", "doc_id": "pol_initech_2026"},
}
NO_DOC_ID = {"text": "orphan passage", "citation": {"label": "Untitled", "doc_id": None}}


class TestDeduplication:
    def test_one_document_cited_twice_becomes_one_card(self):
        """A cap rule and a cabin rule from the same policy file must not double the tile."""
        kept = _deduplicated_citations([GLOBEX_CAP, GLOBEX_CABIN])
        assert kept == [GLOBEX_CAP]

    def test_first_occurrence_wins(self):
        """The most relevant passage decides the card's position — retrieval already ranked
        these."""
        kept = _deduplicated_citations([GLOBEX_CABIN, GLOBEX_CAP])
        assert kept == [GLOBEX_CABIN]

    def test_two_documents_produce_two_cards_in_order(self):
        kept = _deduplicated_citations([GLOBEX_CAP, INITECH_CAP])
        assert kept == [GLOBEX_CAP, INITECH_CAP]

    def test_a_passage_with_no_doc_id_is_dropped(self):
        """No id means nothing to presign — a card here would be a button that 404s on click."""
        kept = _deduplicated_citations([NO_DOC_ID, GLOBEX_CAP])
        assert kept == [GLOBEX_CAP]

    def test_empty_input_produces_no_cards(self):
        assert _deduplicated_citations([]) == []

    def test_all_orphaned_produces_no_cards(self):
        assert _deduplicated_citations([NO_DOC_ID]) == []


class TestCardContract:
    """The one check every other card-emitting tool runs against a live backend
    (`assert_all_valid` in each family's `test_local.py`) — `knowledge` has no such smoke test,
    since it talks to Bedrock directly rather than the mock TMC, so this is the offline substitute:
    build the exact card `search_policy_knowledge` builds and check it against `shared/cards.py`.
    """

    def test_a_citation_built_from_a_passage_satisfies_the_card_contract(self):
        for passage in (GLOBEX_CAP, INITECH_CAP):
            built = card(
                CardType.CITATION,
                f"citation-{passage['citation']['doc_id']}",
                passage["citation"],
            )
            assert_valid(built)  # raises CardContractError on failure

    def test_a_citation_with_no_version_metadata_still_satisfies_the_contract(self):
        """`_citation()` sends `version: metadata.get('version')`, which is `None` for a document
        with no declared version — `REQUIRED_DATA` checks key presence, not truthiness, and this
        pins that a `None` value does not fail validation the way a missing key would."""
        built = card(
            CardType.CITATION,
            "citation-pol_globex_2026",
            {"label": "Globex policy", "doc_id": "pol_globex_2026", "version": None},
        )
        assert_valid(built)
