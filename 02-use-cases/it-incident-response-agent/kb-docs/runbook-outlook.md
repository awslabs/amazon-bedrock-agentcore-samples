# Runbook: Outlook desktop search and crash issues

## Symptoms
- Outlook search returns no results or stale results.
- Outlook crashes when opening large mailboxes or attachments.
- Profile won't load on first launch after laptop refresh.

## Diagnosis
1. Confirm the version of `outlook-desktop`. Versions earlier than 16.84
   are deprecated.
2. Check the OST file size. OST files larger than 50 GB are unsupported
   and frequently corrupt the search index.

## Resolution steps
1. Have the user close Outlook completely (including background processes).
2. Rebuild the Outlook profile:
   - Control Panel -> Mail -> Show Profiles -> Add new profile, then set as
     default. Old OST will rebuild on first launch.
3. If the issue persists after profile reset, file a change request to
   provision a new mailbox archive policy.

## Escalation
- If multiple users on the same team report the issue at once, escalate to
  the EUC team — likely a policy push problem rather than per-user.
