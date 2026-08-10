"""Scope of Work scoring.

Two-stage by design, following ADR 0014 in the reference sample ("deterministic
phase, no LLM"):

1. A deterministic heuristic pre-pass scans for the signals each criterion needs.
   It runs with no model, no network and no AWS account, and produces a floor
   score. This is what makes the feature testable and demonstrable offline.

2. When a model is available, a classifier refines each criterion into a 0-4
   band with a justification. The model only *classifies*; the weighted roll-up
   is arithmetic done here, so two runs over the same document cannot produce
   two different totals for the same set of bands.

If stage 2 is unavailable the result is returned with ``model_assisted=False``
and the UI labels it as heuristic-only rather than presenting it as a full score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from . import catalog


@dataclass
class CriterionScore:
    criterion_id: str
    name: str
    weight: int
    band: int
    band_label: str
    justification: str
    gap_fix: str = ""

    @property
    def weighted(self) -> float:
        return self.weight * (self.band / 4.0)

    @property
    def is_gap(self) -> bool:
        return self.band <= 2


@dataclass
class SOWScore:
    scores: list[CriterionScore] = field(default_factory=list)
    model_assisted: bool = False
    word_count: int = 0

    @property
    def total(self) -> float:
        earned = sum(score.weighted for score in self.scores)
        available = sum(score.weight for score in self.scores)
        if not available:
            return 0.0
        return round(earned / available * 100, 1)

    @property
    def gaps(self) -> list[CriterionScore]:
        return sorted(
            (s for s in self.scores if s.is_gap), key=lambda s: (s.band, -s.weight)
        )

    @property
    def rating(self) -> str:
        thresholds = catalog.sow_criteria()["thresholds"]
        total = self.total
        if total >= thresholds["strong"]:
            return "Strong"
        if total >= thresholds["acceptable"]:
            return "Acceptable"
        if total >= thresholds["weak"]:
            return "Weak"
        return "Inadequate"

    @property
    def summary(self) -> str:
        gaps = self.gaps
        if not gaps:
            return "No material gaps. Every criterion scored Adequate or better."
        worst = gaps[0]
        return (
            f"{len(gaps)} criteri{'on' if len(gaps) == 1 else 'a'} below Adequate. "
            f"The largest exposure is '{worst.name}', which carries "
            f"{worst.weight}% of the total weight and scored {worst.band_label}."
        )


_TOC_LINE_ENDING = re.compile(r"\t\s*\d{1,4}\s*$")


def _is_toc_occurrence(text_lower: str, idx: int) -> bool:
    """True if the character at ``idx`` sits on a Table-of-Contents line.

    Word's tab-stop TOC fields render as plain text as "<title>\\t<page
    number>" per line once extracted. A keyword's first occurrence is very
    often one of these lines (every section title appears in the ToC before
    it appears as a real heading) rather than the section itself — and a ToC
    line is *not* obviously sparse: title words plus a trailing page number
    can out-count a short, real bulleted section on a naive word count. So
    ToC-shaped lines are excluded from consideration outright rather than
    left to compete on word count.
    """
    line_start = text_lower.rfind("\n", 0, idx) + 1
    line_end = text_lower.find("\n", idx)
    if line_end == -1:
        line_end = len(text_lower)
    return bool(_TOC_LINE_ENDING.search(text_lower[line_start:line_end]))


def _best_window(text_lower: str, hits: list[str], signals: list[str], span: int = 600) -> str:
    """Find the richest window around any occurrence of a hit signal.

    A document's Table of Contents repeats section headings near the top of the
    file, so the *first* occurrence of a keyword is frequently a ToC line, not
    the real section — anchoring there systematically undercounts substance in
    any professionally-formatted document, which is nearly all of them. Instead,
    scan every occurrence of every hit, skip ones sitting on a ToC line, and
    keep the window with the most co-occurring signals, then the most words.
    """
    best_window = ""
    best_score = (-1, -1)
    fallback_window = ""
    for hit in hits:
        start = 0
        while True:
            idx = text_lower.find(hit, start)
            if idx == -1:
                break
            if not fallback_window:
                fallback_window = text_lower[idx : idx + span]
            if not _is_toc_occurrence(text_lower, idx):
                window = text_lower[idx : idx + span]
                score = (sum(1 for signal in signals if signal in window), len(window.split()))
                if score > best_score:
                    best_score, best_window = score, window
            start = idx + len(hit)
    # Every occurrence was ToC-shaped (unusual, but possible) — fall back to
    # the first occurrence rather than scoring on an empty window.
    return best_window or fallback_window


def _heuristic_band(text_lower: str, signals: list[str]) -> tuple[int, str]:
    """Score a criterion from keyword presence and surrounding substance.

    Deliberately conservative. Finding the phrase 'out of scope' proves the
    section exists, not that it is any good, so keyword presence alone never
    scores above Partial. Only density of distinct signals plus enough
    surrounding text lifts a criterion to Adequate.
    """
    hits = [signal for signal in signals if signal in text_lower]
    if not hits:
        return 0, "No matching language found in the document."

    # Measure substance near the richest occurrence, not just the first one.
    window = _best_window(text_lower, hits, signals)
    window_words = len(window.split())

    if len(hits) >= 3 and window_words > 60:
        return 3, f"Found {len(hits)} related signals with substantive surrounding text."
    if len(hits) >= 2 and window_words > 100:
        return 3, f"Found {len(hits)} related signals with a substantial section around them."
    if len(hits) >= 2:
        return 2, f"Found {len(hits)} related signals, but limited detail around them."
    if window_words > 120:
        return 2, "Referenced once, but within a substantial section."
    return 1, "Referenced once, with little supporting detail."


def score_heuristic(sow_text: str) -> SOWScore:
    """Deterministic pass. No model, no network."""
    spec = catalog.sow_criteria()
    bands = spec["bands"]
    heuristics = spec["heuristics"]
    text_lower = sow_text.lower()

    scores: list[CriterionScore] = []
    for criterion in spec["criteria"]:
        signals = heuristics.get(criterion["id"], [])
        band, justification = _heuristic_band(text_lower, signals)
        scores.append(
            CriterionScore(
                criterion_id=criterion["id"],
                name=criterion["name"],
                weight=criterion["weight"],
                band=band,
                band_label=bands[band]["label"],
                justification=justification,
                gap_fix=criterion["gap_fix"].strip(),
            )
        )

    return SOWScore(
        scores=scores,
        model_assisted=False,
        word_count=len(re.findall(r"\b\w+\b", sow_text)),
    )


def apply_model_bands(score: SOWScore, bands_by_id: dict[str, dict[str, Any]]) -> SOWScore:
    """Overlay model-assigned bands onto a heuristic score.

    ``bands_by_id`` maps criterion id to ``{"band": int, "justification": str}``,
    normally captured by the ``submit_sow_assessment`` structured-output tool.
    Unknown ids and out-of-range bands are ignored rather than trusted, and the
    arithmetic is redone here — the model never reports a total.
    """
    spec = catalog.sow_criteria()
    band_labels = spec["bands"]
    applied = False

    for criterion_score in score.scores:
        payload = bands_by_id.get(criterion_score.criterion_id)
        if not isinstance(payload, dict):
            continue
        band = payload.get("band")
        if not isinstance(band, int) or not 0 <= band <= 4:
            continue
        criterion_score.band = band
        criterion_score.band_label = band_labels[band]["label"]
        criterion_score.justification = (
            payload.get("justification") or criterion_score.justification
        )
        applied = True

    score.model_assisted = applied
    return score


def criteria_for_prompt() -> list[dict[str, str]]:
    """Compact criteria list to hand a classifier. Weights are withheld
    deliberately so the model cannot optimise the total it never computes."""
    spec = catalog.sow_criteria()
    return [
        {
            "id": criterion["id"],
            "name": criterion["name"],
            "question": criterion["prompt"].strip(),
        }
        for criterion in spec["criteria"]
    ]
