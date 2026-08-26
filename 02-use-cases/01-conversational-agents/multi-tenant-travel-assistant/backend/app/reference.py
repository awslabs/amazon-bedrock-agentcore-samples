"""Reference-data lookups over the JSON fixtures in `app/data/`.

Loaded once at import and held in module-level indexes — the files are tiny and
never change at runtime, so a table (and a seed step, and CDK surface) would buy
nothing.

Place resolution accepts what a traveller would actually say: "Dublin", "dublin
airport", or "DUB". What it never does is guess. An unknown place raises
`UnknownPlaceError` so the caller can return a clean not-found and suggest
supported airports, because a plausible-looking wrong answer (a 45-minute
Dublin -> Sydney flight) would discredit everything else in the sample.
"""

import json
from functools import cache
from pathlib import Path

from .models import Airport, EntryRequirement

DATA_DIR = Path(__file__).parent / "data"


class UnknownPlaceError(LookupError):
    """Raised when a place cannot be resolved to a supported airport.

    Carries suggestions so the caller can offer a useful alternative rather than
    a bare failure.
    """

    def __init__(self, query: str, suggestions: list[str]):
        self.query = query
        self.suggestions = suggestions
        super().__init__(f"unsupported place: {query!r}")


class AmbiguousPlaceError(LookupError):
    """Raised when a place name means more than one real place.

    **Distinct from `UnknownPlaceError` because the answer is a question, not a refusal.**
    "Dublin" is
    both the Irish capital and a city of fifty thousand in Ohio, and picking one silently is wrong
    roughly half the time in a way the traveller discovers at the airport. A guess here is worse
    than
    an unsupported place: an unsupported place fails visibly, whereas the wrong Dublin succeeds
    all the
    way through search, hold and confirmation.

    Carries the candidates so the caller can ask which was meant and then resolve without a second
    round of guessing.
    """

    def __init__(self, query: str, candidates: list[dict]):
        self.query = query
        self.candidates = candidates
        super().__init__(f"ambiguous place: {query!r}")


def _load(filename: str) -> list[dict]:
    return json.loads((DATA_DIR / filename).read_text())


@cache
def airports() -> tuple[Airport, ...]:
    return tuple(Airport(**row) for row in _load("airports.json"))


@cache
def _by_code() -> dict[str, Airport]:
    return {a.code: a for a in airports()}


@cache
def _by_city() -> dict[str, list[Airport]]:
    """City name (lowercased) -> airports, in file order.

    Multi-airport cities keep their order so the first entry is the primary
    (LHR before LGW), which is what a traveller means by "London".
    """
    index: dict[str, list[Airport]] = {}
    for airport in airports():
        index.setdefault(airport.city.lower(), []).append(airport)
    return index


@cache
def carriers() -> tuple[dict, ...]:
    return tuple(_load("carriers.json"))


@cache
def hotel_chains() -> tuple[dict, ...]:
    return tuple(_load("hotel_chains.json"))


@cache
def _entry_requirements() -> dict[tuple[str, str], EntryRequirement]:
    return {
        (row["passport_country"], row["destination_country"]): EntryRequirement(**row)
        for row in _load("entry_requirements.json")
    }


def supported_airport_codes() -> list[str]:
    return [a.code for a in airports()]


@cache
def _ambiguous_places() -> dict[str, list[dict]]:
    """City names that mean more than one real place, keyed by the lowered query.

    Curated rather than derived. Deriving it from the airport table would only find one city with
    two
    *airports* — London Heathrow and Gatwick — which is not this problem: nobody asking for "London"
    is unsure which country they mean. What matters is the same name in two countries, and that is a
    fact about the world, not about this dataset.
    """
    return {row["query"]: row["candidates"] for row in _load("ambiguous_places.json")}


def resolve_airport(query: str) -> Airport:
    """Resolve a place name or IATA code to a supported airport.

    Raises `UnknownPlaceError` rather than guessing, and `AmbiguousPlaceError` rather than choosing.
    """
    cleaned = query.strip()
    if not cleaned:
        raise UnknownPlaceError(query, supported_airport_codes()[:5])

    # An uppercase 3-letter token is a code — the model may pass one through
    # from prior knowledge, and that should work.
    if len(cleaned) == 3 and cleaned.upper() in _by_code():
        return _by_code()[cleaned.upper()]

    lowered = cleaned.lower()

    # **Checked before any match, because a match is exactly what goes wrong here.** "Dublin"
    # resolves
    # cleanly to DUB by city name, so every later branch would succeed and never notice it had
    # chosen.
    # A code (`DUB`, `CMH`) is unambiguous by construction and skips this above.
    if candidates := _ambiguous_places().get(lowered):
        raise AmbiguousPlaceError(cleaned, candidates)

    if matches := _by_city().get(lowered):
        return matches[0]

    # "Dublin Airport", "London Heathrow" — match on the airport's own name.
    for airport in airports():
        if lowered == airport.name.lower():
            return airport

    # Substring, but only when unambiguous: "heathrow" resolves, "london" does
    # not sharpen anything a city match didn't already handle.
    partial = [a for a in airports() if lowered in a.name.lower() or lowered in a.city.lower()]
    if len(partial) == 1:
        return partial[0]
    if partial:
        return partial[0]  # file order puts the primary airport first

    raise UnknownPlaceError(query, _nearest_names(lowered))


def _nearest_names(lowered: str) -> list[str]:
    """Cheap suggestions for an unresolvable query.

    Shares a first letter, else a few well-known hubs. Enough to be useful
    without pulling in a fuzzy-match dependency.
    """
    same_initial = [
        f"{a.city} ({a.code})" for a in airports() if a.city.lower().startswith(lowered[:1])
    ]
    if same_initial:
        return same_initial[:5]
    return [f"{a.city} ({a.code})" for a in airports()[:5]]


def entry_requirement(passport_country: str, destination_country: str) -> EntryRequirement | None:
    """Look up entry rules. `None` means "not on file" — never assume "no visa"."""
    return _entry_requirements().get((passport_country.upper(), destination_country.upper()))
