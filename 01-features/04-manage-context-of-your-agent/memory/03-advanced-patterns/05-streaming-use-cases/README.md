# Streaming use cases

Each of these composes the **memory record streaming primitive** with another AWS service or analytics pipeline. Read [`../../02-long-term-memory/01-core-features/09-record-streaming.py`](../../02-long-term-memory/01-core-features/09-record-streaming.py) first — it covers how to enable streaming, pick `METADATA_ONLY` vs `FULL_CONTENT`, and consume from Kinesis.

| Notebook | What it builds |
|---|---|
| [`01-cross-region-replication/`](./01-cross-region-replication/) | Replicates memory records from a source region to a destination region via Kinesis and Lambda |
| [`02-personalised-recommendations.py`](./02-personalised-recommendations.py) | Feeds streamed records into a recommendations pipeline |
| [`03-cross-customer-analytics.py`](./03-cross-customer-analytics.py) | Aggregates streamed records into an analytics store across tenants |

## Running the Python Scripts

Install dependencies (if a `requirements.txt` is present):

```bash
pip install -r requirements.txt
```

Run each script directly:

```bash
python 02-personalised-recommendations.py
python 03-cross-customer-analytics.py
```
