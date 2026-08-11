# Why GP3 instead of GP2 for RDS storage?

GP3 is the current generation general-purpose SSD volume type for RDS and
EBS. GP2 is still selectable in the console and in older Infrastructure as
Code templates, which is why it keeps showing up in architecture proposals
even though it is the wrong default today.

**Why it matters:**
- GP3 decouples IOPS and throughput from volume size — a GP2 volume's
  baseline IOPS scale with capacity (3 IOPS/GB), which means a small GP2
  volume is throttled regardless of the workload's actual needs. GP3 gives a
  flat 3,000 IOPS and 125 MiB/s baseline at any size, provisionable higher.
- GP3 is priced lower per GB than GP2 for the same baseline performance, so
  choosing GP2 is very rarely a legitimate cost optimization — it is usually
  just an older template that was never updated.
- The only real reason to still choose GP2 is exact IOPS-per-GB legacy
  behavior some workloads were tuned against — rare, and worth calling out
  explicitly if that is the actual justification, rather than defaulting to
  it silently.

**What to check for:** an RDS or EBS volume with `StorageType: gp2` in the
proposal, with no stated reason. Flag it as a finding with the recommended
fix being GP3 at equivalent or better performance and lower cost.
