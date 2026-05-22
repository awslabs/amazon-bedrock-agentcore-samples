# Record metadata

Memory records can carry structured metadata (key → value) so retrieval can apply hard filters at the index instead of in the prompt. Typical uses: region, tier, source system, language, retention class.

## What you learn

- Attach metadata when writing via `BatchCreateMemoryRecords` (each record's `metadata` field is a `string → MetadataValue` map)
- Declare `indexedKeys` on `CreateMemory` so the keys you intend to filter on are pre-indexed
- Filter retrieval via `searchCriteria.metadataFilters` (`EQUALS_TO`, `EXISTS`, `NOT_EXISTS`)

## Run

```bash
pip install boto3 bedrock-agentcore
python structured-metadata.py boto3   # default — direct service calls
python structured-metadata.py sdk     # documents the SDK gap (no indexedKeys / batch / metadataFilters helpers)
python structured-metadata.py cli     # print equivalent AWS CLI commands
```

## Best practices

- **Pre-declare `indexedKeys`** on the memory resource at creation. Once declared they cannot be removed, and they are required for index-side filtering.
- **Keep keys low-cardinality and stable** (`region`, `tier`, `source`). Don't put free-form values here.
- **Don't store secrets in metadata.** Same reasoning as event metadata — it isn't encrypted with your CMK.
- **Prefer metadata over namespace explosion.** If a record can be split *or* filtered by an attribute, prefer filtering — a smaller namespace tree is easier to scope with IAM and easier to evolve.
- **Combine with namespace.** Namespace = ownership/scope; metadata = orthogonal attributes. They compose well.
