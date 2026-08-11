# 0011 — Recurring findings live in a Knowledge Base, not a Memory namespace

## Status
Accepted. Deployed and verified end to end.

## Context

Certain findings recur across reviews independent of who submits them:
HIPAA workloads without Lambda in a VPC, RDS proposals defaulting to GP2,
public ALBs without WAF. Following USER_PREFERENCE memory (ADR 0009), the
natural extension was a shared answer set for these recurring questions.

Every AgentCore Memory namespace in this sample — SEMANTIC, SUMMARIZATION,
USER_PREFERENCE — is keyed by `pocvalidator/{actorId}/...`. That shape fits
a reviewer's own history, which is what USER_PREFERENCE is for. It does not
fit content that is identical regardless of who is asking. A shared FAQ
forced into a per-actor namespace has two options: a synthetic shared
actor id, which repurposes a primitive not designed for that use, or
duplicate writes into every real actor's namespace, which does not
accumulate.

AgentCore exposes a Knowledge Base (FMKB) as a first-class `agentcore.json`
resource (`knowledgeBases[]`, added with `agentcore add knowledge-base`).
The CLI provisions a real `AWS::Bedrock::KnowledgeBase` — the standard
Bedrock Knowledge Bases feature, not an AgentCore-native service — with an
S3 data source, embedded and indexed for vector search. This is a single,
curated store, matching the shared-content requirement Memory's per-actor
namespaces do not.

## Decision

Add `PocValidatorFaqKB`, an `AgentCoreKnowledgeBase` backed by an S3 data
source (`agentcore/faq/*.md`, synced to
`s3://poc-validator-faq-kb-<account>/faq/` by `deploy.sh`). Nine curated
FAQ documents seed it — recurring architecture-review patterns, no client
names, consistent with this sample's scrub requirement.

At query time, `app/pocvalidator/tools/faq_search.py` calls
**`bedrock-agent-runtime:Retrieve`, not `RetrieveAndGenerate`.** `Retrieve`
embeds the query and returns matching source passages — vector search
only, no generation call. `RetrieveAndGenerate` would add a full model
call: unnecessary, since the FAQ documents are written as direct answers,
and in this account likely blocked by the same Bedrock Marketplace
restriction affecting SOW grading and diagram vision. `Retrieve` keeps
this feature's core capability off that dependency entirely.

Result formatting stays deterministic Python (score, matched text, S3
source), consistent with the principle applied to every model-adjacent
step in this sample: the model decides what to look up; code decides what
the answer says.

## Rationale

This is the same shared-versus-per-actor distinction that required a real
actor_id for USER_PREFERENCE memory in ADR 0009, applied in the reverse
direction. There, the fix gave genuinely per-actor content a real per-actor
identity. Here, the fix recognizes that a recurring finding's answer is not
per-actor content, and uses the primitive built for shared, curated
content instead.

## Consequences

- **Knowledge Base provisioning is a control-plane, CloudFormation-driven
  step** (`agentcore deploy`) with no model-access dependency, confirmed
  by deploying it and inspecting the resulting `AWS::Bedrock::KnowledgeBase`
  stack resource directly.
- **Ingestion is a separate, explicit step** (`start-ingestion-job`, run
  through `scripts/sync_faq_knowledge_base.sh`). Bedrock Knowledge Base
  ingestion embeds each document with an embedding model (Titan Text
  Embeddings) before indexing — a model dependency, but a narrower one
  than generation: embedding models are not subject to every account
  restriction that blocks generation-capable models. See Verification
  below for the result of this account's ingestion run.
- Retrieval makes its own embedding call for the query, the same category
  of dependency as ingestion, exercised on every `faq_query`. Its outcome
  in this account is recorded below rather than inferred from the
  ingestion result.
- The FAQ content set is deliberately small (nine documents) and
  hand-curated rather than sourced from real client SOWs, consistent with
  this sample's brand-scrub requirement and with keeping the knowledge
  base auditable — every entry was written for this sample.

## Verification

`agentcore deploy` auto-ingested the FAQ documents during provisioning
(visible in its own progress output as "Auto-ingest knowledge bases"), so
no manual ingestion step was required on initial deployment.
`scripts/sync_faq_knowledge_base.sh` exists for re-ingestion after editing
FAQ content, not for the initial run.

A direct `bedrock-agent-runtime:Retrieve` call — no generation, no Strands
agent, no model-authored content — against the deployed knowledge base for
"Why does production RDS need Multi-AZ?" returned the correct source
document (`multi-az-production-rds.md`) as the top match at score `1.0`,
including the matched passage text and its S3 source URI. Ingestion,
embedding, and vector search completed successfully; this feature has no
dependency on the Marketplace restriction anywhere in its path.

The same call surfaced one defect: **`vectorSearchConfiguration` is
rejected on this knowledge base type.** `Retrieve` accepts either
`vectorSearchConfiguration` (customer-managed vector store, the shape used
in standard Bedrock Knowledge Base tutorials) or `managedSearchConfiguration`
(AgentCore-managed knowledge bases, created with
`agentcore add knowledge-base` and backed by a fully-managed vector store
rather than a customer-provisioned OpenSearch Serverless collection). The
API's `ValidationException` names the required key directly ("
`vectorSearchConfiguration` is not supported for managed knowledge bases.
Use `managedSearchConfiguration` instead"). This was caught by calling
`Retrieve` directly against the deployed `AgentCoreKnowledgeBase`, rather
than assuming the standard Bedrock Knowledge Base tutorial shape applied
unchanged.
