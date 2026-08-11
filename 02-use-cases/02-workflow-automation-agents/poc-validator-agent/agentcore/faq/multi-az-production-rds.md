# Does production RDS need Multi-AZ?

Yes, for any database classified as production or handling data the business
cannot lose. Single-AZ RDS has no automatic failover — an Availability Zone
outage or an underlying host failure means downtime until AWS (or the
customer) manually restores from backup, which can take anywhere from
minutes to hours depending on database size.

**Why it matters:** Multi-AZ RDS keeps a synchronously-replicated standby in
a second Availability Zone and fails over automatically, typically in under
a minute, with no data loss for committed transactions. For any workload
where the business impact of an outage is non-trivial, single-AZ is a
finding, not a cost optimization — it is deferring an outage, not avoiding
one.

**Cost tradeoff, stated honestly:** Multi-AZ roughly doubles the compute and
storage cost of the RDS instance, because the standby runs full-time. That
doubling is a real and material line item — it should be shown separately in
any cost estimate (as a "compliance/availability premium," not buried in the
baseline) so a partner or client can see exactly what availability is
costing them, rather than discovering it as an unexplained total.

**What to check for:** `MultiAZ: false` (or the equivalent) on any RDS
instance whose name, tags, or context indicate production use. Non-production
(dev/staging/sandbox) databases are a legitimate case for single-AZ — the
finding is about production, not about Multi-AZ always being mandatory.
