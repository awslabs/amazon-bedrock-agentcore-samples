"""Shared domain primitives.

Everything here is used across more than one router. Types that belong to a
single domain live in that domain's module instead.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Tenant-prefixed key parts. The prefix is not cosmetic: DynamoDB partition keys
# are `TENANT#<id>`, and `dynamodb:LeadingKeys` constrains that exact value at
# the IAM layer. Isolation depends on the prefix existing in the key itself.
TENANT_KEY_PREFIX = "TENANT#"


def tenant_pk(tenant_id: str) -> str:
    """Partition key for any tenant-scoped item."""
    return f"{TENANT_KEY_PREFIX}{tenant_id}"


class Currency(StrEnum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


class Money(BaseModel):
    """An amount always travels with its currency.

    Tenants differ (Globex bills USD, Initech EUR), so no layer downstream may
    assume a symbol — cards render currency from this field.
    """

    model_config = ConfigDict(frozen=True)

    amount: Decimal = Field(ge=0, decimal_places=2)
    currency: Currency

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce(cls, v: object) -> Decimal:
        # Floats lose cents, so go via str. Quantised to 2dp so serialisation is
        # consistent: "250.00" beside "178.50", never a bare "250" that a UI
        # would render as "$250" next to "$178.50".
        return Decimal(str(v)).quantize(Decimal("0.01"))

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"


class CabinClass(StrEnum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class TravelKind(StrEnum):
    AIR = "air"
    HOTEL = "hotel"


class PolicyStatus(StrEnum):
    """Whether an option sits inside the tenant's policy.

    The **backend** decides this, the way a real OBT annotates search results.
    The agent layer passes the verdict through; it never recomputes it.
    """

    IN_POLICY = "in_policy"
    OUT_OF_POLICY = "out_of_policy"
    REQUIRES_APPROVAL = "requires_approval"


class GenerationMode(StrEnum):
    """Determinism is a property of the environment, not a claim about reality.

    FIXTURE — same query yields identical options, so exact-match assertions and
              cost baselines mean something in CI.
    LIVE    — the seed includes a time bucket, so results drift plausibly
              between sessions for demos.
    """

    FIXTURE = "fixture"
    LIVE = "live"


# Tenants are organisations, so their ids stay human-readable: they appear in
# every partition key (`TENANT#globex`), in `dynamodb:LeadingKeys` conditions, in
# Cedar policies, in S3 prefixes and in CloudTrail — all read by people auditing
# something. A company name is not personal data, and tenant onboarding is
# admin-controlled, so the uniqueness pressure that forces opaque ids on people
# does not apply. **Immutable once issued**: a rename would mean rewriting every
# partition key.
TenantId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{1,31}$")]

# Travellers are people, so their ids are opaque and stable. A readable id like
# `priya` would be derived from a name (which changes), collide with the next
# Priya, and leak personal data into logs, URLs, provenance and audit trails.
# The display name is a separate, freely-changing attribute; references are by id.
#
# The model never supplies one of these: it passes a *name* as intent, and the
# tool resolves it within the caller's authorised scope — surfacing ambiguity as
# a question rather than guessing which Priya was meant.
TravelerId = Annotated[str, Field(pattern=r"^trv_[0-9a-f]{12}$")]

IataCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
CountryCode = Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
