# 0004 — Code-enforced domain allowlist for recommendations

## Status
Accepted.

## Context
The requirement is that further reading comes from AWS and Amazon sources only —
documentation, AWS blogs, and re:Invent sessions on AWS-owned YouTube channels.

## Decision
`core/resources.py` validates every URL against an explicit host allowlist at load time.
Entries that fail are dropped into `rejected()`. A test asserts `rejected()` is empty for
the shipped catalogue. YouTube is permitted only for AWS-owned channel path prefixes.
HTTPS is required.

## Rationale
The obvious alternative is a system-prompt instruction. A prompt instruction is a
request, not a constraint: a model asked to cite only AWS sources will eventually cite a
Medium post, and the failure is silent. Enforcing in code turns a drift into a CI failure.

The lookalike case matters too — `aws.amazon.com.evil.example` contains the string
`aws.amazon.com`, so substring matching would pass it. The check compares the parsed host
exactly, and there is a test for that specific URL.

## Consequences
Adding a recommendation from a non-AWS source is impossible without deliberately editing
the allowlist, which is a reviewable change.
