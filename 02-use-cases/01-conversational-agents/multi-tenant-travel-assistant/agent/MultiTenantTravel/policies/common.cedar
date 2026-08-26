// policies that apply to every tenant.
//
// Evaluated by the Gateway on every `tools/call`, BEFORE the target Lambda is invoked.
// That is the whole point: an `if` inside a tool handler is application code — correct
// until someone adds tool fourteen and forgets. This cannot be bypassed by the agent, and
// a reviewer audits it by reading two files rather than thirteen handlers.
//
// What Cedar can see here:
//   principal.getTag("<claim>")  — verified JWT claims (from the ACCESS token, which is
//                                  why the pre-token-generation trigger is load-bearing)
//   context.input.<arg>          — the tool's arguments (guard with `has` first, or a
//                                  missing argument is an evaluation error, not a deny)
//
// Three constraints the service enforces, each of which failed a deploy before it was
// understood:
//
//  1. **Action names carry the target prefix** — `policy___get_travel_policy`, not
//     `get_travel_policy`. Cedar supports no action wildcards, so tools are named
//     explicitly; a bare name would silently never match, which is what
//     `FAIL_ON_ANY_FINDINGS` exists to catch.
//  2. **Specific actions require a specific gateway ARN.** `resource is AgentCore::Gateway`
//     (the type check) is allowed *only* when matching any action. This is why the ARN below
//     is a `{{GATEWAY_ARN}}` placeholder rather than a literal: the gateway's id is generated
//     per-deploy, so a committed ARN would name *someone else's* gateway in any other account
//     and match nothing — an ENFORCE engine that denies every call while every resource
//     reports READY. `scripts/sync_policies.py` substitutes the deployed ARN.
//  3. **Cedar analysis rejects always-deny policies.** A blanket
//     `forbid(...) unless { principal.hasTag(...) }` is flagged *"Overly Restrictive:
//     Policy Engine will deny every request"* — because the analyser cannot prove the tag
//     ever exists, and for an `IamEntity` principal (which supports no tags at all) it
//     genuinely would deny everything. So fail-closed is expressed as **permits that
//     require the claim**, not as a blanket forbid: Cedar is deny-by-default, so a token
//     without `custom:tenant_id` matches no permit and is refused anyway. Same outcome,
//     and it survives automated analysis.
//
// What Cedar deliberately does NOT encode: hotel caps, cabin rules, star limits. Those are
// `TravelPolicy` *data* that differs per tenant and changes without a deploy — writing
// `$250` here would duplicate the record and drift from it. Cedar authorises *actions*;
// `check_policy_eligibility` computes *verdicts*.

// --- Read tools require a verified tenant ------------------------------------
//
// The `when` clause **is** the fail-closed control: a token minted without the
// pre-token-generation trigger carries no `custom:tenant_id`, matches no permit, and is
// denied by default.
//
// One place to see the entire read surface, which is the audit trail a reviewer wants —
// adding a read tool means adding it here. Specific actions, so a specific gateway ARN.
permit(
  principal is AgentCore::OAuthUser,
  action in [
    AgentCore::Action::"policy___get_travel_policy",
    AgentCore::Action::"policy___check_policy_eligibility",
    AgentCore::Action::"profile___get_traveler_profile",
    AgentCore::Action::"knowledge___search_policy_knowledge",
    AgentCore::Action::"trips___get_trips",
    AgentCore::Action::"search___search_flights",
    AgentCore::Action::"search___search_hotels",
    AgentCore::Action::"entry___check_entry_requirements",
    AgentCore::Action::"location___find_nearby",
    AgentCore::Action::"location___get_route",
    AgentCore::Action::"escalation___escalate_to_human"
  ],
  resource == AgentCore::Gateway::"{{GATEWAY_ARN}}"
)
when {
  principal.hasTag("custom:tenant_id")
};
