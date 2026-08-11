# Why does a public-facing ALB/CloudFront need WAF managed rule groups?

Any architecture that terminates public internet traffic at an Application
Load Balancer or CloudFront distribution, and sits in front of an
application handling real user data or payments, should have AWS WAF
attached with at minimum the AWS-managed Core Rule Set
(`AWSManagedRulesCommonRuleSet`) and the Known Bad Inputs rule group
(`AWSManagedRulesKnownBadInputsRuleSet`).

**Why it matters:** WAF's managed rule groups block the OWASP Top 10 attack
patterns (SQL injection, cross-site scripting, common exploit signatures)
without the customer having to author and maintain their own rule set. Not
having WAF on a public endpoint is one of the most common findings across
architecture reviews precisely because it's easy to skip — the application
"works" without it in every demo and every load test, and the gap is only
visible once someone probes it.

**Cost note:** WAF is priced per Web ACL (a flat monthly fee) plus per rule
and per million requests evaluated — it is a genuinely small line item
relative to the compute it protects, which is part of why its absence reads
as an oversight rather than a deliberate cost tradeoff.

**What to check for:** a public ALB or CloudFront distribution with no
associated WAF Web ACL, or a Web ACL that exists but has no managed rule
groups attached (an empty or default-allow Web ACL provides no real
protection and should not be treated as satisfying the requirement).
