# Why does CloudTrail need to be multi-region?

A CloudTrail trail created without explicitly enabling multi-region logging
only captures API activity in the region it was created in. Most AWS
accounts are used across more than one region even when the primary
workload lives in just one — IAM, Route 53, CloudFront, and account-level
actions are global-service events that a single-region trail can miss
entirely, and any activity in a second region (intentional or not, including
by an attacker) goes unlogged.

**Why it matters:** compliance frameworks (HIPAA, PCI-DSS, SOC 2) and basic
incident-response practice both expect a complete, tamper-evident audit
trail of account activity. A single-region trail creates a blind spot that
is invisible until the moment it matters — during an incident investigation,
when the missing region's logs are the ones needed.

**What to check for:** a CloudTrail trail with `IsMultiRegionTrail: false`,
or no CloudTrail trail at all. The fix is enabling multi-region logging on
an existing trail (a one-line change, not a redesign) or creating one with
`is-multi-region-trail` set from the start — combined with log file
validation enabled and delivery to an S3 bucket with restrictive access,
ideally in a separate logging/audit account for anything compliance-scoped.
