"""Loads every YAML pack: services, integrations, pricing, rules, SOW criteria, resources.

Data lives outside the package so a contributor can add a service, an industry or
a reading recommendation without touching Python. Paths resolve relative to the
sample root, which keeps the core importable from the agent, the UI and the tests
without any of them agreeing on a working directory.
"""

from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any

import yaml

# app/pocvalidator/core/catalog.py -> sample root is four levels up when run
# from a checkout, but the Runtime container flattens app/pocvalidator/ to /app/
# (one level shallower) and always sets POC_VALIDATOR_ROOT — so the fallback
# must be lazy. os.getenv's default argument is evaluated eagerly regardless of
# whether the env var is set, and `parents[3]` doesn't exist from /app/core/
# in the container, which crashes the Runtime on boot even though the env var
# it should have used is set correctly.
_root_env = os.getenv("POC_VALIDATOR_ROOT")
ROOT = Path(_root_env) if _root_env else Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
RULES = ROOT / "rules"


def _read(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@functools.lru_cache(maxsize=1)
def services() -> dict[str, Any]:
    return _read(DATA / "services.yaml")


@functools.lru_cache(maxsize=1)
def service_defs() -> dict[str, dict[str, Any]]:
    return services()["services"]


@functools.lru_cache(maxsize=1)
def attribute_defs() -> dict[str, dict[str, Any]]:
    return services()["attributes"]


@functools.lru_cache(maxsize=1)
def integrations() -> dict[tuple[str, str], dict[str, Any]]:
    raw = _read(DATA / "integrations.yaml")["integrations"]
    return {(item["from"], item["to"]): item for item in raw}


@functools.lru_cache(maxsize=1)
def pricing() -> dict[str, Any]:
    return _read(DATA / "pricing.yaml")


@functools.lru_cache(maxsize=1)
def examples() -> list[dict[str, Any]]:
    return _read(DATA / "examples.yaml")["examples"]


@functools.lru_cache(maxsize=1)
def resources_raw() -> dict[str, Any]:
    return _read(DATA / "resources.yaml")


@functools.lru_cache(maxsize=1)
def sow_criteria() -> dict[str, Any]:
    return _read(RULES / "sow_criteria.yaml")


def _load_packs(directory: Path) -> dict[str, dict[str, Any]]:
    packs: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.yaml")):
        pack = _read(path)
        packs[pack["id"]] = pack
    return packs


@functools.lru_cache(maxsize=1)
def segments() -> dict[str, dict[str, Any]]:
    return _load_packs(RULES / "segments")


@functools.lru_cache(maxsize=1)
def industries() -> dict[str, dict[str, Any]]:
    return _load_packs(RULES / "industries")


def service_choices() -> list[tuple[str, str]]:
    defs = service_defs()
    ordered = sorted(defs.items(), key=lambda kv: (kv[1]["category"], kv[1]["name"]))
    return [(sid, d["name"]) for sid, d in ordered]


def default_config(service_id: str) -> dict[str, Any]:
    attrs = service_defs()[service_id].get("attributes", [])
    return {name: attribute_defs()[name]["default"] for name in attrs}


def default_usage(service_id: str) -> dict[str, float]:
    drivers = service_defs()[service_id].get("cost_drivers", [])
    return {d["id"]: float(d["default"]) for d in drivers}


def resolve_service(name: str) -> str | None:
    """Best-effort map of a free-text service name onto a catalogue id.

    Used when a vision model reports what it saw on a diagram. Returns None for
    anything it cannot match confidently — an unmatched box is surfaced to the
    user for correction rather than silently dropped or silently guessed.
    """
    needle = name.strip().lower().replace("-", " ").replace("_", " ")
    if not needle:
        return None
    defs = service_defs()
    if needle in defs:
        return needle
    for service_id, definition in defs.items():
        candidates = {
            service_id.replace("_", " "),
            definition["name"].lower(),
            definition["name"].lower().replace("amazon ", "").replace("aws ", ""),
        }
        if needle in candidates:
            return service_id
    for service_id, definition in defs.items():
        short = definition["name"].lower().replace("amazon ", "").replace("aws ", "")
        if short and (short in needle or needle in short):
            return service_id

    # Token overlap. Diagram labels rarely match catalogue names exactly —
    # "RDS PostgreSQL" against "Amazon RDS for PostgreSQL" — so compare
    # meaningful tokens and require the label's tokens to be covered.
    filler = {"amazon", "aws", "for", "service", "services", "the", "on"}
    needle_tokens = {t for t in needle.split() if t not in filler}
    if not needle_tokens:
        return None

    best_id, best_overlap = None, 0
    for service_id, definition in defs.items():
        candidate = f"{service_id.replace('_', ' ')} {definition['name'].lower()}"
        tokens = {t for t in candidate.split() if t not in filler}
        overlap = len(needle_tokens & tokens)
        if overlap > best_overlap:
            best_id, best_overlap = service_id, overlap

    # Require the label to be mostly accounted for, so a single shared word
    # like "amazon" or "gateway" cannot produce a confident wrong match.
    if best_id and best_overlap >= max(1, len(needle_tokens) - 1):
        return best_id
    return None
