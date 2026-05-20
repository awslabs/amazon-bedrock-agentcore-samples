# Long-term memory — core features

Framework-agnostic tutorials for the long-term memory primitives. Start here before jumping into the framework integrations under [`../02-single-agent/`](../02-single-agent/) and [`../03-multi-agent/`](../03-multi-agent/).

Default surface: **boto3** (the raw API is clearest for primitive walkthroughs).

| # | Notebook | Covers |
|---|---|---|
| 01 | [`01-built-in-strategies/semantic.py`](./01-built-in-strategies/semantic.py) | Semantic memory strategy — facts via vector search |
| 01 | [`01-built-in-strategies/summary.py`](./01-built-in-strategies/summary.py) | Summary memory strategy — rolling conversation summaries |
| 01 | [`01-built-in-strategies/user-preference.py`](./01-built-in-strategies/user-preference.py) | User preference strategy |
| 01 | [`01-built-in-strategies/episodic.py`](./01-built-in-strategies/episodic.py) | Episodic memory strategy |
| 02 | `02-strategies-with-overrides.py` | Prompt overrides on built-in strategies |
| 03 | `03-self-managed-strategy.py` | Custom extraction + consolidation Lambdas |
| 04 | `04-namespaces-and-organization.py` | `{actorId}` / `{sessionId}` / `{strategyId}` namespace templates |
| 05 | `05-retrieve-records-and-citations.py` | `RetrieveMemoryRecords`, citation payloads |
| 06 | `06-structured-metadata.py` | Record-level structured metadata for filtering |
| 07 | `07-batch-create-update-delete.py` | Batch data-plane APIs |
| 08 | `08-redrive-failed-ingestions.py` | `Redrive` for failed extractions |
| 09 | [`09-record-streaming.py`](./09-record-streaming.py) | Kinesis streaming (`METADATA_ONLY` / `FULL_CONTENT`) |

> **Status:** Notebooks 01–08 are placeholders documenting scope. Notebook 09 is existing content moved from `03-advanced-patterns/05-memory-streaming/`; streaming *use cases* built on top live in [`../../03-advanced-patterns/05-streaming-use-cases/`](../../03-advanced-patterns/05-streaming-use-cases/).

## Running the Python Scripts

Install dependencies (if a `requirements.txt` is present):

```bash
pip install -r requirements.txt
```

Run each script directly:

```bash
python 09-record-streaming.py
```
