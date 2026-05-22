# Event metadata and filtering

Attach key-value metadata to each event so you can filter `ListEvents` later without scanning the whole session. Examples: tag events by topic, channel, priority, or downstream-pipeline routing key.

## What you learn

- Adding metadata on `CreateEvent` (max 15 keys per event, 128-char keys, 256-char string values)
- Filtering `ListEvents` with `EQUALS_TO`, `EXISTS`, `NOT_EXISTS`
- Composing up to 5 filter expressions per request (logical AND across them)

## Run

```bash
python event-metadata-filtering.py boto3   # default — direct service calls
python event-metadata-filtering.py sdk     # documents the SDK gap (no metadata=)
python event-metadata-filtering.py cli     # print equivalent AWS CLI commands
```

## Best practices

- **Keep metadata small and bounded.** Use stable, low-cardinality keys (`topic`, `priority`, `channel`) — not free-form text.
- **Do not store sensitive data in metadata.** Event metadata is **not** encrypted with your customer-managed KMS key, even when the memory resource is. Keep PII/PHI in `payload`.
- Filter values are exact-match (`EQUALS_TO`); for free-text search you want long-term memory, not metadata filters.
- Plan your metadata schema up front — `indexedKeys` on `CreateMemory` cannot be removed once declared.
