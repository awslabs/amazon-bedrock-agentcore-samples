"""Prompt rendering and versioning.

Templates rather than a Python string, for three reasons: composability makes cache-safety
structural instead of remembered, a prompt change shows up in a PR as a text diff, and reusable
partials keep shared instructions consistent without duplicating them.

**`prompt_version` is a content hash, not a hand-maintained number.** The eval gate has to
attribute a quality regression to a prompt change, and a manual version is one forgotten
edit away from lying — two different prompts recorded under one version make an A/B
comparison silently invalid. The hash is also the cache-prefix identity, so a changed
hash explains a cache-miss spike in the same field.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES_DIR = Path(__file__).parent
SYSTEM_TEMPLATE = "system.j2"

# 12 hex chars: enough to distinguish every prompt this project will ever have, short
# enough to read in a log line beside the tenant and session.
VERSION_LENGTH = 12


@lru_cache(maxsize=1)
def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        # **`autoescape=False` deliberately.** QuickWork sets it True, correct for an
        # HTML-adjacent product; for prompts it corrupts the content — apostrophes and
        # quotes in policy text would arrive at the model as `&#39;`.
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
        # Fail on an undefined variable rather than rendering an empty string. A prompt
        # silently missing a section is the kind of bug that shows up as a mysterious
        # eval regression months later.
        undefined=StrictUndefined,
    )


@lru_cache(maxsize=1)
def system_prompt() -> str:
    """The assembled system prompt.

    Cached because it is identical for every request — which is the point. It takes no arguments *by
    design*, and the reason is narrower than "no variables in prompts": **anything that varies before a
    cache breakpoint means no two requests share a cache entry**, so a tenant's policy values here
    would give every tenant a private prefix and destroy the economics the sample argues for.

    Per-session context is a different matter and belongs *after* the breakpoint — see
    `system_blocks()`.
    """
    return _environment().get_template(SYSTEM_TEMPLATE).render().strip()


def system_blocks(session_context: str | None = None) -> str | list[dict]:
    """The system prompt as Bedrock content blocks, with the cache point placed explicitly.

    **The shape that makes per-session context free.** A breakpoint caches everything *before* it, so:

        [ stable prompt ] [ cachePoint ] [ this session's context ]

    means the stable prefix is read from cache no matter what follows. Measured against the deployed
    model: three requests with three different session blocks — globex/priya, initech/sam,
    globex/adaeze — each read the **same 1042 cached tokens**, zero writes after the first. So a
    traveller's name and home airport cost only their own tokens, and cost nothing in cache terms.

    That corrects an over-broad rule this file used to imply. Variables are fine; variables *before the
    breakpoint* are not.

    Returns a plain string when there is no session context, so the common path and the ledger's
    `prompt_version` hash are unchanged — the version identifies the *stable* prefix, which is the
    thing a cache-miss spike or an eval regression needs attributing to.
    """
    if not session_context:
        return system_prompt()
    return [
        {"text": system_prompt()},
        # `default` is the 5-minute TTL. A conversation's turns arrive well inside that; a longer TTL
        # is a paid option and buys nothing for a prefix this size.
        {"cachePoint": {"type": "default"}},
        {"text": session_context},
    ]


@lru_cache(maxsize=1)
def prompt_version() -> str:
    """Short content hash of the rendered prompt, recorded on every trajectory.

    blake2b rather than sha256 for no cryptographic reason — it is faster and takes a
    digest size directly. This is an identity, not a security boundary.
    """
    digest = hashlib.blake2b(system_prompt().encode(), digest_size=VERSION_LENGTH // 2)
    return digest.hexdigest()


__all__ = ["prompt_version", "system_blocks", "system_prompt"]
