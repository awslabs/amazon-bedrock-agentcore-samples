"""Unit tests for the routing-critical text parsers in app/claimsagent/parsing.py.

These cover the regex fallback path used when the agents don't call the
structured-output tools. Pure functions, no AWS/Strands dependencies.

Run:
    python3 -m unittest discover -s tests
    # or
    python3 tests/test_parsing.py
"""

import os
import sys
import unittest

# Make app/claimsagent importable without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "claimsagent"))

from parsing import parse_confidence, parse_decision  # noqa: E402


class ParseConfidenceTests(unittest.TestCase):
    def test_extracts_score(self):
        self.assertEqual(parse_confidence("CONFIDENCE: 85"), 85)

    def test_no_space(self):
        self.assertEqual(parse_confidence("CONFIDENCE:100"), 100)

    def test_zero(self):
        self.assertEqual(parse_confidence("CONFIDENCE: 0\nROUTING: HUMAN_REVIEW"), 0)

    def test_embedded_in_larger_block(self):
        text = "VALIDATION_NOTES: looks fine\nCONFIDENCE: 92\nROUTING: AUTO_APPROVE"
        self.assertEqual(parse_confidence(text), 92)

    def test_missing_defaults_to_50(self):
        # 50 is the safe default → routes to human review.
        self.assertEqual(parse_confidence("no score here"), 50)

    def test_empty_defaults_to_50(self):
        self.assertEqual(parse_confidence(""), 50)


class ParseDecisionTests(unittest.TestCase):
    def test_accept(self):
        self.assertEqual(parse_decision("DECISION: ACCEPT"), "ACCEPT")

    def test_reject(self):
        self.assertEqual(parse_decision("DECISION: REJECT"), "REJECT")

    def test_markdown_wrapped(self):
        self.assertEqual(parse_decision("**DECISION:** ACCEPT"), "ACCEPT")

    def test_lowercase(self):
        self.assertEqual(parse_decision("decision: reject"), "REJECT")

    def test_decision_separated_from_value(self):
        # First regex fails on intervening words; DOTALL fallback recovers it.
        self.assertEqual(parse_decision("DECISION\n\nFinal answer: ACCEPT"), "ACCEPT")

    def test_standalone_accept_without_keyword(self):
        self.assertEqual(parse_decision("I recommend we ACCEPT this claim."), "ACCEPT")

    def test_standalone_reject_without_keyword(self):
        self.assertEqual(parse_decision("We must REJECT this claim."), "REJECT")

    def test_missing_defaults_to_reject(self):
        # REJECT is the conservative default → never auto-approve on parse failure.
        self.assertEqual(parse_decision("no decision present"), "REJECT")

    def test_empty_defaults_to_reject(self):
        self.assertEqual(parse_decision(""), "REJECT")

    def test_reject_wins_when_both_present_near_top(self):
        # A standalone ACCEPT only wins if no REJECT is nearby; here REJECT is present.
        self.assertEqual(parse_decision("Could ACCEPT, but we REJECT due to fraud."), "REJECT")


if __name__ == "__main__":
    unittest.main()
