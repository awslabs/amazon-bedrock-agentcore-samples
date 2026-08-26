"""Turn a trajectory's token counts into dollars.

**Separate from `ledger.py` on purpose.** The ledger records facts — tokens, latency, which
tool, which prompt version — because those cannot be reconstructed later. Cost is a
*conclusion*: it is the facts multiplied by a rate card that changes without warning and
differs by region. Keeping the two apart means a line recorded today can be repriced
tomorrow, and it is why every priced line carries `rate_version`: a number in a cost report
that cannot be traced to the rates that produced it is not auditable.

**The measured fact this arithmetic rests on.** For Anthropic models on Bedrock, cache
tokens are *additive* to `inputTokens`, not included in them. Measured rather than assumed,
with two `converse` calls sharing a cached system prefix:

    first : inputTokens=9  cacheWrite=1081 cacheRead=0    output=5 total=1095
    second: inputTokens=10 cacheWrite=0    cacheRead=1081 output=4 total=1095

so `totalTokens == inputTokens + cacheRead + cacheWrite + outputTokens` holds in both. This
matters because **the opposite convention exists on the same service**: AWS's own guidance
for OpenAI models on Bedrock states `input_tokens = cached_tokens + cache_write_tokens +
remainder`, where adding the cache counts on top would double-count them. Applying that
guidance here would undercount every cached turn instead. The identity is asserted in the
tests so a future SDK change cannot quietly flip it.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger(__name__)

# Bumped whenever the fallback table below changes, and recorded on every priced line. A cost
# figure whose rate card is unknown cannot be checked, and "the numbers moved" is
# indistinguishable from "the rates moved" without it.
RATE_VERSION = "2026-08-anthropic-list"

# USD per 1,000,000 tokens, which is the unit the vendors publish, so a reader can diff this
# against the price page without arithmetic. Anthropic list prices for Claude Sonnet 4.5:
# $3.00 input, $15.00 output, $0.30 cache read (0.1x input), $3.75 cache write at the 5-minute
# TTL (1.25x), $6.00 at the 1-hour TTL (2x).
#
# **Both write rates are here because the TTL is observable.** Bedrock returns
# `cacheDetails: [{ttl: "5m", ...}]` on a write, so the right rate can be selected from what
# the response reported rather than from what the config was believed to say.
FALLBACK_RATES: dict[str, dict[str, float]] = {
    "global.anthropic.claude-sonnet-4-5-20250929-v1:0": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.00,
    },
}

# Overrides the table above, so a rate change is a parameter edit rather than a deploy. Same
# reason the model id and guardrail version are read from SSM: a rate pasted into code drifts
# from the invoice silently.
RATES_PARAM = "/multi-tenant-travel/model/rates"
RATES_VAR = "MODEL_RATES_JSON"

_rates: dict[str, dict[str, float]] | None = None
_rate_version: str = RATE_VERSION


def _load() -> dict[str, dict[str, float]]:
    """The rate card, from SSM if published, else the table above.

    **Absent is not a warning; malformed is.** A fresh deploy has no rates parameter and the
    built-in table is correct, so shouting about it every container start would train the
    reader to ignore the log. A parameter that exists but cannot be parsed is different: it
    means someone tried to set rates and the bill is now being computed from something other
    than what they wrote.

    Cached per container. Rates change on the order of months and this is called once per
    trajectory, so an SSM round trip per turn would buy nothing.
    """
    global _rates, _rate_version
    if _rates is not None:
        return _rates

    raw = os.environ.get(RATES_VAR)
    source = RATES_VAR
    if not raw:
        try:
            import boto3

            ssm = boto3.client("ssm")
            raw = ssm.get_parameter(Name=RATES_PARAM)["Parameter"]["Value"]
            source = RATES_PARAM
        except Exception:  # noqa: BLE001 - absent is the normal case; see the docstring
            raw = None

    if raw:
        try:
            published = json.loads(raw)
            table = published.get("rates", published)
            if not isinstance(table, dict) or not table:
                raise ValueError("no rates in the published document")
            _rates = {str(k): {str(n): float(v) for n, v in r.items()} for k, r in table.items()}
            _rate_version = str(published.get("version", f"{source}-unversioned"))
            return _rates
        except Exception as error:  # noqa: BLE001 - a bad override must be loud, not silent
            log.warning(
                "rates at %s are unusable (%s) — falling back to the built-in %s table, so "
                "any rate change published there is NOT in effect",
                source,
                type(error).__name__,
                RATE_VERSION,
            )

    _rates = FALLBACK_RATES
    _rate_version = RATE_VERSION
    return _rates


def rate_version() -> str:
    _load()
    return _rate_version


def cache_write_rate(rates: dict[str, float], ttl: str | None) -> float:
    """The write rate for the TTL Bedrock reported, defaulting to the cheaper 5-minute one.

    Defaulting *down* is deliberate: an unknown TTL is far more likely to be the 5-minute
    default than the 1-hour opt-in, and a cost report that overstates spend gets dismissed as
    broken, which is a worse outcome than one that is slightly conservative and trusted.
    """
    if ttl and ttl.lower().startswith("1h"):
        return rates.get("cache_write_1h", rates.get("cache_write_5m", 0.0))
    return rates.get("cache_write_5m", 0.0)


def price(
    *,
    model_id: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    cache_ttl: str | None = None,
) -> dict[str, Any]:
    """Cost of one model call, or of a whole trajectory if given its totals.

    **An unrecognised model prices to `None`, never to zero.** Zero is the dangerous answer:
    a model upgrade would make spend appear to vanish, the cost graph would improve, and the
    gate would pass a change that had in fact stopped being measured. `None` propagates as a
    gap, and the gate treats a gap as a failure rather than as a cheap turn. Asserted in the
    tests, because this is the one branch whose wrongness would be invisible.
    """
    table = _load()
    rates = table.get(model_id)
    if not rates:
        log.warning(
            "no rate card for model %r in %s — this trajectory is unpriced. Publish rates at "
            "%s or add the model to FALLBACK_RATES; spend is being incurred either way.",
            model_id,
            _rate_version,
            RATES_PARAM,
        )
        return {
            "usd": None,
            "rate_version": _rate_version,
            "unpriced_reason": f"no rate card for {model_id}",
        }

    write_rate = cache_write_rate(rates, cache_ttl)
    components = {
        "input": input_tokens * rates.get("input", 0.0) / 1_000_000,
        "output": output_tokens * rates.get("output", 0.0) / 1_000_000,
        "cache_read": cache_read_tokens * rates.get("cache_read", 0.0) / 1_000_000,
        "cache_write": cache_write_tokens * write_rate / 1_000_000,
    }
    # Six decimals is a hundredth of a cent — finer than any decision made from this number,
    # and coarse enough that two runs of the same trajectory produce the same string. Rounded
    # once at the end rather than per component, so the parts sum to the whole.
    return {
        "usd": round(sum(components.values()), 6),
        "usd_detail": {k: round(v, 6) for k, v in components.items()},
        "rate_version": _rate_version,
    }
