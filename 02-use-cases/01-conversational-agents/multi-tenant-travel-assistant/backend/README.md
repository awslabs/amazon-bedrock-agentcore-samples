# Mock TMC Backend

**This is the folder you delete.**

It stands in for the travel platform a corporate travel management company (TMC)
already runs — trips, bookings, traveler profiles, policy — the system that
would exist long before anyone added an AI assistant. Replacing it with your
real API is the point: nothing in `agent/`, `tools/`, or `frontend/` imports
from here. Tool Lambdas call it over HTTP, exactly as they would call yours.

## What's inside

| Path | Purpose |
|---|---|
| `app/models/` | Pydantic models — the backend's API contract, **PII included on purpose** (see below) |
| `app/data/` | Small JSON fixtures: ~40 airports, entry requirements, hotel chains |
| `app/routers/` | trips · booking · profile · policy · hotels |
| `generator/` | Deterministic flight/hotel option generation |
| `seed/` | Two tenants, three travelers, trips, policies |

## Two design choices worth understanding

**PII exists here deliberately.** `TravelerProfile` holds passport numbers,
loyalty numbers, and card last-four. A real profile store does, and the tool
layer needs something real to curate: `get_traveler_profile` returns passport
*country* and a masked payment label, never the raw fields. PII that never
leaves this Lambda cannot leak into model context, a card, or a log.

**Policy is not a rigid schema.** Corporate policy is heterogeneous — caps by
city tier, cabin by duration or seniority, approval thresholds, exception prose.
So `TravelPolicy` types only what code computes on (`PolicyCore`) and keeps
everything else as loose `rules` the model narrates. The knowledge base carries
the third tier: exceptions and the "spirit of the policy" no schema captures.

## Determinism

The generator has two modes. **`FIXTURE`** seeds on
`hash(route + dates + tenant)`, so the same query always returns identical
options — that is what makes exact-match eval assertions and cost baselines
meaningful. **`LIVE`** adds a time bucket so results drift plausibly for demos.

Options are computed per request and never stored. A *held offer* is real state:
pricing an option freezes a fare with an expiry, mirroring how GDS pricing
returns a short-lived handle. Only the handle reaches the client; the server
re-prices and re-checks ownership before booking.

## Limits are surfaced, not hidden

~40 airports cover the demo and eval routes. An unknown airport returns
not-found and the agent suggests supported ones — it never invents coordinates,
because a 45-minute Dublin → Sydney flight would discredit everything else here.

## Running

```bash
uv sync
uv run pytest
uv run ruff check .
```

Tenant arrives as an `X-Tenant-Id` header. In the deployed sample the tool
Lambda derives it from a verified token — never from the model. That is what
your real API's auth already does.
