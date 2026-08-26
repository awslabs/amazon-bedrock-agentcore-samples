"""Structured values extracted from Strands tool-result content blocks."""

import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[1] / "MultiTenantTravel" / "app" / "MultiTenantTravel"
sys.path.insert(0, str(AGENT_DIR))

import stream  # noqa: E402


def test_payloads_in_returns_the_tool_envelope():
    result = {
        "content": [
            {
                "text": (
                    '{"cards":[{"card_type":"booking_confirmed"}],'
                    '"facts":{"booked":true},"provenance":{"source":"booking_confirm"}}'
                )
            }
        ]
    }
    assert stream.payloads_in(result) == [
        {
            "cards": [{"card_type": "booking_confirmed"}],
            "facts": {"booked": True},
            "provenance": {"source": "booking_confirm"},
        }
    ]


def test_payloads_in_ignores_unparseable_content():
    result = {"content": [{"text": "not json"}, {"json": {"facts": {"booked": True}}}, None]}
    assert stream.payloads_in(result) == []


def test_cards_in_reuses_the_same_envelope_parser():
    result = {
        "content": [
            {"text": '{"facts":{"booked":true}}'},
            {
                "text": (
                    '{"cards":[{"card_type":"booking_confirmed"},null,"bad"],'
                    '"facts":{"booked":true}}'
                )
            },
        ]
    }
    assert stream.cards_in(result) == [{"card_type": "booking_confirmed"}]
