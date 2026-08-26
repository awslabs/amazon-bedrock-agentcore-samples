"""Pagination outcomes for the CloudTrail audit verifier."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_audit import (
    DATA_ROLE_NAME,
    SearchStatus,
    assume_role_event,
)


class FakeCloudTrail:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def lookup_events(self, **kwargs):
        self.calls.append(kwargs)
        return self.pages[len(self.calls) - 1]


def cloudtrail_event(session: str) -> dict:
    return {
        "CloudTrailEvent": json.dumps(
            {
                "eventName": "AssumeRole",
                "requestParameters": {
                    "roleArn": f"arn:aws:iam::123456789012:role/{DATA_ROLE_NAME}",
                    "tags": [{"key": "session_id", "value": session}],
                },
            }
        )
    }


def test_found_reports_the_matching_page_and_event():
    session = "audit-session"
    client = FakeCloudTrail(
        [
            {"Events": [], "NextToken": "page-2"},
            {"Events": [cloudtrail_event(session)]},
        ]
    )

    result = assume_role_event(session, max_pages=5, cloudtrail=client)

    assert result.status is SearchStatus.FOUND
    assert result.pages == 2
    assert result.event["requestParameters"]["tags"][0]["value"] == session
    assert client.calls[1]["NextToken"] == "page-2"


def test_not_found_means_cloudtrail_had_no_more_pages():
    client = FakeCloudTrail([{"Events": []}])

    result = assume_role_event("missing-session", max_pages=5, cloudtrail=client)

    assert result.status is SearchStatus.NOT_FOUND
    assert result.pages == 1
    assert result.event is None


def test_exhausted_means_the_bound_was_hit_while_pages_remained():
    client = FakeCloudTrail(
        [
            {"Events": [], "NextToken": "page-2"},
            {"Events": [], "NextToken": "page-3"},
        ]
    )

    result = assume_role_event("deep-session", max_pages=2, cloudtrail=client)

    assert result.status is SearchStatus.EXHAUSTED
    assert result.pages == 2
    assert result.event is None


def test_max_pages_must_allow_at_least_one_request():
    with pytest.raises(ValueError, match="at least 1"):
        assume_role_event("session", max_pages=0, cloudtrail=FakeCloudTrail([]))
