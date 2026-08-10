"""Curated further reading, restricted to AWS and Amazon sources.

The restriction is enforced in code, at load time, against a domain allowlist.
It is not a prompt instruction, because a prompt instruction is a request and
this is a requirement: a model asked to "only cite AWS sources" will eventually
cite a Medium post, and nobody will notice until it is in front of a customer.

Anything not on the allowlist is dropped and recorded in ``rejected()``. The
test suite asserts that rejection list is empty for the shipped catalogue, so a
bad URL fails CI rather than reaching a partner.

YouTube is permitted only for AWS-owned channels, since re:Invent session
recordings live there and nowhere else.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from urllib.parse import urlparse

from . import catalog

ALLOWED_HOSTS = {
    "aws.amazon.com",
    "docs.aws.amazon.com",
    "amazon.com",
    "www.amazon.com",
    "calculator.aws",
    "builder.aws.com",
    "repost.aws",
}

# YouTube is allowed only for these AWS-owned channel paths.
ALLOWED_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com"}
ALLOWED_YOUTUBE_PREFIXES = (
    "/@AWSEventsChannel",
    "/@amazonwebservices",
    "/user/AmazonWebServices",
    "/c/AmazonWebServices",
)

KIND_LABEL = {
    "documentation": "AWS documentation",
    "blog": "AWS blog",
    "video": "re:Invent / AWS video",
}


@dataclass(frozen=True)
class Resource:
    id: str
    title: str
    kind: str
    url: str
    summary: str
    tags: frozenset[str]

    @property
    def kind_label(self) -> str:
        return KIND_LABEL.get(self.kind, self.kind)


def is_allowed(url: str) -> bool:
    """True only for AWS/Amazon domains, or AWS-owned YouTube channels."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.netloc or "").lower()
    if host in ALLOWED_HOSTS:
        return True
    if host in ALLOWED_YOUTUBE_HOSTS:
        return any(parsed.path.startswith(prefix) for prefix in ALLOWED_YOUTUBE_PREFIXES)
    return False


@functools.lru_cache(maxsize=1)
def _partition() -> tuple[tuple[Resource, ...], tuple[dict, ...]]:
    allowed: list[Resource] = []
    rejected: list[dict] = []
    for entry in catalog.resources_raw()["resources"]:
        if not is_allowed(entry["url"]):
            rejected.append({"id": entry.get("id", "?"), "url": entry.get("url", "")})
            continue
        allowed.append(
            Resource(
                id=entry["id"],
                title=entry["title"],
                kind=entry["kind"],
                url=entry["url"],
                summary=entry["summary"].strip(),
                tags=frozenset(entry.get("tags", [])),
            )
        )
    return tuple(allowed), tuple(rejected)


def all_resources() -> tuple[Resource, ...]:
    return _partition()[0]


def rejected() -> tuple[dict, ...]:
    """Catalogue entries dropped for failing the allowlist. Should be empty."""
    return _partition()[1]


def recommend(report, sow_score=None, limit: int = 8) -> list[tuple[Resource, str]]:
    """Rank the catalogue against what this specific review found.

    Returns (resource, reason) pairs. The reason states which finding or input
    caused the recommendation, so nothing appears without an explanation — the
    same rule the findings themselves follow.
    """
    graph = report.graph
    wanted: dict[str, list[str]] = {}

    def want(tag: str, reason: str) -> None:
        wanted.setdefault(tag, []).append(reason)

    want(graph.industry_id, f"you selected the {graph.industry_id.upper()} industry lens")
    want(graph.segment_id, f"you selected the {graph.segment_id.replace('_', ' ')} segment")
    want("general", "general architecture practice")

    for finding in report.findings:
        want(finding.pillar.lower().replace(" ", "-"), f"finding {finding.rule_id}")
        for tag in _tags_from_finding(finding):
            want(tag, f"finding {finding.rule_id} ({finding.title[:48]})")

    for node in graph.nodes.values():
        want(node.category, f"your design includes {node.name}")

    if report.cost and report.cost.premium > report.cost.baseline * 0.3:
        want("cost", "the compliance premium exceeds 30% of the baseline cost")

    if sow_score is not None:
        want("sow", "you submitted a Scope of Work for scoring")
        want("partner", "SOW and engagement practice")

    # Broad tags explain nothing useful, so they rank last when choosing which
    # reason to show the user even though they still contribute to relevance.
    broad = {"general", "architecture", "security", "reliability", "cost",
             "operational-excellence", "performance-efficiency", "industry"}

    scored: list[tuple[int, Resource, str]] = []
    for resource in all_resources():
        overlap = resource.tags & wanted.keys()
        if not overlap:
            continue
        weight = sum(len(wanted[tag]) for tag in overlap)
        specific = overlap - broad
        pool = specific or overlap
        best_tag = max(pool, key=lambda tag: (len(wanted[tag]), tag))
        scored.append((weight, resource, wanted[best_tag][0]))

    scored.sort(key=lambda item: (-item[0], item[1].title))

    # Spread across kinds so the list is not eight documentation pages.
    picked: list[tuple[Resource, str]] = []
    per_kind: dict[str, int] = {}
    cap = max(2, limit // 2)
    for _, resource, reason in scored:
        if per_kind.get(resource.kind, 0) >= cap:
            continue
        picked.append((resource, reason))
        per_kind[resource.kind] = per_kind.get(resource.kind, 0) + 1
        if len(picked) >= limit:
            break
    return picked


def _tags_from_finding(finding) -> set[str]:
    """Map a finding back onto catalogue tags via its rule attribute."""
    tags: set[str] = set()
    title = finding.title.lower()
    for attribute, meta in catalog.attribute_defs().items():
        if meta["label"].lower() in title:
            tags.add(attribute)
    if finding.source.startswith("chaining"):
        tags.update({"chaining", "integration"})
    if "glue" in title:
        tags.add("glue")
    return tags
