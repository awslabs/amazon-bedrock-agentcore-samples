# What retention periods should S3 and CloudWatch Logs use?

Default retention (often "forever" for S3 with no lifecycle rule, and either
"never expire" or a short default for CloudWatch Logs) is rarely the right
answer for either cost or compliance, and the correct value depends on what
the data is.

**Compliance-driven data (audit logs, financial records, PHI-adjacent
records subject to regulatory retention):** many frameworks set a specific
floor — for example, several healthcare and financial retention schedules
require 6-7 years. Setting an S3 lifecycle rule that transitions to Glacier
or expires objects *before* that floor is a finding, even if it looks like a
sensible cost optimization — moving compliance data to Glacier at 90 days
when the regulatory minimum is 7 years violates the retention requirement,
it doesn't just make retrieval slower.

**Operational logs (application logs, access logs, general CloudWatch Log
Groups):** these usually do NOT need multi-year retention. A CloudWatch Log
Group left at "Never expire" (the default) silently accumulates storage
cost indefinitely. 90 days is a reasonable default for operational
troubleshooting logs unless a specific compliance or business reason
requires longer.

**What to check for:** (a) any S3 lifecycle rule or Glacier transition that
expires data faster than a stated compliance retention requirement, and (b)
CloudWatch Log Groups with no retention policy set (defaults to indefinite)
on non-compliance-driven operational logs. These are opposite-direction
findings — one is "retention too short," the other is "retention
unnecessarily long and costing money" — so state which one applies rather
than a generic "fix retention" note.
