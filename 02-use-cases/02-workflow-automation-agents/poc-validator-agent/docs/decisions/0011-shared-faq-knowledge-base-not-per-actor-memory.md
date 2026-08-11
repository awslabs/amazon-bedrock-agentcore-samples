# 0011 — Recurring findings live in a Knowledge Base, not a Memory namespace

## Status
Accepted.

## Context

Across enough reviews, the same findings recur — HIPAA workloads keep
missing Lambda-in-VPC, RDS proposals keep defaulting to GP2, public ALBs
keep shipping without WAF. The natural next step after adding AgentCore
Memory's USER_PREFERENCE strategy (ADR 0009) was to ask whether the same
mechanism could hold a shared answer set for these recurring questions.

It can't, cleanly. Every AgentCore Memory namespace in this sample —
SEMANTIC, SUMMARIZATION, USER_PREFERENCE alike — is keyed by
`pocvalidator/{actorId}/...`. That's the right shape for "this reviewer's
own history," which is what USER_PREFERENCE is for. It's the wrong shape for
"the answer to this question is the same no matter who's asking." Forcing a
shared FAQ into a per-actor namespace means either: (a) writing it under one
synthetic shared actor id, which is a workaround bent around a primitive
that wasn't designed for it, or (b) writing the same content redundantly
into every real actor's namespace, which doesn't accumulate — it just
duplicates.

AgentCore also exposes a Knowledge Base (FMKB) as a first-class
`agentcore.json` resource (`knowledgeBases[]`, added via
`agentcore add knowledge-base`). Under the CLI, this provisions a real
`AWS::Bedrock::KnowledgeBase` — the standard Bedrock Knowledge Bases
feature (`bedrock-agent`/`bedrock-agent-runtime`), not a new AgentCore-native
service — with an S3 data source, embedded and indexed for vector search.
That's a single, deliberately-curated store: exactly the shape "everyone
should see the same answer" needs, and exactly the shape per-actor Memory
namespaces are not.

## Decision

Add `PocValidatorFaqKB`, an `AgentCoreKnowledgeBase` backed by an S3 data
source (`agentcore/faq/*.md` in this repo, synced to
`s3://poc-validator-faq-kb-<account>/faq/` by `deploy.sh`). Nine curated,
generic FAQ documents — recurring architecture-review patterns, no client
names, matching this sample's existing scrub discipline — seed it.

At query time, `app/pocvalidator/tools/faq_search.py` calls
**`bedrock-agent-runtime:Retrieve` directly, not `RetrieveAndGenerate`.**
`Retrieve` embeds the query and returns the matching source passages —
vector search only, no generation call. `RetrieveAndGenerate` would add a
full model call on top of that, which is both unnecessary (the FAQ docs are
already written as direct answers; a reviewer can read the matched passage
without a model rephrasing it) and, in this account, likely blocked by the
same Bedrock Marketplace restriction that blocks SOW grading and diagram
vision. Choosing `Retrieve` keeps this feature's core value — "find the
relevant, already-correct answer" — off that dependency entirely.

Formatting results into the response stays deterministic Python (score,
matched text, S3 source), the same principle applied to every other
model-adjacent step in this sample: a model decides *what* to look up, code
decides what the answer *says*.

## Rationale

This is the same "shared vs. per-actor" distinction that made USER_PREFERENCE
memory need a real actor_id in ADR 0009, applied in the opposite direction —
there, the fix was giving something genuinely per-actor a real per-actor
identity; here, the fix is recognizing that "the answer to this recurring
question" is not per-actor at all and reaching for the primitive built for
shared, curated content instead of bending one built for personal history
around it.

## Consequences

- **Knowledge Base *provisioning* is a control-plane, CloudFormation-driven
  step** (`agentcore deploy`) and does not itself depend on model access —
  confirmed by deploying it and inspecting the resulting
  `AWS::Bedrock::KnowledgeBase` stack resource directly.
- **Ingestion is a separate, explicit step** (`start-ingestion-job`, run via
  `scripts/sync_faq_knowledge_base.sh`), not folded into the CDK stack. Bedrock
  Knowledge Base ingestion embeds each document with an embedding model
  (Titan Text Embeddings) before indexing — a real model dependency, but a
  narrower one than generation: embedding models are not gated by every
  account restriction that blocks generation-capable models. See "Verified
  independent of the Marketplace gate" below for what this account's
  ingestion run actually showed.
- Retrieval (`Retrieve`) itself makes its own embedding call for the query,
  same category of dependency as ingestion, and is exercised on every real
  `faq_query` — its outcome in this account is recorded below rather than
  assumed from the ingestion result.
- The FAQ content set is intentionally small (nine documents) and hand-curated
  rather than harvested from real client SOWs — consistent with this
  sample's brand-scrub requirement (see the main README) and with keeping
  the knowledge base auditable: every entry in it was written for this
  sample, not lifted from a real engagement.

## Verified independent of the Marketplace gate

`agentcore deploy` auto-ingested the FAQ documents as part of provisioning
(a step visible in its own progress output — "Auto-ingest knowledge
bases" — not something this sample's scripts had to trigger separately;
`scripts/sync_faq_knowledge_base.sh` exists for re-ingesting after editing
the FAQ content later, not for the initial run). A direct
`bedrock-agent-runtime:Retrieve` call — no generation, no Strands agent, no
model-authored anything — against the real deployed knowledge base for
"Why does production RDS need Multi-AZ?" returned the correct source
document (`multi-az-production-rds.md`) as its top match at score `1.0`,
with the actual matched passage text and its S3 source URI. Ingestion,
embedding, and vector search all completed successfully in this account —
this feature has no dependency on the Marketplace restriction anywhere in
its path.

That same direct call caught one real bug: **`vectorSearchConfiguration` is
rejected on this kind of knowledge base.** `Retrieve`'s API accepts either
`vectorSearchConfiguration` (customer-managed vector store — the shape
tutorials for plain Bedrock Knowledge Bases show) or
`managedSearchConfiguration` (AgentCore-managed knowledge bases — created
via `agentcore add knowledge-base`, backed by a fully-managed vector store
rather than a customer-provisioned OpenSearch Serverless collection). Using
the wrong one fails with a `ValidationException` that names the correct key
directly (*"vectorSearchConfiguration is not supported for managed
knowledge bases. Use managedSearchConfiguration instead"*) — caught by
calling `Retrieve` directly against the real, deployed
`AgentCoreKnowledgeBase` rather than assuming the standard Bedrock KB
tutorial shape would carry over unchanged.
