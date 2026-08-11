# How should a proposal identify its real cost drivers?

Every cost estimate should call out its top 2-3 cost drivers explicitly,
rather than presenting only a single bottom-line total. In practice, three
line items recur across most real-world estimates as the ones worth naming:

1. **GPU or specialized compute for ML/AI training or inference** — when
   present, this is very often 50-70% of the total monthly cost by itself.
   Burying it inside a general "compute" line item hides the single biggest
   lever a client has for cost control (e.g., spot instances, right-sizing
   the instance family, or batching training runs).
2. **Multi-AZ / high-availability database costs** — see the Multi-AZ FAQ.
   Roughly doubles the database line item and is easy to under-notice because
   it's a multiplier applied to an existing number, not a new visible line.
3. **Data transfer** — frequently underestimated because it does not show up
   until real traffic patterns are measured. Cross-AZ transfer, NAT Gateway
   data processing charges, and internet egress are all billed separately and
   can be a larger fraction of the total than the compute that "obviously"
   drives cost. Where actual usage data isn't available yet, state the
   estimate as directional and say so, rather than presenting a precise
   number built on an unstated assumption.

**Why it matters:** a client reading a single total cannot tell what to
question or what to optimize first. Naming the top drivers turns a cost
estimate into something actionable instead of just a number to accept or
reject.

**On engagement minimums:** figure out and state the client's actual budget
constraint *before* designing the architecture, not after. Designing an
unconstrained "ideal" architecture and then cutting it down after the client
reacts to the number wastes a review cycle and reads as not having listened
in the first place.
