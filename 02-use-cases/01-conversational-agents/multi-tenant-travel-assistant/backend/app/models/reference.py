"""Reference fixtures — airports and entry requirements.

Both ship as JSON in the repo rather than living in a table. `airports.json` is
~40 rows covering the demo and eval routes only: **not a world dataset.** It
exists for one reason — the option generator needs coordinates so a Dublin →
Atlanta flight comes out around eight hours instead of forty-five minutes.

There are deliberately no `City` or `Country` models: city and country are
fields on the airport row, and any lookup is an index over the same file.

The 40-airport limit is surfaced in the UI and by an honest not-found from
search, never widened by inventing coordinates. A plausible-looking but wrong
duration would discredit everything else the sample claims.
"""

from enum import StrEnum
from math import asin, cos, radians, sin, sqrt

from pydantic import BaseModel

from .common import CountryCode, IataCode

# Mean earth radius. Great-circle distance is a good enough proxy for scheduled
# flight time once a taxi/climb allowance is added.
EARTH_RADIUS_KM = 6371.0


class Airport(BaseModel):
    code: IataCode
    name: str
    city: str
    country: CountryCode
    latitude: float
    longitude: float

    def distance_km(self, other: "Airport") -> float:
        lat1, lon1, lat2, lon2 = map(
            radians, (self.latitude, self.longitude, other.latitude, other.longitude)
        )
        h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
        return 2 * EARTH_RADIUS_KM * asin(sqrt(h))


class EntryRequirementKind(StrEnum):
    NONE = "none"
    EVISA = "evisa"
    VISA = "visa"


class EntryRequirement(BaseModel):
    """What a passport holder needs to enter a destination.

    Fictional data. A production system reads this from a licensed provider
    (IATA Timatic, Sherpa) behind the same contract — the tool shape does not
    change. `disclaimer` is always present because entry advice is
    legal-adjacent and must never read as authoritative.
    """

    passport_country: CountryCode
    destination_country: CountryCode
    requirement: EntryRequirementKind
    note: str | None = None
    disclaimer: str = "Fictional demo data. Always verify with official sources before travel."
