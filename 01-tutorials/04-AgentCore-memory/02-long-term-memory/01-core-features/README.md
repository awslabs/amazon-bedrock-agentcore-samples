# Long-term memory — core features

Framework-agnostic tutorials for the long-term memory primitives. Start here before jumping into the framework integrations under [`../02-single-agent/`](../02-single-agent/) and [`../03-multi-agent/`](../03-multi-agent/).

Default surface: **boto3** (the raw API is clearest for primitive walkthroughs).

| # | Notebook | Covers |
|---|---|---|
| 01 | [`01-built-in-strategies/semantic.ipynb`](./01-built-in-strategies/semantic.ipynb) | Semantic memory strategy — facts via vector search |
| 01 | [`01-built-in-strategies/summary.ipynb`](./01-built-in-strategies/summary.ipynb) | Summary memory strategy — rolling conversation summaries |
| 01 | [`01-built-in-strategies/user-preference.ipynb`](./01-built-in-strategies/user-preference.ipynb) | User preference strategy |
| 01 | [`01-built-in-strategies/episodic.ipynb`](./01-built-in-strategies/episodic.ipynb) | Episodic memory strategy |
| 02 | `02-strategies-with-overrides.ipynb` | Prompt overrides on built-in strategies |
| 03 | `03-self-managed-strategy.ipynb` | Custom extraction + consolidation Lambdas |
| 04 | `04-namespaces-and-organization.ipynb` | `{actorId}` / `{sessionId}` / `{strategyId}` namespace templates |
| 05 | `05-retrieve-records-and-citations.ipynb` | `RetrieveMemoryRecords`, citation payloads |
| 06 | `06-structured-metadata.ipynb` | Record-level structured metadata for filtering |
| 07 | `07-batch-create-update-delete.ipynb` | Batch data-plane APIs |
| 08 | `08-redrive-failed-ingestions.ipynb` | `Redrive` for failed extractions |
| 09 | [`09-record-streaming.ipynb`](./09-record-streaming.ipynb) | Kinesis streaming (`METADATA_ONLY` / `FULL_CONTENT`) |

> **Status:** Notebooks 01–08 are placeholders documenting scope. Notebook 09 is existing content moved from `03-advanced-patterns/05-memory-streaming/`; streaming *use cases* built on top live in [`../../03-advanced-patterns/05-streaming-use-cases/`](../../03-advanced-patterns/05-streaming-use-cases/).
