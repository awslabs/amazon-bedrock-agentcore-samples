# Streaming use cases

Each of these composes the **memory record streaming primitive** with another AWS service or analytics pipeline. Read [`../../02-long-term-memory/01-core-features/09-record-streaming.ipynb`](../../02-long-term-memory/01-core-features/09-record-streaming.ipynb) first — it covers how to enable streaming, pick `METADATA_ONLY` vs `FULL_CONTENT`, and consume from Kinesis.

| Notebook | What it builds |
|---|---|
| [`01-cross-region-replication/`](./01-cross-region-replication/) | Replicates memory records from a source region to a destination region via Kinesis and Lambda |
| [`02-personalised-recommendations.ipynb`](./02-personalised-recommendations.ipynb) | Feeds streamed records into a recommendations pipeline |
| [`03-cross-customer-analytics.ipynb`](./03-cross-customer-analytics.ipynb) | Aggregates streamed records into an analytics store across tenants |
