# Short-term memory — core features

Framework-agnostic tutorials for the short-term memory primitives. Use these to understand the API surface before moving on to the framework integrations in [`../02-single-agent/`](../02-single-agent/) and [`../03-multi-agent/`](../03-multi-agent/).

Default surface: **boto3** (the raw API is clearest for primitive walkthroughs). Where a CLI one-liner adds value, it's inlined alongside.

| # | Notebook | Covers |
|---|---|---|
| 01 | `01-events-and-sessions.ipynb` | `CreateEvent`, `ListEvents`, `GetEvent`, `DeleteEvent` |
| 02 | `02-event-metadata-filtering.ipynb` | Event metadata tags + filtering in `ListEvents` |
| 03 | `03-actor-session-isolation.ipynb` | Multi-actor / multi-session organization patterns |
| 04 | `04-event-branching.ipynb` | The `branchId` primitive — how branches diverge from an event |

> **Status:** all four notebooks are currently placeholders documenting scope. Content to be authored.
